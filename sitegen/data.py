"""Load, validate and cross-check everything under ``data/``.

Every rule that spans more than one file is enforced here so that a bad edit
fails the build with an actionable message instead of producing a broken page.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from functools import cached_property
from pathlib import Path
from typing import Any

import yaml
from pydantic import TypeAdapter, ValidationError

from .models import (
    Item,
    ItemType,
    Person,
    Site,
    Strict,
    Tag,
)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ITEMS_DIR = DATA_DIR / "items"
STATIC_DIR = ROOT / "static"


class DataError(Exception):
    """Raised with a human-readable list of every problem found."""


# --------------------------------------------------------------------------
# auxiliary content models
# --------------------------------------------------------------------------


class Education(Strict):
    degree: str
    org: str
    years: str
    href: str | None = None


# --------------------------------------------------------------------------
# yaml loading
# --------------------------------------------------------------------------


def _read_yaml(path: Path) -> Any:
    if not path.exists():
        raise DataError(
            f"missing required data file: {path.relative_to(ROOT)}\n"
            "See README.md for what goes in it."
        )
    try:
        with path.open(encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise DataError(f"{path.relative_to(ROOT)} is not valid YAML:\n{exc}") from exc


def _parse(model: type[Any], path: Path) -> Any:
    """Load a YAML file and validate it, reporting problems in YAML-path form."""
    raw = _read_yaml(path)
    if raw is None:
        raise DataError(f"{path.relative_to(ROOT)} is empty")
    adapter = TypeAdapter(model)
    try:
        return adapter.validate_python(raw)
    except ValidationError as exc:
        rel = path.relative_to(ROOT)
        lines = [f"{rel}:"]
        for err in exc.errors():
            where = ".".join(str(p) for p in err["loc"]) or "<root>"
            lines.append(f"  - {where}: {err['msg']}")
        raise DataError("\n".join(lines)) from exc


# --------------------------------------------------------------------------
# the site context handed to templates
# --------------------------------------------------------------------------


class SiteContext:
    """Validated, fully derived view of the site. Templates only read this."""

    def __init__(self) -> None:
        self.errors: list[str] = []

        self.person: Person = _parse(Person, DATA_DIR / "person.yaml")
        self.site: Site = _parse(Site, DATA_DIR / "site.yaml")
        self.tags: list[Tag] = _parse(list[Tag], DATA_DIR / "tags.yaml")
        self.education: list[Education] = _parse(
            list[Education], DATA_DIR / "education.yaml"
        )
        self.items: list[Item] = self._load_items()
        self.draft_items: list[Item] = []

        self._validate()
        if self.errors:
            raise DataError(
                "your site data has problems:\n\n"
                + "\n".join(f"  {e}" for e in self.errors)
            )

    # -- loading ---------------------------------------------------------

    def _load_items(self) -> list[Item]:
        if not ITEMS_DIR.is_dir():
            raise DataError(f"no items directory at {ITEMS_DIR.relative_to(ROOT)}")

        items: list[Item] = []
        for path in sorted(ITEMS_DIR.glob("*.yaml")):
            item = _parse(Item, path)
            if item.id != path.stem:
                raise DataError(
                    f"{path.relative_to(ROOT)}: id is {item.id!r} but the filename "
                    f"says {path.stem!r}. They must match."
                )
            items.append(item)
        return items

    # -- cross-file rules ------------------------------------------------

    def _validate(self) -> None:
        self._check_unique_ids()
        self._check_tags()
        self._check_featured_order()
        self._check_static_files()
        self._check_orphans()

    def _check_unique_ids(self) -> None:
        for field, values in (
            ("id", [i.id for i in self.items]),
            ("tag id", [t.id for t in self.tags]),
        ):
            for dupes, count in Counter(values).items():
                if count > 1:
                    self.errors.append(f"duplicate {field} {dupes!r} ({count} times)")

    def _check_tags(self) -> None:
        known = {tag.id for tag in self.tags}
        groups = {tag.group for tag in self.tags}
        for tag in self.tags:
            if tag.group not in groups:  # pragma: no cover - trivially true
                self.errors.append(f"tag {tag.id!r} has an unknown group")

        for item in self.items:
            for tag in item.tags:
                if tag not in known:
                    close = _suggest(tag, known)
                    self.errors.append(
                        f"item {item.id!r} uses unknown tag {tag!r}"
                        + (f" - did you mean {close!r}?" if close else "")
                        + f"\n      add it to data/tags.yaml to use it"
                    )

    def _check_featured_order(self) -> None:
        featured = [i for i in self.items if i.featured]
        if not featured:
            self.errors.append(
                "no items are marked `featured: true`, so the home page would have "
                "an empty highlights section"
            )

    def _check_static_files(self) -> None:
        # Who named each path, so one shared by two items is reported once but
        # still names both instead of pointing at whichever came first.
        owners: dict[str, list[tuple[str, str]]] = {}
        for item in self.items:
            for field, path in (("media.image", item.media.image),
                                ("media.poster", item.media.poster)):
                if path:
                    owners.setdefault(path, []).append((item.id, field))

        for ref in sorted(self.static_refs):
            if (STATIC_DIR / ref).is_file():
                continue
            refs_here = owners.get(ref, [])
            if not any(field == "media.poster" for _, field in refs_here):
                self.errors.append(f"referenced file static/{ref} does not exist")
                continue

            who = ", ".join(repr(i) for i, _ in refs_here)
            fields = " and ".join(sorted({f for _, f in refs_here}))
            # An exact stem match is the only near miss worth naming. It is a
            # strong signal - the filename is right and either the extension or
            # the folder is wrong - and it cannot point at the wrong file,
            # which fuzzy matching on short names does readily. This repo makes
            # that worth handling: static/images/info_images/ and
            # static/images/projects/ both hold re3, vince, vsp and splitnet,
            # so the folder is genuinely ambiguous when picking a path.
            # Restricted to images because every paper has a same-named PDF in
            # static/pdfs/, which would otherwise match every single one.
            poster_exts = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"}
            same_name = sorted(
                p
                for p in self._static_paths
                if Path(p).stem == Path(ref).stem
                and Path(p).suffix.lower() in poster_exts
            )
            if len(same_name) == 1:
                hint = f"did you mean static/{same_name[0]}?"
            elif same_name:
                hint = (
                    f"that filename is in {len(same_name)} folders "
                    f"({', '.join('static/' + p for p in same_name)}) - "
                    f"check which one you meant"
                )
            else:
                hint = ""
            subject, verb = ("item", "sets") if len(refs_here) == 1 else ("items", "set")
            self.errors.append(
                f"{subject} {who} {verb} {fields} to static/{ref}, which is not on disk"
                + (f" - {hint}" if hint else "")
                + "\n      a declared poster is not optional: with the file "
                "missing it silently falls back to the gradient artwork on the "
                "item page and renders a broken image in the work list, and "
                "nothing else in the build would notice. CI checks out a clean "
                "tree, so a file you never committed fails the same way there."
            )

    def _check_orphans(self) -> None:
        """A tag nobody uses is dead weight in the filter bar."""
        used = {tag for item in self.items for tag in item.tags}
        for tag in self.tags:
            if tag.id not in used:
                self.errors.append(
                    f"tag {tag.id!r} ({tag.label}) is defined in tags.yaml but not "
                    "used by any item - remove it or tag something with it"
                )

    # -- derived views ---------------------------------------------------

    @cached_property
    def tag_by_id(self) -> dict[str, Tag]:
        return {tag.id: tag for tag in self.tags}

    @cached_property
    def published(self) -> list[Item]:
        return [i for i in self.items if not i.draft]

    @cached_property
    def by_date(self) -> list[Item]:
        """Newest first, ordered by when the entry *finished*.

        Sorting on the start date alone put a four-year role below the papers
        published in its first few months, which reads as though the role barely
        happened. Ranking by the end date puts Third Wave (2020-2024) above the
        papers from 2020, which is the order the reader expects from the dates
        printed on the card.

        Entries with no end date sort on their own date, and a current role
        floats to the top.
        """
        return sorted(self.published, key=self._recency_key, reverse=True)

    def _recency_key(self, item: Item) -> tuple[int, dt.date, str]:
        if item.is_current:
            return (1, dt.date.max, item.id)
        return (0, item.end or item.date, item.id)

    @cached_property
    def featured(self) -> list[Item]:
        """Highlighted items for the home page, newest first.

        Ordered by the same recency rule as the rest of the site, so the dates
        printed on the cards run in the direction they are sorted in. A separate
        `featured_order` used to hand-rank these, which only ever disagreed with
        the dates beside them.

        Any type can be featured: the experience timeline lists every role
        regardless, so a role that is also worth featuring on its own terms
        (a couple of years leading a team, say) can be both without appearing
        twice on the page.
        """
        return sorted(
            (i for i in self.published if i.featured),
            key=lambda i: i.sort_key,
            reverse=True,
        )

    @cached_property
    def positions(self) -> list[Item]:
        """Roles, current one first, then most recently finished."""
        return sorted(
            (i for i in self.published if i.type is ItemType.POSITION),
            key=lambda i: i.sort_key,
            reverse=True,
        )

    def of_type(self, *types: ItemType) -> list[Item]:
        wanted = set(types)
        return [i for i in self.by_date if i.type in wanted]

    @property
    def papers(self) -> list[Item]:
        return self.of_type(ItemType.PAPER)

    @cached_property
    def tag_groups(self) -> list[tuple[str, list[Tag]]]:
        groups: dict[str, list[Tag]] = {}
        for tag in self.tags:
            used = sum(1 for item in self.published if tag.id in item.tags)
            if not used:
                continue
            groups.setdefault(tag.group, []).append(tag)
        order = [g for g in ("Tags", "Focus", "Role") if g in groups]
        order += [g for g in groups if g not in order]
        # Most-used first, then alphabetical. Sorted by label alone, the bar read
        # as arbitrary - "Computer Vision" with 15 entries sat between "Datasets &
        # Benchmarks" with 3 and "Embodied AI" with 10, so the biggest choices
        # were scattered through the list instead of leading it. Count is the
        # useful order for a filter bar; the alphabetical tiebreak keeps it
        # stable when two tags are equally common.
        return [(g, sorted(groups[g], key=lambda t: (-self._tag_use(t), t.label.lower())))
                for g in order]

    def _tag_use(self, tag: Tag) -> int:
        return sum(1 for item in self.published if tag.id in item.tags)

    @cached_property
    def tag_counts(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for item in self.published:
            counts.update(item.tags)
        return dict(counts)

    @property
    def last_updated(self) -> dt.date:
        return max((i.date for i in self.items), default=dt.date.today())

    # -- asset bookkeeping ------------------------------------------------

    @cached_property
    def static_refs(self) -> set[str]:
        """Every file under ``static/`` that the content actually references."""
        refs: set[str] = set()

        refs.add(self.person.photo)
        # Every srcset candidate has to be copied, not just the `src` fallback:
        # a browser picks from the srcset first, so a missing candidate is a
        # broken image even when the `src` file is present.
        for sset in self.person.photo_srcset:
            refs.add(sset.split()[0].lstrip("/"))
        if self.person.cv.href.startswith("/"):
            refs.add(self.person.cv.href.lstrip("/"))
        if self.site.hero_image:
            refs.add(self.site.hero_image)
        for item in self.items:
            if item.media.image:
                refs.add(item.media.image.lstrip("/"))
            if item.media.poster:
                # A declared poster is a hard requirement, so it is referenced
                # unconditionally and `_check_static_files` holds it to
                # existing. Only the derived YouTube still is optional - a
                # video without one still renders, on the gradient fallback.
                refs.add(item.media.poster)
            elif item.media.thumbnail and (
                STATIC_DIR / item.media.thumbnail
            ).is_file():
                refs.add(item.media.thumbnail)
            for link in item.links:
                if link.is_internal and "." in link.href:
                    refs.add(link.href.lstrip("/"))

        return {r for r in refs if not r.startswith("http")}

    @property
    def missing_thumbnails(self) -> list[str]:
        """Videos with neither an explicit ``poster:`` nor a vendored still.

        A video that names its own poster never needs a copy of YouTube's
        frame, so it must not be reported as missing one.
        """
        return [
            item.media.video
            for item in self.items
            if item.media.video
            and not item.media.poster
            and not (STATIC_DIR / item.media.thumbnail).is_file()  # type: ignore[arg-type]
        ]

    @cached_property
    def _static_paths(self) -> set[str]:
        """Every file under ``static/``, relative and posix-style.

        Only used to suggest a fix when a referenced path turns out to be a
        typo, so it deliberately includes files no item references.
        """
        return {
            path.relative_to(STATIC_DIR).as_posix()
            for path in STATIC_DIR.rglob("*")
            if path.is_file() and path.name != ".DS_Store"
        }

    @property
    def unreferenced_static(self) -> list[Path]:
        referenced = {r for r in self.static_refs}
        orphans: list[Path] = []
        for path in sorted(STATIC_DIR.rglob("*")):
            if not path.is_file() or path.name == ".DS_Store":
                continue
            rel = path.relative_to(STATIC_DIR).as_posix()
            if rel.startswith(("fonts/", "favicon/")):
                continue
            if rel not in referenced:
                orphans.append(path)
        return orphans


def _suggest(word: str, options: set[str]) -> str | None:
    import difflib

    matches = difflib.get_close_matches(word, sorted(options), n=1, cutoff=0.7)
    return matches[0] if matches else None
