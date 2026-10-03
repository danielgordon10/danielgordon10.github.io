"""Behaviour tests for the built site.

Checks the things a layout audit cannot: that the theme toggle really persists
across page loads, that filtering works and is reflected in the URL,
that the video facade does not contact YouTube until it is clicked, and that
copy buttons put the right text on the clipboard.

    (cd dist && python3 -m http.server 8899) &
    uv run --with playwright python tools/audit_behavior.py http://localhost:8899
"""

from __future__ import annotations

import re
import sys
from urllib.parse import urlsplit

from playwright.sync_api import Page, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8899"

failures: list[str] = []
checks = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if condition:
        print(f"  ok    {label}")
    else:
        print(f"  FAIL  {label}{(' - ' + detail) if detail else ''}")
        failures.append(label)


def theme_of(page: Page) -> str:
    return page.evaluate("() => document.documentElement.dataset.theme")


# --------------------------------------------------------------- theme ---


def test_theme(page: Page) -> None:
    print("\ntheme")
    page.goto(f"{BASE}/", wait_until="networkidle")
    check(
        "a theme is applied on first paint",
        theme_of(page) in ("light", "dark"),
        theme_of(page),
    )

    page.click("[data-theme-toggle]")
    first = theme_of(page)
    check("toggle switches the theme", first in ("light", "dark"), first)

    # The whole point of the requirement: the choice must survive navigation.
    page.goto(f"{BASE}/work/", wait_until="networkidle")
    check("choice survives a navigation", theme_of(page) == first, theme_of(page))

    page.click("[data-theme-toggle]")
    second = theme_of(page)
    check("toggle switches back", second != first, second)

    page.goto(f"{BASE}/about/", wait_until="networkidle")
    check("second choice survives too", theme_of(page) == second, theme_of(page))

    stored = page.evaluate("() => localStorage.getItem('theme')")
    check("stored under the 'theme' key", stored == second, str(stored))

    # The pre-paint script has to be the thing that sets it, otherwise a
    # returning visitor sees a flash of the wrong theme.
    check(
        "document starts on the saved theme",
        page.evaluate("() => document.documentElement.dataset.theme")
        == page.evaluate("() => localStorage.getItem('theme')"),
    )
    page.evaluate("() => localStorage.setItem('theme', 'light')")
    page.goto(f"{BASE}/work/", wait_until="networkidle")
    check("saved light theme applied on load", theme_of(page) == "light", theme_of(page))

    # Leave the browser in a defined state for the rest of the run.
    page.evaluate("() => localStorage.removeItem('theme')")


def test_no_flash(page: Page) -> None:
    print("\nno theme flash")
    page.goto(f"{BASE}/", wait_until="domcontentloaded")
    check(
        "theme is set before the body exists",
        page.evaluate(
            "() => document.documentElement.dataset.theme !== undefined"
        ),
    )
    check(
        "no-js class is removed by the inline script",
        page.evaluate("() => !document.documentElement.classList.contains('no-js')"),
    )


# ------------------------------------------------------------ filtering ---


def test_filters(page: Page) -> None:
    print("\nwork filters")
    page.goto(f"{BASE}/work/", wait_until="networkidle")

    total = page.eval_on_selector_all("[data-results] [data-item]", "els => els.length")
    check("every item is listed without JavaScript", total == 18, str(total))

    page.click('[data-tag="reinforcement-learning"]')
    page.wait_for_timeout(200)
    shown = page.eval_on_selector_all(
        "[data-results] [data-item]:not([hidden])", "els => els.length"
    )
    check("tag filter narrows the list", 0 < shown < total, f"{shown} of {total}")

    matched = page.eval_on_selector_all(
        "[data-results] [data-item]:not([hidden])",
        "els => els.every(e => e.dataset.tags.split(' ').includes('reinforcement-learning'))",
    )
    check("every visible card carries the tag", matched)

    pressed = page.get_attribute('[data-tag="reinforcement-learning"]', "aria-pressed")
    check("active tag is marked pressed", pressed == "true", str(pressed))

    check(
        "the filter is recorded in the URL",
        "tags=reinforcement-learning" in page.url,
        page.url,
    )

    # Two tags are OR-ed: a card carrying either one is shown. Asserted as a
    # union rather than "every card has both", which is what the old AND check
    # did and which is exactly the behavior this replaced.
    page.click('[data-tag="robotics"]')
    page.wait_for_timeout(200)
    union = page.eval_on_selector_all(
        "[data-results] [data-item]:not([hidden])",
        "els => els.every(e => {const t = e.dataset.tags.split(' ');"
        " return t.includes('reinforcement-learning') || t.includes('robotics'); })",
    )
    check("two tags are combined with OR", union)

    # The union has to be strictly larger than either tag alone, or the OR is
    # quietly collapsing to an AND (or to whichever tag was clicked last).
    or_count = page.eval_on_selector_all(
        "[data-results] [data-item]:not([hidden])", "els => els.length"
    )
    page.click("[data-clear-filters]:not([hidden])")
    page.wait_for_timeout(150)
    page.click('[data-tag="robotics"]')
    page.wait_for_timeout(150)
    robotics_only = page.eval_on_selector_all(
        "[data-results] [data-item]:not([hidden])", "els => els.length"
    )
    page.click("[data-clear-filters]:not([hidden])")
    page.wait_for_timeout(150)
    page.click('[data-tag="reinforcement-learning"]')
    page.wait_for_timeout(150)
    rl_only = page.eval_on_selector_all(
        "[data-results] [data-item]:not([hidden])", "els => els.length"
    )
    check(
        "OR shows more than either tag alone",
        or_count > max(robotics_only, rl_only),
        f"or={or_count} robotics={robotics_only} rl={rl_only}",
    )
    # Put the two-tag state back for the URL round-trip checks below.
    page.click('[data-tag="robotics"]')
    page.wait_for_timeout(200)

    page.click("[data-clear-filters]:not([hidden])")
    page.wait_for_timeout(200)
    restored = page.eval_on_selector_all(
        "[data-results] [data-item]:not([hidden])", "els => els.length"
    )
    check("clear restores every item", restored == total, f"{restored} of {total}")
    check("clear empties the query string", urlsplit(page.url).query == "", page.url)

    # A filtered view has to be shareable, so the URL alone must rebuild it.
    page.goto(f"{BASE}/work/?tags=computer-vision", wait_until="networkidle")
    page.wait_for_timeout(300)
    from_url = page.eval_on_selector_all(
        "[data-results] [data-item]:not([hidden])", "els => els.length"
    )
    check("a ?tags= link restores the filter", 0 < from_url < total, str(from_url))
    check(
        "the restored tag button reads as pressed",
        page.get_attribute('[data-tag="computer-vision"]', "aria-pressed") == "true",
    )


def test_removed_chrome(page: Page) -> None:
    """The search box and the Type group were deliberately removed."""
    print("\nremoved work-page chrome")
    page.goto(f"{BASE}/work/", wait_until="networkidle")
    check(
        "no cards are left in the lists",
        page.eval_on_selector_all("[data-results] .card", "els => els.length") == 0,
    )
    check(
        "the search box is gone",
        page.eval_on_selector_all("[data-search-input]", "els => els.length") == 0,
    )
    check(
        "the Type filter group is gone",
        page.eval_on_selector_all("[data-type]", "els => els.length") == 0,
    )
    check(
        "the Year filter is gone",
        page.eval_on_selector_all("[data-year]", "els => els.length") == 0,
    )
    check(
        "no result counter is rendered",
        page.eval_on_selector_all("[data-result-count]", "els => els.length") == 0,
    )
    check(
        "items are rows, not cards",
        page.eval_on_selector_all("[data-results] .row", "els => els.length") == 18,
    )
    check(
        "the search JSON index is no longer shipped",
        page.request.get(f"{BASE}/assets/js/work-index.json").status == 404,
    )


def test_favicon_follows_theme(page: Page) -> None:
    """The SVG switches itself on prefers-color-scheme; the manual toggle needs
    site.ts to repoint the <link> at the dark twin.

    Written relative to whatever theme the page is on rather than assuming dark,
    because an earlier test may have left a preference in localStorage."""
    print("\nfavicon")
    page.goto(f"{BASE}/", wait_until="networkidle")

    def icon_for(theme: str) -> str:
        # Clicking the toggle flips whatever is showing, so read it afterward.
        before = page.get_attribute("html", "data-theme")
        page.click("[data-theme-toggle]")
        page.wait_for_timeout(150)
        href = page.get_attribute("link[data-favicon]", "href")
        page.click("[data-theme-toggle]")
        page.wait_for_timeout(150)
        assert before
        return href if before != theme else page.get_attribute("link[data-favicon]", "href")

    check(
        "the themed favicon link is present",
        bool(page.get_attribute("link[data-favicon]", "href")),
    )
    dark = icon_for("dark")
    check("a dark page uses the dark mark", dark.endswith("favicon-dark.svg"), dark)
    check("the dark mark is actually served", page.request.get(f"{BASE}/{dark.lstrip('/')}").status == 200)

    light = icon_for("light")
    check("a light page uses the light mark", light.endswith("favicon.svg"), light)
    check(
        "toggling back and forth settles",
        light.endswith("favicon.svg") and not light.endswith("favicon-dark.svg"),
        light,
    )


def test_contact_card(page: Page) -> None:
    """The handles sit in a flex row after the label; a fixed max-width used to
    clip "danielgordon10" to "danielgordo..."."""
    print("\ncontact card")
    page.goto(f"{BASE}/", wait_until="networkidle")
    clipped = page.eval_on_selector_all(
        ".contact-card .handle",
        "els => els.filter(e => e.scrollWidth > e.clientWidth + 1).map(e => e.textContent)",
    )
    check("no handle is clipped", not clipped, str(clipped))

    full = page.eval_on_selector_all(
        ".contact-card .handle",
        "els => els.filter(e => e.textContent.trim() === 'danielgordon10').length",
    )
    check("the GitHub handle is rendered whole", full == 1, str(full))

    # The frame, not the photo: the photo is scaled up 1.12 to crop a colored
    # band baked into the source JPEG, so its box is larger than what is visible
    # and sub-pixel rounding makes width != height by a fraction of a pixel.
    photo = page.eval_on_selector(
        ".contact-card__frame", "e => {const r = e.getBoundingClientRect(); return [r.width, r.height];}"
    )
    check(
        "the portrait is a decent size, not a thumbnail",
        photo[0] >= 120 and abs(photo[0] - photo[1]) < 1,
        f"{photo[0]:.0f}x{photo[1]:.0f}",
    )

    # The hero card's portrait used to be capped narrower than the panel, which
    # left a band of dead space to its right.
    slack = page.eval_on_selector(
        ".contact-card",
        """e => {
             // The frame, not the photo: the photo is inset 5px inside it, and
             // measuring the photo made that deliberate inset read as dead space.
             const photo = e.querySelector(".contact-card__frame");
             const cs = getComputedStyle(e);
             const inner = e.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
             return Math.round(inner - photo.getBoundingClientRect().width);
           }""",
    )
    check("the portrait fills the card, no dead space", slack <= 1, f"{slack}px")

    # The hero card once sat stranded at the left of an over-wide `auto` track,
    # with a band of dead space to its right.
    slack = page.eval_on_selector(
        ".hero__inner",
        """e => {
             const cs = getComputedStyle(e);
             const card = e.querySelector(".contact-card").getBoundingClientRect();
             return Math.round(e.getBoundingClientRect().right
                               - parseFloat(cs.paddingRight) - card.right);
           }""",
    )
    check("the hero card is flush with the right edge", abs(slack) <= 1, f"{slack}px")

    footer = page.eval_on_selector(
        ".site-footer__line", "e => {const r = e.getBoundingClientRect(); return r.width;}"
    )
    check("the footer is a single line of text", 0 < footer < 600, f"{footer:.0f}px")
    check(
        "the footer reports the build month",
        re.search(r"Last updated \w+ \d{4}", page.text_content(".site-footer__line") or "") is not None,
        (page.text_content(".site-footer__line") or "").strip(),
    )
    check(
        "the footer has no link columns left",
        page.eval_on_selector_all(".footer-links", "els => els.length") == 0,
    )


def test_structural_css(page: Page) -> None:
    """Guard against layout rules going missing.

    Nothing else here notices an undefined class: an unstyled .about-grid is
    still readable and still passes contrast, it just collapses to one column.
    So the structural boxes are checked for the geometry they are supposed to
    produce.
    """
    print("\nstructural css")
    page.goto(f"{BASE}/about/", wait_until="networkidle")
    cols = page.eval_on_selector(
        ".about-grid", "e => getComputedStyle(e).gridTemplateColumns.split(' ').length"
    )
    check("the about page keeps two columns", cols == 2, f"{cols} track(s)")
    check(
        "the contact card portrait is square",
        page.eval_on_selector(".contact-card__photo", "e => e.clientWidth === e.clientHeight"),
    )

    page.goto(f"{BASE}/work/", wait_until="networkidle")
    check(
        "the filter label has its own line, above the chips",
        page.evaluate("""() => {
          const label = document.querySelector('.filter-group__label');
          const chips = document.querySelector('.filter-group__chips');
          if (!label || !chips) return false;
          return label.getBoundingClientRect().bottom <= chips.getBoundingClientRect().top + 1;
        }"""),
    )
    check(
        "no chip wraps under the filter label",
        page.evaluate("""() => {
          const label = document.querySelector('.filter-group__label').getBoundingClientRect();
          return ![...document.querySelectorAll('.filter-group__chips button')]
            .some(c => c.getBoundingClientRect().top < label.bottom - 1);
        }"""),
    )
    check(
        "the filter group is labeled Tags, not Topic",
        page.eval_on_selector(".filter-group__label", "e => e.textContent.trim()") == "Tags",
    )
    check(
        "the empty state is hidden until it is needed",
        page.eval_on_selector("[data-empty]", "e => getComputedStyle(e).display") == "none",
    )
    # thumb | title+meta | date. No marker track: the timeline is home-page only.
    check(
        "work-index rows stack the date in its own column",
        page.eval_on_selector(
            ".row", "e => getComputedStyle(e).gridTemplateColumns.split(' ').length"
        )
        == 3,
    )
    # A pseudo-element cannot go in querySelectorAll, so the spine is asked for
    # separately - but it has to be checked on the index too, not just here.
    check(
        "the work index carries no timeline dots",
        page.eval_on_selector_all(".row__node", "els => els.length") == 0,
    )
    check(
        "the work index carries no timeline spine",
        page.eval_on_selector(".rows", "e => getComputedStyle(e, '::before').content")
        == "none",
    )
    check(
        "the footer wraps into a centered block",
        page.eval_on_selector(".site-footer .wrap", "e => getComputedStyle(e).justifyContent")
        == "center",
    )


# --------------------------------------------------------------- video ---


def test_home_timeline(page: Page) -> None:
    """The roles list on the homepage is a timeline. The work cards are not."""
    print("\nhome timeline")
    page.goto(f"{BASE}/", wait_until="networkidle")

    check(
        "the roles list draws one spine",
        page.eval_on_selector(".roles--timeline", "e => getComputedStyle(e, '::before').content")
        != "none",
    )
    check(
        "every role has a dot",
        page.eval_on_selector_all(".roles--timeline .role__node", "els => els.length") >= 2,
    )

    geom = page.evaluate("""() => {
      const roles = document.querySelector('.roles--timeline');
      const spine = getComputedStyle(roles, '::before');
      const rr = roles.getBoundingClientRect();
      const spineX = rr.left + parseFloat(spine.left) + parseFloat(spine.width) / 2;
      return [...roles.querySelectorAll('.role')].map(role => {
        const n = role.querySelector('.role__node').getBoundingClientRect();
        const d = role.querySelector('.role__when').getBoundingClientRect();
        return {
          spineOff: (n.left + n.width / 2) - spineX,
          vsDate: (n.top + n.height / 2) - (d.top + d.height / 2),
        };
      });
    }""")
    for i, g in enumerate(geom):
        check(f"dot {i} sits on the spine", abs(g["spineOff"]) <= 1, f"{g['spineOff']:.1f}px off")
        check(f"dot {i} is level with its date", abs(g["vsDate"]) <= 1, f"{g['vsDate']:.1f}px off")

    # The featured work list is cards, with no spine or dots anywhere.
    check(
        "the featured work list has no spine or dots",
        page.eval_on_selector_all(".rows .row__node", "els => els.length") == 0
        and page.eval_on_selector(".rows", "e => getComputedStyle(e, '::before').content")
        == "none",
    )


def test_work_cards(page: Page) -> None:
    """One card treatment, used identically on the homepage and the work index."""
    print("\nwork cards")
    styles = {}
    for label, path in (("home", "/"), ("work", "/work/")):
        page.goto(f"{BASE}{path}", wait_until="networkidle")
        styles[label] = page.evaluate("""() => {
          const row = document.querySelector('.row');
          const cs = getComputedStyle(row);
          const when = row.querySelector('.row__when').getBoundingClientRect();
          const rr = row.getBoundingClientRect();
          return {
            radius: cs.borderTopLeftRadius,
            pad: cs.padding,
            border: cs.borderTopWidth,
            bg: cs.backgroundColor,
            align: cs.alignItems,
            centeredDate: Math.abs(
              (when.top + when.height / 2) - (rr.top + rr.height / 2)) < 2,
            gap: getComputedStyle(row.parentElement).gap,
            thumb: Math.round(row.querySelector('.row__thumb').getBoundingClientRect().width),
            margin: cs.marginLeft + '/' + cs.marginRight,
          };
        }""")

    for key in styles["home"]:
        check(
            f"the cards match on both pages ({key})",
            styles["home"][key] == styles["work"][key],
            f"home={styles['home'][key]!r} work={styles['work'][key]!r}",
        )
    check("the dates are centered in the cards", styles["home"]["centeredDate"])
    check("the thumbnails are large", styles["home"]["thumb"] >= 176, f"{styles['home']['thumb']}px")
    check("the cards have margin around them", styles["home"]["gap"] != "normal")


def test_row_text_selectable(page: Page) -> None:
    """Row and timeline text can be highlighted and copied.

    The whole row is clickable via a stretched overlay on the title anchor. That
    overlay used to paint *over* the row's content, so a drag landed on an empty
    absolutely-positioned box and the browser began a click instead of a
    selection - none of the text could be selected. It is now painted behind the
    content (`z-index: -1` plus `isolation: isolate` on the row), so text is hit
    as text and only the background, the gaps and the thumbnail navigate.

    Link text is deliberately not tested: Chrome starts a link-drag instead of a
    selection when a drag begins on an anchor, on this site and everywhere else,
    and no CSS changes that. Only non-link text is asserted here.
    """
    print("\nrow text selection")
    for path, selector in (
        ("/work/", ".row__abstract"),
        ("/", ".role__detail p"),
    ):
        page.goto(f"{BASE}{path}", wait_until="networkidle")
        # Let the 600ms reveal transition finish, otherwise the element is still
        # moving and the measured rect is stale by the time the drag runs.
        page.evaluate("(s) => document.querySelector(s)?.scrollIntoView({ block: 'center' })", selector)
        page.wait_for_timeout(1000)
        page.evaluate("() => window.getSelection().removeAllRanges()")

        box = page.evaluate(
            """(s) => {
              const el = document.querySelector(s);
              if (!el) return null;
              const r = document.createRange();
              r.selectNodeContents(el);
              const rects = [...r.getClientRects()].filter((x) => x.height > 0);
              if (!rects.length) return null;
              const c = rects[0];
              return { x1: c.left + 1, y: c.top + c.height / 2, x2: c.right - 1 };
            }""",
            selector,
        )
        if box is None:
            check(f"text is selectable ({path} {selector})", False, "element or text rect not found")
            continue

        page.mouse.move(box["x1"], box["y"])
        page.mouse.down()
        for i in range(1, 12):
            page.mouse.move(box["x1"] + (box["x2"] - box["x1"]) * i / 11, box["y"])
        page.mouse.up()
        selected = page.evaluate("() => window.getSelection().toString()")
        check(
            f"text is selectable ({path} {selector})",
            len(selected.strip()) > 3,
            f"drag selected {selected!r}",
        )

    # And the click targets the fix had to keep working.
    page.goto(f"{BASE}/work/", wait_until="networkidle")
    thumb = page.evaluate(
        """() => {
          const t = document.querySelector('.row__thumb').getBoundingClientRect();
          return { x: t.left + t.width / 2, y: t.top + t.height / 2 };
        }"""
    )
    page.mouse.click(thumb["x"], thumb["y"])
    page.wait_for_timeout(600)
    check(
        "the thumbnail still opens the item",
        page.url.rstrip("/").endswith("/work/apple"),
        f"url={page.url}",
    )

    page.goto(f"{BASE}/work/", wait_until="networkidle")
    gap = page.evaluate(
        """() => {
          const r = document.querySelector('.row').getBoundingClientRect();
          return { x: r.left + 5, y: r.top + r.height / 2 };
        }"""
    )
    page.mouse.click(gap["x"], gap["y"])
    page.wait_for_timeout(600)
    check(
        "the empty background still opens the item",
        page.url.rstrip("/").endswith("/work/apple"),
        f"url={page.url}",
    )


def test_contact_cards_match(page: Page) -> None:
    """The contact card renders the same on the homepage and on /about/."""
    print("\ncontact card parity")
    seen = {}
    for label, path in (("home", "/"), ("about", "/about/")):
        page.goto(f"{BASE}{path}", wait_until="networkidle")
        seen[label] = page.evaluate("""() => {
          const c = document.querySelector('.contact-card');
          const cs = getComputedStyle(c);
          const photo = c.querySelector('.contact-card__photo');
          const email = c.querySelector('[data-copy-email] span');
          const ecs = getComputedStyle(email);
          return {
            width: cs.width,
            bg: cs.backgroundColor,
            pad: cs.padding,
            radius: cs.borderTopLeftRadius,
            items: [...c.querySelectorAll('.contact-list a, .contact-list button')]
                     .map(a => a.textContent.trim().replace(/\s+/g, ' ')),
            headings: [...c.querySelectorAll('h2, h3')].map(h => h.textContent.trim()),
            photoWidth: Math.round(photo.getBoundingClientRect().width),
            emailLines: Math.round(email.getBoundingClientRect().height / parseFloat(ecs.lineHeight)),
            srcset: !!photo.getAttribute('srcset'),
          };
        }""")

    for key in seen["home"]:
        check(
            f"the contact card matches ({key})",
            seen["home"][key] == seen["about"][key],
            f"home={seen['home'][key]!r} about={seen['about'][key]!r}",
        )
    check("the email fits on one line", seen["home"]["emailLines"] == 1, str(seen["home"]["emailLines"]))
    check("the card carries a srcset for the portrait", seen["home"]["srcset"])


def test_video_facade(page: Page) -> None:
    print("\nvideo facade")
    page.goto(f"{BASE}/work/tetris/", wait_until="networkidle")
    check("the video item renders a facade", page.locator("[data-youtube]").count() == 1)
    check("no iframe before the click", page.locator(".media__frame iframe").count() == 0)

    requests: list[str] = []
    page.on("request", lambda r: requests.append(r.url))
    page.reload(wait_until="networkidle")
    check(
        "no YouTube request on load",
        not any("youtube" in r for r in requests),
        str([r for r in requests if "youtube" in r][:2]),
    )

    page.click("[data-youtube-play]")
    page.wait_for_timeout(600)
    check("an iframe is inserted on click", page.locator(".media__frame iframe").count() == 1)
    src = page.get_attribute(".media__frame iframe", "src") or ""
    check("the embed uses the no-cookie domain", "youtube-nocookie.com" in src, src)
    check("the embed autoplays", "autoplay=1" in src, src)
    check("the poster button is gone", page.locator("[data-youtube-play]").count() == 0)


# ---------------------------------------------------------------- copy ---


def test_copy(page: Page) -> None:
    print("\ncopy buttons")
    page.goto(f"{BASE}/work/vince/", wait_until="networkidle")
    if page.locator("[data-copy-target]").count() == 0:
        print("  --    no BibTeX block on this page, skipped")
        return
    page.click("[data-copy-target]")
    page.wait_for_timeout(300)
    copied = page.evaluate("() => navigator.clipboard.readText()")
    check("BibTeX is on the clipboard", "title" in copied.lower() or "author" in copied.lower(), copied[:60])
    check(
        "the button confirms the copy",
        page.get_attribute("[data-copy-target]", "data-copied") == "true",
    )


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            permissions=["clipboard-read", "clipboard-write"],
        )
        page = context.new_page()
        page.on("pageerror", lambda e: failures.append(f"pageerror: {e}"))

        test_theme(page)
        test_no_flash(page)
        test_filters(page)
        test_removed_chrome(page)
        test_favicon_follows_theme(page)
        test_contact_card(page)
        test_structural_css(page)
        test_home_timeline(page)
        test_work_cards(page)
        test_row_text_selectable(page)
        test_contact_cards_match(page)
        test_video_facade(page)
        test_copy(page)

        context.close()
        browser.close()

    print(f"\n{checks - len(failures)}/{checks} checks passed")
    for f in failures:
        print(f"  failed: {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
