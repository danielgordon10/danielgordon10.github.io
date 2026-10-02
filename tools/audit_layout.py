"""Layout audit for the built site.

Loads each page in a real browser and reports the problems that are easy to miss
by reading HTML: horizontal overflow, text clipped by its own box, tap targets
that are too small to hit reliably, images that fail to load, missing fonts,
broken heading order, console errors and failed requests.

Run it against a served build:

    uv run site build
    (cd dist && python3 -m http.server 8899) &
    uv run --with playwright python tools/audit_layout.py http://localhost:8899
"""

from __future__ import annotations

import sys
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

PAGES = [
    "/",
    "/work/",
    "/about/",
    "/work/vince/",
    "/work/apple/",
    "/404.html",
]

VIEWPORTS = [("desktop", 1440, 900), ("mobile", 390, 844)]

#: Anything smaller than this is a fussy tap target. WCAG 2.2 asks for 24px.
MIN_TAP = 24

AUDIT_JS = r"""
(minTap) => {
  const problems = [];
  const docW = document.documentElement.clientWidth;

  if (document.documentElement.scrollWidth > docW + 1) {
    problems.push({
      kind: "page-overflow-x",
      detail: `scrollWidth ${document.documentElement.scrollWidth} > ${docW}`,
    });
  }

  const describe = (el) => {
    const id = el.id ? `#${el.id}` : "";
    const cls = el.className && typeof el.className === "string"
      ? "." + el.className.trim().split(/\s+/).slice(0, 3).join(".")
      : "";
    const text = (el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 28);
    return `${el.tagName.toLowerCase()}${id}${cls}${text ? ` "${text}"` : ""}`;
  };

  // An element sticking out is only a defect if nothing above it clips it away.
  const isClippedAway = (el) => {
    for (let p = el.parentElement; p; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (cs.overflowX !== "visible" || cs.overflowY !== "visible") return true;
    }
    return false;
  };

  for (const el of document.querySelectorAll("body *")) {
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") continue;
    // Intentionally hidden helpers are not defects.
    if (el.closest(".visually-hidden, .skip-link, .noscript-note")) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;

    if (r.right > docW + 2 && cs.position !== "fixed" && !isClippedAway(el)) {
      problems.push({
        kind: "overflow-right",
        el: describe(el),
        detail: `right ${Math.round(r.right)} > ${docW}`,
      });
    }

    // Clipped text. A line-clamp or a fade is deliberate truncation, not a bug.
    const clamped =
      cs.webkitLineClamp && cs.webkitLineClamp !== "none";
    const hasOwnText = Array.from(el.childNodes).some(
      (n) => n.nodeType === 3 && n.textContent.trim().length > 0
    );
    if (
      hasOwnText &&
      !clamped &&
      el.scrollHeight > el.clientHeight + 4 &&
      cs.overflowY === "hidden"
    ) {
      problems.push({
        kind: "clipped-text",
        el: describe(el),
        detail: `scrollHeight ${el.scrollHeight} > clientHeight ${el.clientHeight}`,
      });
    }
  }

  // Images: the page was scrolled and lazy sources were forced open before this
  // ran, so anything with no pixels really is missing.
  for (const img of document.images) {
    if (img.naturalWidth === 0) {
      problems.push({ kind: "image-broken", el: describe(img), detail: img.currentSrc || img.src });
      continue;
    }
    // `cover` crops to the box on purpose; only an un-cropped image is stretched.
    const fit = getComputedStyle(img).objectFit;
    if (fit === "fill" || fit === "none") {
      const srcAR = img.naturalWidth / img.naturalHeight;
      const outAR = img.width / img.height;
      if (outAR > 0 && Math.abs(srcAR - outAR) > 0.02) {
        problems.push({
          kind: "image-distorted",
          el: describe(img),
          detail: `src ${srcAR.toFixed(3)} vs box ${outAR.toFixed(3)}, object-fit ${fit}`,
        });
      }
    }
  }

  // True for a link that sits inside a running sentence: an inline element with
  // text flowing on both sides of it. WCAG 2.5.8 exempts exactly this case
  // ("the target is in a sentence or block of text"), and the exemption is the
  // right call rather than a loophole - a 24px floor on a word in a paragraph
  // can only be met by padding the paragraph, which costs line height and
  // breaks the rhythm of the text it is protecting.
  //
  // Anchors with `display: block/flex/grid` or in a list are standalone controls
  // and still get measured, so this only silences prose links.
  const BLOCK_TEXT = new Set(["P", "LI", "TD", "TH", "DD", "DT", "BLOCKQUOTE", "FIGCAPTION", "CAPTION", "H1", "H2", "H3", "H4"]);
  const isInlineInText = (el) => {
    if (el.tagName !== "A") return false;
    const display = getComputedStyle(el).display;
    if (display !== "inline" && display !== "inline-block") return false;

    // Walk up to the nearest block-level text container. The `authors()` macro
    // wraps each name in a <span class="me">, and prose runs through <strong>
    // and <em>, so the immediate parent is usually not the block - the test has
    // to be against the paragraph, not the span.
    let block = el;
    while (block.parentElement && !BLOCK_TEXT.has(block.tagName)) {
      const d = getComputedStyle(block).display;
      if (d !== "inline" && d !== "inline-block" && d !== "contents") return false;
      block = block.parentElement;
    }
    if (!BLOCK_TEXT.has(block.tagName)) return false;

    // A link wrapping an icon, image or badge is a button in disguise and is
    // still held to the minimum - only real prose counts.
    if (el.querySelector("img, svg, icon")) return false;

    // The block must hold more prose than this link does, otherwise the link is
    // the whole of the block and is standing alone.
    return block.textContent.trim().length > el.textContent.trim().length;
  };

  for (const el of document.querySelectorAll("a, button, input, [role=button]")) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (el.closest(".visually-hidden")) continue;
    if (isInlineInText(el)) continue;
    if (r.height < minTap) {
      problems.push({
        kind: "tap-target-small",
        el: describe(el),
        detail: `${Math.round(r.width)}x${Math.round(r.height)}`,
      });
    }
  }

  if (document.fonts) {
    if (document.fonts.status !== "loaded") {
      problems.push({ kind: "fonts-not-loaded", detail: document.fonts.status });
    }
    const h1 = getComputedStyle(document.querySelector("h1")).fontFamily;
    const body = getComputedStyle(document.body).fontFamily;
    for (const [name, used] of [["Newsreader", h1], ["Inter", body]]) {
      if (new RegExp(name, "i").test(used) && !document.fonts.check(`1em ${name}`)) {
        problems.push({ kind: "font-fallback", detail: `${name} requested by "${used}" not available` });
      }
    }
  }

  const headings = Array.from(document.querySelectorAll("h1,h2,h3,h4,h5,h6"))
    .filter((h) => h.getBoundingClientRect().height > 0)
    .map((h) => `h${h.tagName[1]}:${(h.textContent || "").trim().slice(0, 22)}`);
  const levels = headings.map((h) => Number(h[1]));
  if (levels.length && levels[0] !== 1) {
    problems.push({ kind: "no-h1", detail: `first heading is ${headings[0]}` });
  }
  for (let i = 1; i < levels.length; i++) {
    if (levels[i] - levels[i - 1] > 1) {
      problems.push({
        kind: "heading-skip",
        detail: `${headings[i - 1]} -> ${headings[i]}`,
      });
    }
  }

  // An element armed for a scroll-in animation is expected to be transparent
  // while it is still below the fold. One that is on screen and still hidden
  // means the reveal never fired, and the reader sees a blank card.
  const stillHidden = Array.from(document.querySelectorAll("[data-reveal]")).filter((el) => {
    if (getComputedStyle(el).opacity !== "0") return false;
    const r = el.getBoundingClientRect();
    return r.top < window.innerHeight && r.bottom > 0;
  });
  if (stillHidden.length) {
    problems.push({
      kind: "invisible-reveal",
      el: describe(stillHidden[0]),
      detail: `${stillHidden.length} on-screen element(s) still at opacity 0`,
    });
  }

  // --- color contrast -------------------------------------------------
  // Walk up for the first non-transparent background, resolve alpha properly,
  // and check the ratio. This is the check that matters most for a site with a
  // dark and a light theme, because one theme can pass while the other fails.
  const parseColor = (value) => {
    const m = value.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const parts = m[1].split(/[\s,/]+/).filter(Boolean).map(Number);
    const [r, g, b] = parts;
    const a = parts.length > 3 ? parts[3] : 1;
    if ([r, g, b, a].some(Number.isNaN)) return null;
    return { r, g, b, a };
  };

  const over = (fg, bg) => ({
    r: fg.r * fg.a + bg.r * (1 - fg.a),
    g: fg.g * fg.a + bg.g * (1 - fg.a),
    b: fg.b * fg.a + bg.b * (1 - fg.a),
    a: 1,
  });

  const channel = (v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };

  const luminance = (c) =>
    0.2126 * channel(c.r) + 0.7152 * channel(c.g) + 0.0722 * channel(c.b);

  const ratio = (a, b) => {
    const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
  };

  const effectiveBackground = (el) => {
    let stack = [];
    for (let p = el; p; p = p.parentElement) {
      const c = parseColor(getComputedStyle(p).backgroundColor);
      if (c && c.a > 0) {
        stack.push(c);
        if (c.a === 1) break;
      }
    }
    let result = { r: 255, g: 255, b: 255, a: 1 };
    for (let i = stack.length - 1; i >= 0; i--) result = over(stack[i], result);
    return result;
  };

  const seen = new Set();
  // A gradient or image background cannot be reduced to one color, so those
  // elements are skipped rather than reported with a made-up ratio. The two
  // places this is used deliberately (the avatar gradient and the image
  // caption scrim) are designed against white text.
  const hasPaint = (el) => {
    for (let p = el; p; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (cs.backgroundImage && cs.backgroundImage !== "none") return true;
      if (cs.webkitBackgroundClip === "text" || cs.backgroundClip === "text") return true;
    }
    return false;
  };

  for (const el of document.querySelectorAll("p, a, h1, h2, h3, h4, li, span, button, code, label, time, figcaption, pre")) {
    const text = Array.from(el.childNodes)
      .filter((n) => n.nodeType === 3)
      .map((n) => n.textContent.trim())
      .join("")
      .trim();
    if (!text) continue;

    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) < 0.15) continue;
    if (el.closest(".visually-hidden, .skip-link")) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (hasPaint(el)) continue;

    const fg = parseColor(cs.color);
    if (!fg) continue;
    const bg = effectiveBackground(el);
    const size = parseFloat(cs.fontSize);
    const bold = Number(cs.fontWeight) >= 700;
    const large = size >= 24 || (size >= 18.66 && bold);
    const need = large ? 3 : 4.5;
    const got = ratio(over(fg, bg), bg);
    if (got < need) {
      const key = `${el.tagName}.${el.className}|${cs.color}`;
      if (seen.has(key)) continue;
      seen.add(key);
      problems.push({
        kind: "contrast-low",
        el: describe(el),
        detail: `${got.toFixed(2)}:1 (needs ${need}:1) ${cs.fontSize}/${cs.color}`,
      });
    }
  }

  return {
    title: document.title,
    h1: document.querySelector("h1")?.textContent.trim().slice(0, 60) ?? null,
    h1Count: document.querySelectorAll("h1").length,
    headings,
    theme: document.documentElement.dataset.theme,
    problems,
  };
}
"""


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8899"
    total = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        for label, width, height in VIEWPORTS:
          for theme in ("dark", "light"):
            context = browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
                color_scheme=theme,
            )
            # Seed the stored choice so the page starts in the theme under test.
            context.add_init_script(
                f"try {{ localStorage.setItem('theme', '{theme}'); }} catch (e) {{}}"
            )
            page = context.new_page()
            console: list[str] = []
            failed: list[str] = []
            page.on(
                "console",
                lambda m: console.append(f"{m.type}: {m.text}")
                if m.type in ("error", "warning")
                else None,
            )
            page.on("pageerror", lambda e: console.append(f"pageerror: {e}"))
            page.on("requestfailed", lambda r: failed.append(f"{r.url} ({r.failure})"))
            page.on(
                "response",
                lambda r: failed.append(f"{r.url} -> HTTP {r.status}") if r.status >= 400 else None,
            )

            for path in PAGES:
                console.clear()
                failed.clear()
                page.goto(urljoin(base, path), wait_until="networkidle")
                # Walk the page so lazy images and reveal animations settle,
                # force every lazy image open, then return to the top before
                # measuring so an unloaded placeholder is not reported as broken.
                page.evaluate(
                    """async () => {
                        const step = window.innerHeight * 0.8;
                        const height = () => document.documentElement.scrollHeight;
                        for (let y = 0; y < height(); y += step) {
                            window.scrollTo(0, y);
                            await new Promise((r) => setTimeout(r, 60));
                        }
                        window.scrollTo(0, 0);
                        for (const img of document.images) img.loading = "eager";
                        await Promise.all(
                            Array.from(document.images).map((img) =>
                                img.complete && img.naturalWidth > 0
                                    ? null
                                    : new Promise((r) => {
                                        img.addEventListener("load", r, { once: true });
                                        img.addEventListener("error", r, { once: true });
                                    })
                            )
                        );
                        await Promise.all(
                            Array.from(document.images).map((img) => img.decode().catch(() => {}))
                        );
                        await new Promise((r) => setTimeout(r, 300));
                    }"""
                )
                result = page.evaluate(AUDIT_JS, MIN_TAP)
                result["problems"] += [
                    {"kind": "console", "detail": c} for c in console
                ] + [{"kind": "request", "detail": f} for f in failed]

                if result["h1Count"] != 1:
                    result["problems"].append(
                        {"kind": "h1-count", "detail": str(result["h1Count"])}
                    )
                if result["theme"] != theme:
                    result["problems"].append(
                        {
                            "kind": "theme-mismatch",
                            "detail": f"asked for {theme}, page is {result['theme']}",
                        }
                    )

                status = "ok" if not result["problems"] else f"{len(result['problems'])} issue(s)"
                print(f"[{label:7}/{theme:5}] {path:16} {status}")
                for problem in result["problems"]:
                    where = problem.get("el", "")
                    print(f"              - {problem['kind']}: {where} {problem['detail']}".rstrip())
                total += len(result["problems"])
            context.close()
        browser.close()

    print(f"\n{total} problem(s) total")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
