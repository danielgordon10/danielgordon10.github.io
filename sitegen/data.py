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
        for ref in sorted(self.static_refs):
            if not (STATIC_DIR / ref).is_file():
                self.errors.append(
                    f"referenced file static/{ref} does not exist"
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
            thumb = item.media.thumbnail
            # Only reference the poster still if it was actually vendored; a
            # video without one still renders, on the gradient fallback.
            if thumb and (STATIC_DIR / thumb).is_file():
                refs.add(thumb)
            for image in item.media.gallery:
                refs.add(image.src.lstrip("/"))
            for link in item.links:
                if link.is_internal and "." in link.href:
                    refs.add(link.href.lstrip("/"))

        return {r for r in refs if not r.startswith("http")}

    @property
    def missing_thumbnails(self) -> list[str]:
        """Video ids with no vendored poster still under ``static/images/video``."""
        return [
            item.media.video
            for item in self.items
            if item.media.video
            and not (STATIC_DIR / item.media.thumbnail).is_file()  # type: ignore[arg-type]
        ]

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
