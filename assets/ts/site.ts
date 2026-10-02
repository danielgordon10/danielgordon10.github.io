/**
 * Client-side behaviour for the site.
 *
 * Everything here is progressive enhancement: the HTML that arrives from the
 * generator is already complete and readable. This file only adds the things
 * that need a browser — filtering, the theme toggle, the lightbox-free
 * video facade and copy buttons.
 *
 * Built by esbuild to assets/js/site.js. No runtime dependencies.
 */

type Theme = "light" | "dark";

const THEME_KEY = "theme";

/* ------------------------------------------------------------------ theme -- */

/** The favicon <link> that site.ts rewrites when the theme changes. */
function syncFavicon(theme: Theme): void {
  const link = document.querySelector<HTMLLinkElement>('link[data-favicon]');
  if (!link) return;
  // The SVG carries its own prefers-color-scheme block, so this only needs to
  // agree with it when the page theme has been chosen by hand - otherwise both
  // mechanisms fight and the icon flickers as the OS setting changes.
  //
  // The dark path is derived from the current href rather than hardcoded, so a
  // site served from a subdirectory keeps its prefix. Both halves have to
  // tolerate either filename: rewriting only favicon.svg would leave the link
  // stuck on favicon-dark.svg the first time the visitor toggled back.
  const current = link.getAttribute("href") ?? "";
  const lightHref = current.replace(/-dark\.svg$/, ".svg");
  const href = theme === "dark" ? lightHref.replace(/\.svg$/, "-dark.svg") : lightHref;
  if (current !== href) link.setAttribute("href", href);
}

function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

function initTheme(): void {
  const toggle = document.querySelector<HTMLButtonElement>("[data-theme-toggle]");
  if (!toggle) return;

  const sync = (): void => {
    const theme = currentTheme();
    toggle.setAttribute(
      "aria-label",
      theme === "dark" ? "Switch to light theme" : "Switch to dark theme",
    );
    syncFavicon(theme);
  };

  toggle.addEventListener("click", () => {
    const next: Theme = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* storage unavailable: the choice just will not persist */
    }
    sync();
  });

  // Follow the OS while the visitor has not made an explicit choice.
  const media = window.matchMedia("(prefers-color-scheme: light)");
  media.addEventListener("change", (event) => {
    let stored: string | null = null;
    try {
      stored = localStorage.getItem(THEME_KEY);
    } catch {
      /* ignore */
    }
    if (stored !== "light" && stored !== "dark") {
      document.documentElement.dataset.theme = event.matches ? "light" : "dark";
      sync();
    }
  });

  sync();
}

/* ----------------------------------------------------------------- header -- */

function initHeader(): void {
  {
    /* The veil is driven by scroll distance, not by a boolean.

       Three attempts got this wrong before. A constant 55% read as a slab in
       both themes. Two states - 12% at rest, 88% stuck - fixed the top but
       swapped in a single-frame jump of 84/255 the moment you scrolled. One
       constant 12% removed the jump but left the bar too transparent once rows
       were passing under it, dropping nav contrast to 2.25:1.

       So: fully transparent at scrollY 0, ramping to opaque over the first
       RANGE px of scroll. Continuous, so there is no frame to catch, and the
       value is written as a percentage the stylesheet can drop straight into
       color-mix without doing arithmetic on a unitless number. */
    const RANGE = 140;
    /* Ceiling, not a floor. The bar goes fully opaque once scrolled, which is a
       deliberate reversal: two adjacent blurred bars met in a visible line, and
       the user judged that seam worse than the slab it was avoiding. The ramp
       still earns its keep - transparent at scrollY 0 so the hero image runs
       under the header untouched, opaque by the time anything is passing
       underneath. Only the resting state stays see-through. */
    const MAX_VEIL = 100;
    const MAX_BLUR = 20;
    let queued = false;

    const paint = (): void => {
      queued = false;
      const travelled = Math.min(Math.max(window.scrollY, 0), RANGE);
      const t = travelled / RANGE;
      /* Written to :root, where the .site-header rules read them.
         The sticky section heads used to read these three too, which is how they
         ended up sharing the header's glass; they are opaque now and take
         `var(--bg)` directly. */
      const root = document.documentElement.style;
      root.setProperty("--header-veil", `${(t * MAX_VEIL).toFixed(1)}%`);
      /* The blur ramps too. It used to sit at a constant 18px, which was what made
         the bar look opaque at scrollY 0: a heavy blur over the hero image is a
         visibly different material from the sharp image around it, and that edge
         reads as a filled bar even at 0% alpha. No blur at rest, full blur once
         content is passing underneath. */
      root.setProperty("--header-blur", `${(t * MAX_BLUR).toFixed(2)}px`);
      /* The saturation has to ramp with everything else. It was left at a flat
         160% while the blur and fill ramped to zero, so at scrollY 0 the bar was
         still applying a filter to the hero image - measured 74% more saturated
         than the strip immediately below it, which is the edge the eye was
         catching. 100% is a no-op, so the top of the page is truly untouched. */
      root.setProperty("--header-sat", `${(100 + t * 60).toFixed(1)}%`);
    };

    const schedule = (): void => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(paint);
    };

    paint();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule, { passive: true });
  }

  const nav = document.querySelector<HTMLElement>("[data-nav]");
  const toggle = document.querySelector<HTMLButtonElement>("[data-nav-toggle]");
  if (!nav || !toggle) return;

  const setOpen = (open: boolean): void => {
    nav.dataset.open = String(open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  };

  toggle.addEventListener("click", () => {
    setOpen(nav.dataset.open !== "true");
  });

  nav.addEventListener("click", (event) => {
    if ((event.target as HTMLElement).closest("a")) setOpen(false);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && nav.dataset.open === "true") {
      setOpen(false);
      toggle.focus();
    }
  });
}

/* --------------------------------------------------------------- filtering -- */

const normalise = (value: string): string =>
  value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");

/** One filterable item on the work index. */
interface WorkItem {
  el: HTMLElement;
  tags: string[];
}

/** Tag filter for the work index. No search box, no type filter, no years. */
class WorkFilter {
  private form: HTMLFormElement;
  private results: HTMLElement;
  private items: WorkItem[] = [];
  private emptyEl: HTMLElement | null = null;
  private clearButtons: HTMLButtonElement[] = [];
  private tagButtons: HTMLButtonElement[] = [];

  private activeTags = new Set<string>();

  constructor(form: HTMLFormElement) {
    this.form = form;
    // The control panel is a <form> but the list it drives deliberately sits
    // outside it, so the results are looked up at page level, not form level.
    const results = document.querySelector<HTMLElement>("[data-results]");
    if (!results) throw new Error("work filter: no [data-results] container on the page");
    this.results = results;
  }

  init(): void {
    this.items = Array.from(
      this.results.querySelectorAll<HTMLElement>("[data-item]"),
    ).map((el) => ({
      el,
      tags: (el.dataset.tags ?? "").split(" ").filter(Boolean),
    }));

    this.emptyEl = document.querySelector<HTMLElement>("[data-empty]");
    this.clearButtons = Array.from(
      document.querySelectorAll<HTMLButtonElement>("[data-clear-filters]"),
    );
    this.tagButtons = Array.from(
      this.form.querySelectorAll<HTMLButtonElement>("[data-tag]"),
    );

    this.tagButtons.forEach((button) => {
      button.addEventListener("click", () => this.toggleTag(button.dataset.tag ?? ""));
    });
    this.clearButtons.forEach((button) =>
      button.addEventListener("click", () => this.reset()),
    );
    // The form has no fields to submit any more - the tag chips are buttons -
    // but Enter inside a <form> can still trigger a navigation on some engines.
    this.form.addEventListener("submit", (event) => event.preventDefault());

    // Rebuild state from the URL, so a filtered view can be shared or reached
    // with the back button, and so /work/?tags=robotics links still work.
    this.readUrl();
    window.addEventListener("popstate", () => {
      this.readUrl();
      this.apply(false);
    });

    this.apply(false);
  }

  private toggleTag(tag: string): void {
    const key = normalise(tag);
    if (!key) return;
    if (this.activeTags.has(key)) {
      this.activeTags.delete(key);
    } else {
      this.activeTags.add(key);
    }
    // The pressed state is what the stylesheet uses to highlight a chosen tag,
    // so it has to be updated here as well as on load.
    this.syncPressed();
    this.apply();
  }

  private syncPressed(): void {
    this.tagButtons.forEach((button) => {
      const on = this.activeTags.has(normalise(button.dataset.tag ?? ""));
      button.setAttribute("aria-pressed", String(on));
    });
  }

  private reset(): void {
    this.activeTags.clear();
    this.syncPressed();
    this.apply();
  }

  private writeUrl(): void {
    const params = new URLSearchParams();
    if (this.activeTags.size) params.set("tags", [...this.activeTags].join(","));
    const search = params.toString();
    const url = `${window.location.pathname}${search ? `?${search}` : ""}`;
    window.history.replaceState(null, "", url);
  }

  private readUrl(): void {
    const params = new URLSearchParams(window.location.search);
    this.activeTags = new Set(
      (params.get("tags") ?? "")
        .split(",")
        .map((t) => normalise(t.trim()))
        .filter(Boolean),
    );
    this.syncPressed();
  }

  private matches(item: WorkItem): boolean {
    // Tags are OR-ed. The comment here said so while the loop below did the
    // opposite: it returned false unless the item carried *every* active tag,
    // so picking "robotics" and "computer vision" gave the two items carrying
    // both rather than everything in either field.
    //
    // No active tags means no filter, so show everything - which is what the
    // empty loop did before and still has to do.
    if (this.activeTags.size === 0) return true;
    for (const tag of this.activeTags) {
      if (item.tags.includes(tag)) return true;
    }
    return false;
  }

  private apply(writeHistory = true): void {
    let shown = 0;
    for (const item of this.items) {
      const visible = this.matches(item);
      item.el.hidden = !visible;
      if (visible) shown += 1;
    }

    if (this.emptyEl) this.emptyEl.dataset.shown = String(shown === 0);

    const dirty = this.activeTags.size > 0;
    this.clearButtons.forEach((button) => {
      button.hidden = !dirty;
    });

    if (writeHistory) this.writeUrl();
  }
}

/* ---------------------------------------------------------------- youtube -- */

/** Swap the poster for the real iframe only once the visitor asks for it. */
function initVideoFacades(): void {
  document.querySelectorAll<HTMLElement>("[data-youtube]").forEach((figure) => {
    const id = figure.dataset.youtube;
    const poster = figure.querySelector<HTMLElement>("[data-youtube-play]");
    const frame = figure.querySelector<HTMLElement>(".media__frame");
    if (!id || !poster || !frame) return;

    poster.addEventListener("click", () => {
      const iframe = document.createElement("iframe");
      iframe.src = `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0`;
      iframe.title = poster.getAttribute("aria-label") ?? "Video";
      iframe.allow =
        "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture";
      iframe.allowFullscreen = true;
      iframe.loading = "lazy";
      frame.replaceChildren(iframe);
    });
  });
}

/* ------------------------------------------------------------------- copy -- */

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Clipboard API needs a secure context; fall back to the old trick.
    try {
      const area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.append(area);
      area.select();
      const ok = document.execCommand("copy");
      area.remove();
      return ok;
    } catch {
      return false;
    }
  }
}

function flashButton(button: HTMLElement, message: string, revertMs = 1800): void {
  const label = button.querySelector("span");
  if (!label) return;
  const original = label.textContent ?? "";
  label.textContent = message;
  button.dataset.copied = "true";
  window.setTimeout(() => {
    label.textContent = original;
    delete button.dataset.copied;
  }, revertMs);
}

function initCopyButtons(): void {
  document.querySelectorAll<HTMLButtonElement>("[data-copy-target]").forEach((button) => {
    button.addEventListener("click", async () => {
      const selector = button.dataset.copyTarget ?? "";
      const source = document.querySelector(selector);
      if (!source) return;
      const text = source.textContent ?? "";
      const ok = await copyText(text.trim());
      flashButton(button, ok ? "Copied" : "Press Ctrl+C");
    });
  });

  document.querySelectorAll<HTMLButtonElement>("[data-copy-email]").forEach((button) => {
    button.addEventListener("click", async () => {
      const email = button.dataset.copyEmail ?? "";
      const ok = await copyText(email);
      if (ok) {
        // Confirm in place. The bubble is CSS, driven by data-copied.
        button.dataset.copied = "true";
        window.setTimeout(() => delete button.dataset.copied, 1800);
        return;
      }
      // Only if the clipboard was refused - an insecure context, or a browser
      // that blocks the permission - hand the address to the mail app so the
      // click is not simply swallowed. Running this unconditionally meant every
      // copy also opened a blank compose window.
      window.location.href = `mailto:${email}`;
    });
  });
}

/* ----------------------------------------------------------------- reveal -- */

/**
 * Fade content up as it scrolls into view.
 *
 * The CSS only hides an element once site.ts has added `.is-armed`, so a
 * failure here degrades to "everything visible" rather than "half the page is
 * blank". Elements already on screen are never armed at all.
 */
function initReveal(): void {
  const targets = Array.from(document.querySelectorAll<HTMLElement>("[data-reveal]"));
  if (!targets.length) return;

  const show = (el: HTMLElement): void => {
    el.classList.add("is-revealed");
    el.classList.remove("is-armed");
  };

  if (
    !("IntersectionObserver" in window) ||
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  ) {
    targets.forEach(show);
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        show(entry.target as HTMLElement);
        observer.unobserve(entry.target);
      }
    },
    // A positive bottom margin starts the fade slightly before the element
    // reaches the viewport. A negative one would leave the last row of a page
    // sitting in a dead band that can never intersect once you hit the bottom.
    { rootMargin: "100px 0px 0px 0px", threshold: 0 },
  );

  // Arming is decided by the observer rather than by measuring here: at
  // DOMContentLoaded the images have not loaded, so every box measures zero
  // and anything measured now would be classified wrongly. The observer's
  // first callback reports what is really on screen and runs before the first
  // paint, so nothing above the fold is ever painted in the hidden state.
  for (const el of targets) {
    el.classList.add("is-armed");
    observer.observe(el);
  }

  // Safety net. If anything about the observer misbehaves - a browser quirk, a
  // layout that never reports as intersecting, an anchor jump past everything -
  // nothing is left invisible.
  window.setTimeout(() => targets.forEach(show), 4000);
}

/* ------------------------------------------------------------------- boot -- */

function boot(): void {
  initTheme();
  initHeader();
  initVideoFacades();
  initCopyButtons();
  initReveal();
  document.querySelectorAll<HTMLFormElement>("[data-filters]").forEach((form) => {
    new WorkFilter(form).init();
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot, { once: true });
} else {
  boot();
}
