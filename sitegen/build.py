"""Turn ``data/`` + ``templates/`` into a complete, self-contained static site.

Everything under the output directory is generated. Delete it and re-run and
you get a byte-identical site (modulo the build timestamp) - there is no state
in it that cannot be rebuilt from the data files.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import unquote, urlsplit

from jinja2 import Environment

from .data import ROOT, STATIC_DIR, SiteContext
from .models import Item, ItemType
from .render import build_env, markdown, plain, srcset

ASSETS = ROOT / "assets"
TS_ENTRY = ASSETS / "ts" / "site.ts"
JS_OUT = ASSETS / "js" / "site.js"
CSS_IN = ASSETS / "css" / "site.css"

#: directories under the output dir that never ship
IGNORED_DIR_NAMES = {".DS_Store", "__pycache__", ".git"}
SKIP_SUFFIXES = {".map", ".pyc", ".CR2", ".CR3", ".MOV", ".swp"}


def _json_escape_address(value: str) -> str:
    """Escape the email address in the JSON-LD block.

    The template gets the same treatment via the ``entity`` filter, but a
    ``<script type="application/ld+json">`` body is raw text - the HTML parser
    does not decode entities inside it - so HTML entities would survive into
    the JSON as literal ``&#100;`` and break the document. ``\\uXXXX`` escapes
    are valid JSON, decode to the identical string, and keep the address out
    of the served bytes.
    """
    return "".join(f"\\u{ord(c):04x}" for c in value)


@dataclass
class BuildResult:
    pages: int
    assets: int
    bytes: int
    seconds: float


# --------------------------------------------------------------------------
# asset pipeline
# --------------------------------------------------------------------------


def _esbuild() -> list[str]:
    local = ROOT / "node_modules" / ".bin" / "esbuild"
    if local.exists():
        return [str(local)]
    npx = shutil.which("npx")
    if npx:
        return [npx, "--yes", "esbuild"]
    raise SystemExit(
        "esbuild is required to compile assets/ts/site.ts but was not found.\n"
        "Run `npm install` once (it installs esbuild into node_modules/),\n"
        "or set ESBUILD to the path of an esbuild binary."
    )


def compile_typescript(force: bool = False) -> Path:
    """Bundle the TypeScript client into assets/js/site.js."""
    if not TS_ENTRY.exists():
        raise SystemExit(f"missing TypeScript entry point: {TS_ENTRY}")

    needs_build = force or not JS_OUT.exists() or (
        TS_ENTRY.stat().st_mtime > JS_OUT.stat().st_mtime
    )
    if not needs_build:
        return JS_OUT

    cmd = _esbuild() + [
        str(TS_ENTRY),
        "--bundle",
        "--format=esm",
        "--target=es2020",
        "--minify",
        f"--outfile={JS_OUT}",
    ]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"esbuild failed:\n{result.stderr}")
    return JS_OUT


# --------------------------------------------------------------------------
# page rendering
# --------------------------------------------------------------------------


def _root_prefix(out_path: Path) -> str:
    """Relative path from a built page back to the site root.

    ``work/vince/index.html`` is served from ``/work/vince/``, so every root
    asset needs two hops: ``../../favicon/...``.
    """
    return "../" * len(out_path.parent.parts)


def _make_link(root: str):
    def link(path: str) -> str:
        """Root-absolute data paths -> correct relative URL for this page."""
        if not path.startswith("/") or path.startswith("//"):
            return path
        if path == "/":
            # The home page has no parent to climb, and `href=""` is a relative
            # self-reference that breaks the brand link.
            return root or "./"
        return root + path.lstrip("/")

    return link


class SiteBuilder:
    def __init__(self, ctx: SiteContext, out_dir: Path) -> None:
        self.ctx = ctx
        self.out_dir = out_dir
        self.env: Environment = build_env(ctx)
        self.built: list[Path] = []
        # The footer reports when the site was last generated. SOURCE_DATE_EPOCH
        # overrides it so a reproducible build can pin the value.
        epoch = os.environ.get("SOURCE_DATE_EPOCH")
        self.built_at: dt.datetime = (
            dt.datetime.fromtimestamp(int(epoch), dt.timezone.utc)
            if epoch and epoch.isdigit()
            else dt.datetime.now()
        )

    # -- helpers ---------------------------------------------------------

    def render(self, template: str, out_path: Path, **context: Any) -> Path:
        root = _root_prefix(out_path)
        env = self.env.overlay()

        # Social-preview metadata is page-level, but it has to fall back to the
        # site portrait. Pull it out of the render context so a page that has no
        # image of its own cannot blank the tag out.
        og_image = context.pop("og_image", None) or f"/{self.ctx.person.photo}"
        og_image_alt = context.pop("og_image_alt", None) or self.ctx.person.photo_alt_text

        link = _make_link(root)
        # srcset renders site-relative URLs, so it has to be bound to this
        # page's root prefix the same way the `link` global is.
        env.filters["srcset"] = lambda value: srcset(value, link)
        # Same reason: Markdown fields can hold site-relative links (the person
        # intro links to /work/apple/ and /work/thirdwave/), and those have to
        # be rebased for the page they land on.
        env.filters["md"] = lambda value: markdown(value, link)
        env.globals.update(
            root=root,
            link=link,
            abs_url=self._abs_url,
            page_url=self._page_url(out_path),
            og_image=og_image,
            og_image_alt=og_image_alt,
            person_json_ld=self._person_json_ld(),
            built=self.built_at,
        )
        rendered = env.get_template(template).render(ctx=self.ctx, **context)
        target = self.out_dir / out_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
        self.built.append(target)
        return target

    @staticmethod
    def _page_url(out_path: Path) -> str:
        """Site-root path for a built file, e.g. work/vince/index.html -> /work/vince/."""
        parts = out_path.parent.parts
        return "/" + "".join(f"{p}/" for p in parts)

    def _person_json_ld(self) -> str:
        """schema.org Person, emitted once on every page for rich results."""
        person = self.ctx.person
        data: dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": "Person",
            "name": person.name,
            "url": self._abs_url("/"),
            "image": self._abs_url(f"/{person.photo}"),
            "email": _json_escape_address(f"mailto:{person.email}"),
            "jobTitle": person.role,
            "worksFor": {"@type": "Organization", "name": person.org},
            "sameAs": [s.href for s in person.socials if not s.is_email],
        }
        if person.location:
            data["address"] = {
                "@type": "PostalAddress",
                "addressLocality": person.location,
            }
        return json.dumps(data, indent=2)

    @property
    def _abs_url(self):
        base = self.ctx.site.url

        def abs_url(path: str) -> str:
            if path.startswith(("http://", "https://", "//", "mailto:")):
                return path
            return f"{base}/{path.lstrip('/')}"

        return abs_url

    # -- pages -----------------------------------------------------------

    def build(self) -> None:
        self.page_home()
        self.page_work()
        self.page_about()
        for item in self.ctx.by_date:
            self.page_item(item)
        self.page_404()
        self.sitemap()
        self.robots()
        self.manifest()

    def page_home(self) -> None:
        self.render(
            "home.html",
            Path("index.html"),
            active="home",
            title=self.ctx.person.name,
            description=self.ctx.site.description,
            featured=self.ctx.featured,
            recent=self.ctx.by_date[:6],
            positions=self.ctx.positions[:2],
            education=self.ctx.education,
            tag_groups=self.ctx.tag_groups,
            tag_counts=self.ctx.tag_counts,
            page_class="page-home",
        )

    def page_work(self) -> None:
        self.render(
            "work.html",
            Path("work/index.html"),
            active="work",
            title="Work",
            description=(
                "Publications, projects, roles and courses by "
                f"{self.ctx.person.name}, filterable by topic."
            ),
            items=self.ctx.by_date,
            tag_groups=self.ctx.tag_groups,
            tag_counts=self.ctx.tag_counts,
            page_class="page-work",
        )

    def page_about(self) -> None:
        self.render(
            "about.html",
            Path("about/index.html"),
            active="about",
            title="Info",
            description=f"About {self.ctx.person.name}: background and experience.",
            tag_groups=self.ctx.tag_groups,
            page_class="page-about",
        )

    def page_item(self, item: Item) -> None:
        description = plain(item.abstract)[:180] or item.title
        og_image = f"/{item.media.image}" if item.media.image else None
        self.render(
            "item.html",
            item.output_path,
            active="work",
            title=item.title,
            description=description,
            og_image=og_image,
            og_image_alt=item.media.alt or item.title,
            item=item,
            item_json_ld=self._item_json_ld(item),
            page_class="page-item",
        )

    def _item_json_ld(self, item: Item) -> str:
        """schema.org ScholarlyArticle / Person, so search engines and Scholar
        can read the citation metadata without scraping the layout."""
        types = {
            ItemType.PAPER: "ScholarlyArticle",
            ItemType.DATASET: "Dataset",
        }
        data: dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": types.get(item.type, "CreativeWork"),
            "name": item.title,
            "headline": item.title,
            "url": self._abs_url(item.url),
            "datePublished": item.date.isoformat(),
            "author": [
                {
                    "@type": "Person",
                    "name": a.rstrip("*").strip(),
                    **(
                        {"url": self._abs_url("/")}
                        if self.ctx.person.is_me(a.rstrip("*").strip())
                        else {}
                    ),
                }
                for a in item.authors
            ],
        }
        if item.abstract:
            data["abstract"] = plain(item.abstract)
        if item.venue:
            data["publisher"] = {"@type": "Organization", "name": item.venue}
        for link in item.links:
            if link.kind.value == "paper":
                data.setdefault("sameAs", []).append(
                    link.href
                    if link.href.startswith("http")
                    else self._abs_url(link.href)
                )
        return json.dumps(data, indent=2)

    def page_404(self) -> None:
        self.render(
            "404.html",
            Path("404.html"),
            active="",
            title="Page not found",
            description="That page does not exist.",
            page_class="page-404",
        )

    # -- machine-readable extras -----------------------------------------

    def sitemap(self) -> None:
        urls: list[tuple[str, dt.date, str]] = [
            ("/", self.ctx.last_updated, "1.0"),
            ("/work/", self.ctx.last_updated, "0.9"),
            ("/about/", self.ctx.last_updated, "0.7"),
        ]
        for item in self.ctx.by_date:
            urls.append((item.url, item.date, "0.8"))
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]
        for path, lastmod, priority in urls:
            lines += [
                "  <url>",
                f"    <loc>{self._abs_url(path)}</loc>",
                f"    <lastmod>{lastmod.isoformat()}</lastmod>",
                f"    <priority>{priority}</priority>",
                "  </url>",
            ]
        lines.append("</urlset>")
        self._write_text(Path("sitemap.xml"), "\n".join(lines) + "\n")

    def robots(self) -> None:
        self._write_text(
            Path("robots.txt"),
            f"User-agent: *\nAllow: /\n\nSitemap: {self._abs_url('/sitemap.xml')}\n",
        )

    def manifest(self) -> None:
        """Web app manifest, generated so the icons stay in step with the data."""
        person = self.ctx.person
        manifest = {
            "name": person.name,
            "short_name": person.first_name,
            "description": self.ctx.site.description,
            "start_url": "/",
            "display": "standalone",
            "background_color": self.ctx.site.theme_color,
            "theme_color": self.ctx.site.theme_color,
            "icons": [
                {
                    "src": "/favicon/android-chrome-192x192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                },
                {
                    "src": "/favicon/android-chrome-512x512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                },
            ],
        }
        self._write_text(
            Path("site.webmanifest"), json.dumps(manifest, indent=2) + "\n"
        )

    def _write_text(self, path: Path, text: str) -> None:
        target = self.out_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        self.built.append(target)

    # -- static passthrough ---------------------------------------------

    def copy_assets(self, include_unreferenced: bool = False) -> tuple[int, int]:
        copied = 0
        total = 0

        for ref in sorted(self.ctx.static_refs):
            source = STATIC_DIR / ref
            if source.is_file():
                self._copy(source, Path(ref))
                copied += 1
                total += source.stat().st_size

        if include_unreferenced:
            for orphan in self.ctx.unreferenced_static:
                rel = orphan.relative_to(STATIC_DIR)
                self._copy(orphan, rel)
                copied += 1
                total += orphan.stat().st_size

        for extra in (STATIC_DIR / "cv.pdf",):
            if extra.is_file():
                rel = extra.relative_to(STATIC_DIR)
                if not (self.out_dir / rel).exists():
                    self._copy(extra, rel)
                    copied += 1
                    total += extra.stat().st_size

        for name in ("fonts", "favicon"):
            folder = STATIC_DIR / name
            if not folder.is_dir():
                continue
            for path in sorted(folder.rglob("*")):
                if not path.is_file() or path.name in IGNORED_DIR_NAMES:
                    continue
                if path.suffix in SKIP_SUFFIXES:
                    continue
                rel = path.relative_to(STATIC_DIR)
                self._copy(path, rel)
                copied += 1
                total += path.stat().st_size

        # compiled front-end
        if CSS_IN.exists():
            self._copy(CSS_IN, Path("assets/css/site.css"))
            copied += 1
            total += CSS_IN.stat().st_size
        if JS_OUT.exists():
            self._copy(JS_OUT, Path("assets/js/site.js"))
            copied += 1
            total += JS_OUT.stat().st_size

        return copied, total

    def _copy(self, source: Path, rel: Path) -> int:
        target = self.out_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return 1


# --------------------------------------------------------------------------
# output verification
# --------------------------------------------------------------------------

_LOCAL_ATTR = re.compile(r'(?:href|src)="([^"]*)"')
_SRCSET_ATTR = re.compile(r'srcset="([^"]*)"')
_SKIP_PREFIXES = ("http://", "https://", "//", "mailto:", "tel:", "data:", "#")


def _local_urls(html: str) -> Iterator[str]:
    """Every local URL a page points at, from href/src and from srcset.

    srcset is a comma-separated list of "<url> <descriptor>" candidates, so its
    URLs have to be split out one by one. Missing these is how a responsive
    image ends up broken while its `src` fallback is present: the browser
    chooses from the srcset, never from the fallback.
    """
    yield from _LOCAL_ATTR.findall(html)
    for candidates in _SRCSET_ATTR.findall(html):
        for candidate in candidates.split(","):
            url = candidate.strip().split(" ")[0].strip()
            if url:
                yield url


def find_broken_links(out_dir: Path) -> list[tuple[Path, str, str]]:
    """Resolve every local href/src in the built HTML against the real files.

    Templates build relative URLs so the site also works when opened straight
    from disk. That is convenient but easy to get wrong, and a broken asset is
    invisible until someone loads the page, so the build refuses to finish with
    dangling references.
    """
    broken: list[tuple[Path, str, str]] = []
    for page in sorted(out_dir.rglob("*.html")):
        # A page served from /work/vince/ resolves URLs against that directory.
        base = page.parent
        for url in _local_urls(page.read_text(encoding="utf-8")):
            url = url.strip()
            if not url or url.startswith(_SKIP_PREFIXES):
                continue
            path = unquote(urlsplit(url).path)
            if not path:
                continue
            target = (base / path.lstrip("/")).resolve()
            if path.endswith("/"):
                target = target / "index.html"
            if not target.exists():
                rel = (
                    target.relative_to(out_dir)
                    if target.is_relative_to(out_dir)
                    else target
                )
                broken.append((page.relative_to(out_dir), url, str(rel)))
    return broken


def build(
    out_dir: Path | None = None,
    force_ts: bool = False,
    include_unreferenced: bool = False,
    clean: bool = True,
) -> BuildResult:
    import time

    start = time.perf_counter()
    out_dir = (out_dir or (ROOT / "dist")).resolve()

    ctx = SiteContext()
    compile_typescript(force=force_ts)

    if clean and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    builder = SiteBuilder(ctx, out_dir)
    builder.build()
    assets, size = builder.copy_assets(include_unreferenced=include_unreferenced)

    # GitHub Pages must not run Jekyll over the output
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    broken = find_broken_links(out_dir)
    if broken:
        for page, url, target in broken[:20]:
            print(f"  broken link in {page}: {url} -> missing {target}")
        raise SystemExit(
            f"build failed: {len(broken)} broken local link(s) in the output"
        )

    return BuildResult(
        pages=len(builder.built),
        assets=assets,
        bytes=size,
        seconds=time.perf_counter() - start,
    )


def tree_size(path: Path) -> tuple[int, int]:
    count = 0
    size = 0
    for file in path.rglob("*"):
        if file.is_file():
            count += 1
            size += file.stat().st_size
    return count, size
