"""Jinja environment: templates, filters and the helpers every page gets.

Two conventions the templates rely on:

``root``
    Relative path from the current page back to the site root - ``""`` at the
    top level, ``"../"`` one level down, and so on. Using a relative prefix
    (rather than ``/``) means the built site also works when opened straight
    from disk.

``link()``
    Turns a site-root-absolute path from the data files (``/cv.pdf``) into the
    correct relative URL for the current page depth. External URLs pass
    through untouched.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import markdown_it
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from jinja2.exceptions import TemplateError
from markupsafe import Markup

from .data import SiteContext
from .format import short_date

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "templates"

_EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:)?//", re.I)


# --------------------------------------------------------------------------
# markdown
# --------------------------------------------------------------------------


def _build_markdown() -> markdown_it.MarkdownIt:
    md = markdown_it.MarkdownIt(
        "commonmark",
        {"html": True, "linkify": True, "typographer": True},
    )
    md.enable("strikethrough")
    md.enable("table")

    # markdown-it-py has no bespoke `link_open` rule - `<a>` tags are produced by
    # the generic token renderer. Overriding it here is the supported way to add
    # attributes to every link.
    renderer = md.renderer

    def link_open(tokens, idx, options, env):  # type: ignore[no-untyped-def]
        # Renderer rules are called as plain functions with (tokens, idx, options, env).
        token = tokens[idx]
        href = token.attrGet("href") or ""
        if _EXTERNAL.match(href):
            token.attrSet("target", "_blank")
            token.attrSet("rel", "noopener noreferrer")
        return renderer.renderToken(tokens, idx, options, env)

    md.renderer.rules["link_open"] = link_open
    return md


_markdown = _build_markdown()


def markdown(text: str | None) -> Markup:
    if not text:
        return Markup("")
    return Markup(_markdown.render(text.strip()))


def inline(text: str | None) -> Markup:
    """Markdown for a single line, with block-level elements stripped out."""
    if not text:
        return Markup("")
    rendered = _markdown.renderInline(text.strip())
    return Markup(rendered)


def plain(text: str | None) -> str:
    """Strip every tag - for <title>, meta descriptions and social previews."""
    if not text:
        return ""
    rendered = _markdown.render(text)
    return re.sub(r"<[^>]+>", "", rendered).replace("&amp;", "&").strip()


# --------------------------------------------------------------------------
# formatting filters
# --------------------------------------------------------------------------


def srcset(value: list[str], link) -> str:
    """Render a ``["images/me.jpg 512w", ...]`` list as a srcset attribute.

    Jinja has no "join with a separator but no trailing one", and a trailing
    comma in srcset is at best a wasted empty candidate and at worst a parse
    error in a stricter consumer.
    """
    return ", ".join(f"{link('/' + cand.split()[0])} {cand.split()[1]}" for cand in value)


def entity(text: str) -> Markup:
    """Encode every character as a numeric HTML entity.

    Used for the email address so it is not readable as plain text in the
    served HTML. The browser decodes it on the way in, so this works in every
    place an address can appear without any JavaScript:

    - element text          ``<span>&#100;...&#109;</span>``
    - attribute values      ``data-copy-email="&#100;..."`` -> the DOM value is
      already decoded, so ``dataset.copyEmail`` hands JavaScript the real
      address
    - URLs                  ``href="mailto:&#100;..."`` resolves normally

    Three-digit zero-padded entities are used to match the encoding the
    previous version of the site shipped.

    Returns ``Markup``: the output is nothing but entities and letters, and
    escaping it again would emit ``&amp;#100;``, which the browser renders as
    the literal text ``&#100;`` rather than the letter ``d``.
    """
    return Markup("".join(f"&#{ord(c):03d};" for c in text))


def initials(name: str) -> str:
    parts = [p for p in re.split(r"[\s.]+", name) if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def has_equal_contribution(names: Iterable[str]) -> bool:
    """True if any author carries the co-first-author `*` marker."""
    return any(n.endswith("*") for n in names)


def join_and(values: Iterable[str], conjunction: str = "and") -> str:
    items = list(values)
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} {conjunction} {items[1]}"
    return f"{', '.join(items[:-1])}, {conjunction} {items[-1]}"


def truncate(text: str, length: int) -> str:
    text = re.sub(r"\s+", " ", plain(text))
    if len(text) <= length:
        return text
    cut = text[:length].rsplit(" ", 1)[0]
    return cut + "\u2026"


def file_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024 or unit == "GB":
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} GB"  # pragma: no cover


# --------------------------------------------------------------------------
# environment
# --------------------------------------------------------------------------


def _icons() -> dict[str, str]:
    """Inline SVG paths, keyed by name. Kept in Python so templates stay clean."""
    return {
        "arrow-right": "M5 12h14M13 6l6 6-6 6",
        "arrow-up-right": "M7 17 17 7M8 7h9v9",
        "arrow-left": "M19 12H5M11 18l-6-6 6-6",
        "check": "M20 6 9 17l-5-5",
        "copy": "M9 9h10v10a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V11a2 2 0 0 1 2-2Z M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1",
        "document": "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Zm0 0v5h5",
        "cube": "M12 3 3 8v8l9 5 9-5V8Zm0 0v18M3 8l9 5 9-5",
        "building": "M4 21V5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v16M14 9h4a2 2 0 0 1 2 2v10M2 21h20M7 7h3M7 11h3M7 15h3",
        "academic": "M12 4 2 9l10 5 10-5Zm-6 8v5c0 1 3 2.5 6 2.5s6-1.5 6-2.5v-5",
        "microphone": "M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3ZM5 11a7 7 0 0 0 14 0M12 18v3",
        "database": "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3Zm0 0v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
        "play": "M8 5.5v13l11-6.5Z",
        "paper": "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Zm0 0v5h5M9 13h6M9 17h4",
        "demo": "m4 3 7.5 17 2.4-6.6 6.6-2.4Z",
        "other": "M10.5 13.5a4 4 0 0 0 5.7 0l2.3-2.3a4 4 0 0 0-5.7-5.7l-1 1m1.2 3.5a4 4 0 0 0-5.7 0l-2.3 2.3a4 4 0 0 0 5.7 5.7l1-1",
        "code": "m9 18-6-6 6-6m6-6 6 6-6 6",
        "project": "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z",
        "data": "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3Z",
        "poster": "M5 3h14a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Zm3 4h8M8 21v-6h8v6",
        "video": "M3 6h12a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1Zm14 4 5-3v10l-5-3",
        "slides": "M3 4h18M4 4v10a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V4M12 15v5m-4 0h8",
        "course": "M12 4 2 9l10 5 10-5Zm-6 8v5c0 1 3 2.5 6 2.5s6-1.5 6-2.5v-5M22 9v6",
        "mail": "M3 6h18a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1Zm-1 1 10 7L21 7",
        "location": "M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11Zm0-8.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z",
        "calendar": "M4 6h16a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1Zm3-3v5m10-5v5M3 11h18",
        "sun": "M12 5V2m0 20v-3m7-7h3M2 12h3m11.5-6.5 2-2m-15 15 2-2m0-11 2 2m11 11 2 2M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z",
        "moon": "M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z",
        "search": "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm6-2 4 4",
        "close": "M6 6l12 12M18 6 6 18",
        "menu": "M3 6h18M3 12h18M3 18h18",
        "quote": "M9 7H5a2 2 0 0 0-2 2v3a2 2 0 0 0 2 2h2v1a3 3 0 0 1-3 3m14-11h-4a2 2 0 0 0-2 2v3a2 2 0 0 0 2 2h2v1a3 3 0 0 1-3 3",
        "sparkle": "M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4Z",
        "github": "M9 19c-4 1.3-4-2.2-6-2.7m12 5.2v-3.4c0-1 .1-1.4-.5-2 2.3-.3 4.5-1.1 4.5-5a3.9 3.9 0 0 0-1.1-2.7 3.6 3.6 0 0 0-.1-2.7s-.9-.3-3 1.1a10.3 10.3 0 0 0-5.4 0c-2.1-1.4-3-1.1-3-1.1a3.6 3.6 0 0 0-.1 2.7A3.9 3.9 0 0 0 4.4 9c0 3.9 2.2 4.7 4.5 5-.6.6-.6 1.2-.5 2v3.7",
        "linkedin": "M6.5 8.5H3.4V21h3.1ZM4.9 3.5a1.8 1.8 0 1 0 0 3.6 1.8 1.8 0 0 0 0-3.6ZM21 13.9c0-3.1-1.7-4.6-3.9-4.6-1.8 0-2.6 1-3 1.7V8.5H11V21h3.1v-6.9c0-1.2.5-1.8 1.4-1.8s1.4.6 1.4 1.8V21H21Z",
        "scholar": "M12 3 1 9l11 6 9-4.9V16h2V9ZM6 11.5V16c0 1.7 2.7 3 6 3s6-1.3 6-3v-4.5",
        "layers": "m12 3 9 5-9 5-9-5Zm9 9-9 5-9-5m18 4.5-9 5-9-5",
        "x": "M4 4l7 9-7 7h2.5l5.5-6 4.5 6H20l-7.3-9.5L19.5 4H17l-5 5.5L8 4Z",
        "filter": "M3 5h18M6 12h12M10 19h4",
    }


def build_env(ctx: SiteContext) -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters.update(
        md=markdown,
        inline=inline,
        plain=plain,
        date_range=lambda item: item.date_label,
        short_date=short_date,
        initials=initials,
        has_equal_contribution=has_equal_contribution,
        join_and=join_and,
        truncate=truncate,
        filesize=file_size,
        entity=entity,
    )
    env.globals.update(
        site=ctx.site,
        person=ctx.person,
        nav=ctx.site.nav,
        icons=_icons(),
        tag=ctx.tag_by_id.__getitem__,
        abs_url=_site_url_factory(ctx.site.url),
        raise_unknown_icon=_unknown_icon,
    )
    return env


def _unknown_icon(name: object) -> None:
    """Fail the build on a typo'd icon name instead of shipping an empty <svg>."""
    known = ", ".join(sorted(_icons()))
    raise TemplateError(
        f"unknown icon {name!r}; available icons: {known}"
    )


def _site_url_factory(base: str):
    """Build the ``abs_url`` helper: root-relative path -> full URL for meta tags."""

    def abs_url(path: str) -> str:
        if path.startswith(("http://", "https://", "//", "mailto:")):
            return path
        return f"{base}/{path.lstrip('/')}"

    return abs_url
