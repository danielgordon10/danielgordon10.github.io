"""Pydantic schemas for every piece of site content.

Design rules enforced here:

* ``extra="forbid"`` everywhere, so a typo'd key in YAML is a hard build
  error instead of silently disappearing content.
* Nothing is duplicated. A title is written once; the URL, the badge text and
  the "me" highlighting in author lists are all derived.
* Cross-file rules (unique ids, known tags, unique feature ordering) live in
  :mod:`sitegen.data` because they need more than one file to evaluate.
"""

from __future__ import annotations

import datetime as dt
import re
from enum import StrEnum
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .format import date_range

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
YOUTUBE_RE = re.compile(r"(?:youtu\.be/|youtube\.com/(?:embed/|watch\?v=|v/))([A-Za-z0-9_-]{11})")
TAG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _looks_like_html(value: str) -> bool:
    return bool(re.search(r"<[a-zA-Z/!]", value))


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --------------------------------------------------------------------------
# content model
# --------------------------------------------------------------------------


class ItemType(StrEnum):
    PAPER = "paper"
    PROJECT = "project"
    POSITION = "position"
    COURSE = "course"
    TALK = "talk"
    DATASET = "dataset"
    DEMO = "demo"


class TypeMeta(BaseModel):
    """Presentation metadata for an item type. Not user authored."""

    label: str
    icon: str
    #: short badge text used on cards, e.g. "CVPR 2018"
    badge_prefix: str = ""


TYPE_META: dict[ItemType, TypeMeta] = {
    ItemType.PAPER: TypeMeta(label="Paper", icon="document"),
    ItemType.PROJECT: TypeMeta(label="Project", icon="cube"),
    ItemType.POSITION: TypeMeta(label="Role", icon="building"),
    ItemType.COURSE: TypeMeta(label="Course", icon="academic"),
    ItemType.TALK: TypeMeta(label="Talk", icon="microphone"),
    ItemType.DATASET: TypeMeta(label="Dataset", icon="database"),
    ItemType.DEMO: TypeMeta(label="Demo", icon="play"),
}

PUBLICATION_TYPES = {ItemType.PAPER, ItemType.DATASET}


class LinkKind(StrEnum):
    """Picks the button icon. Every link declares one.

    There is no default and no catch-all member. `other` existed as the default
    for links that did not declare a kind, but every link in the data does
    declare one, so the default only ever masked a forgotten field behind a
    generic chain-link icon. Requiring it turns that omission into a build error.
    """

    PAPER = "paper"
    CODE = "code"
    DEMO = "demo"
    PROJECT = "project"
    COURSE = "course"


class Note(Strict):
    """One labelled external resource rendered as a list row.

    `links` are the big buttons under a title - Paper, Code, Demo - and a page
    with thirteen of them stops being a page. A course's lecture notes are the
    opposite case: many small, same-weight destinations that belong in a list.
    """

    title: str
    href: str

    @field_validator("href")
    @classmethod
    def _href_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("note href cannot be empty")
        return v


class Link(Strict):
    label: str
    href: str
    kind: LinkKind
    primary: bool = False

    @field_validator("href")
    @classmethod
    def _href_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("link href cannot be empty")
        if v.startswith("#") or v.lower() == "javascript:":
            raise ValueError(f"unsupported href {v!r}")
        return v

    @property
    def is_internal(self) -> bool:
        return self.href.startswith("/")


class GalleryImage(Strict):
    src: str
    alt: str
    caption: str | None = None

    @field_validator("src")
    @classmethod
    def _src_relative(cls, v: str) -> str:
        if v.startswith(("http://", "https://", "//")):
            raise ValueError("gallery images must be local files under static/")
        return v.lstrip("/")


class Media(Strict):
    video: str | None = None
    image: str | None = None
    alt: str | None = None
    gallery: list[GalleryImage] = Field(default_factory=list)

    @field_validator("video")
    @classmethod
    def _video_id(cls, v: str | None) -> str | None:
        """Accept a bare YouTube id or any watch/embed URL; store the id."""
        if v is None or not v.strip():
            return None
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", v):
            return v
        match = YOUTUBE_RE.search(v)
        if not match:
            raise ValueError(
                f"{v!r} is not a YouTube id or URL (expected an 11-character id "
                "such as 'dQw4w9WgXcQ', or a full youtube.com/watch?v=... link)"
            )
        return match.group(1)

    @property
    def has_any(self) -> bool:
        return bool(self.video or self.image or self.gallery)

    @property
    def thumbnail(self) -> str | None:
        """Poster frame for :attr:`video`, as a path under ``static/``.

        The stills are vendored into ``static/images/video/<id>.jpg`` rather
        than hot-linked from ``i.ytimg.com``. Linking YouTube's thumbnails
        would mean a third-party request on page load, which is exactly what
        the click-to-play facade exists to avoid - and a crawler or an
        ad-blocker can block it, leaving a blank frame. Copying them keeps the
        no-third-party-request property and makes the previews reliable.

        Returns ``None`` when no still has been vendored for this id, in which
        case the template falls back to the abstract gradient poster.
        """
        return f"images/video/{self.video}.jpg" if self.video else None


class Item(Strict):
    """One entry in ``data/items/``.

    The filename must equal ``id``; the URL is derived from the id so it can
    never drift out of sync with the file it lives in.
    """

    id: str
    type: ItemType
    title: str
    date: dt.date
    end: dt.date | None = None
    tags: list[str] = Field(default_factory=list)
    # One sentence written for the row on a list page. The abstract is the
    # paper's own abstract: too long for a row and not written for a reader
    # skimming a list, so it was being truncated mid-sentence.
    summary: str | None = None
    abstract: str | None = None
    venue: str | None = None
    venue_short: str | None = None
    role: str | None = None
    org: str | None = None
    authors: list[str] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    media: Media = Field(default_factory=Media)
    bibtex: str | None = None
    # Semantic Scholar's 40-hex paper id, e.g. the one in
    # /paper/IQA-...-in-Interactive-Gordon-Kembhavi/<id>. Stored as the bare id
    # rather than a URL because the site rewrites every internal path through
    # `link()` and these go out untouched; keeping the id means the template
    # builds the one URL shape in one place.
    semantic_scholar: str | None = None
    instructor: str | None = None
    # People who worked on it with you but are not co-authors: co-TAs on a
    # course, collaborators on a dataset. `authors` is the byline, and it is
    # what feeds citation metadata and the equal-contribution marks, so a TA
    # list does not belong there.
    collaborators: list[str] = Field(default_factory=list)
    notes: list[Note] = Field(default_factory=list)
    featured: bool = False
    draft: bool = False

    @field_validator("id")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not SLUG_RE.match(v):
            raise ValueError(
                f"{v!r} is not a valid slug - use lowercase words joined by hyphens"
            )
        return v

    @field_validator("tags")
    @classmethod
    def _tag_slugs(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        for tag in v:
            if not TAG_RE.match(tag):
                raise ValueError(f"tag {tag!r} must be lowercase-hyphenated")
            if tag in seen:
                raise ValueError(f"tag {tag!r} listed twice")
            seen.add(tag)
        return v

    @field_validator("semantic_scholar")
    @classmethod
    def _paper_id(cls, v: str | None) -> str | None:
        if v is not None and not re.fullmatch(r"[0-9a-f]{40}", v):
            raise ValueError(
                f"{v!r} is not a Semantic Scholar paper id - it is 40 hex "
                "characters, the last path segment of the paper's /paper/ URL"
            )
        return v

    @field_validator("title", "venue", "venue_short", "role", "org")
    @classmethod
    def _no_html(cls, v: str | None) -> str | None:
        if v and _looks_like_html(v):
            raise ValueError(
                f"{v!r} contains HTML - these fields are plain text. "
                "Formatting belongs in `abstract`, which is Markdown."
            )
        return v

    @field_validator("date")
    @classmethod
    def _no_future(cls, v: dt.date) -> dt.date:
        if v > dt.date.today() + dt.timedelta(days=31):
            raise ValueError(f"date {v} is more than a month in the future")
        return v

    @model_validator(mode="after")
    def _end_after_start(self) -> Item:
        if self.end is not None and self.end < self.date:
            raise ValueError(
                f"item {self.id!r} ends ({self.end}) before it starts ({self.date})"
            )
        return self

    @model_validator(mode="after")
    def _type_requirements(self) -> Item:
        if self.type in PUBLICATION_TYPES and not self.authors:
            raise ValueError(f"{self.type} {self.id!r} needs an `authors` list")
        if self.type is ItemType.POSITION:
            if not self.org:
                raise ValueError(f"position {self.id!r} needs an `org`")
            if not self.role:
                raise ValueError(f"position {self.id!r} needs a `role`")
        if not (self.summary or self.abstract or self.media.has_any):
            raise ValueError(
                f"item {self.id!r} has no `summary`, no `abstract` and no media, so "
                "its page would be empty"
            )
        if sum(1 for link in self.links if link.primary) > 1:
            raise ValueError(f"item {self.id!r} has more than one `primary: true` link")
        return self

    @property
    def meta(self) -> TypeMeta:
        return TYPE_META[self.type]

    @property
    def is_current(self) -> bool:
        """A role with no end date, i.e. the thing I am doing now."""
        return self.type is ItemType.POSITION and self.end is None

    @property
    def date_label(self) -> str:
        return date_range(self.date, self.end, current=self.is_current)

    @property
    def sort_key(self) -> tuple[int, dt.date, str]:
        """Order roles so the current one sorts first, then by recency."""
        if self.is_current:
            return (1, dt.date.max, self.id)
        return (0, self.end or self.date, self.id)

    @property
    def url(self) -> str:
        return f"/work/{self.id}/"

    @property
    def output_path(self) -> PurePosixPath:
        return PurePosixPath("work", self.id, "index.html")

    @property
    def badge(self) -> str:
        """Short label for a card: prefers the abbreviation, e.g. 'CVPR 2020'."""
        return self.venue_short or self.venue or ""

    @property
    def is_publication(self) -> bool:
        return self.type in PUBLICATION_TYPES

    @property
    def type_badge_url(self) -> str:
        """Where the type badge goes.

        The work index has no type filter, so there is nothing to select for
        'Course' or 'Talk'. Papers all carry the `paper` tag, so that one links
        to a real filtered view and the rest fall back to the plain index rather
        than to a filter that does not exist.
        """
        if "paper" in self.tags:
            return "/work/?tags=paper"
        return "/work/"

    @property
    def semantic_scholar_url(self) -> str | None:
        """The item's own Semantic Scholar paper page, or nothing.

        Was a title-search URL for both Scholar sites. Search dropped the visitor
        on a results page they then had to pick the right paper from, and the
        results are ordered by relevance, so a same-titled paper by another group
        could sit above yours. A stored id is always this paper's own page.
        """
        if not self.semantic_scholar:
            return None
        return f"https://www.semanticscholar.org/paper/{self.semantic_scholar}"


# --------------------------------------------------------------------------
# tags
# --------------------------------------------------------------------------


class Tag(Strict):
    id: str
    label: str
    group: str = "Tags"

    @field_validator("id")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not TAG_RE.match(v):
            raise ValueError(f"tag id {v!r} must be lowercase-hyphenated")
        return v


# --------------------------------------------------------------------------
# person / site configuration
# --------------------------------------------------------------------------


class Social(Strict):
    label: str
    href: str
    icon: str
    handle: str | None = None

    @field_validator("href")
    @classmethod
    def _http(cls, v: str) -> str:
        if v.startswith("mailto:"):
            return v
        if not v.startswith(("https://", "http://")):
            raise ValueError(f"social href {v!r} must be an absolute http(s) URL")
        return v

    @property
    def is_email(self) -> bool:
        return self.href.startswith("mailto:")


class Cv(Strict):
    label: str = "Curriculum Vitae"
    href: str = "/cv.pdf"
    #: small badge shown next to the button, e.g. "PDF, updated Nov 2025"
    note: str | None = None


class Person(Strict):
    name: str
    role: str
    org: str
    team: str | None = None
    location: str | None = None
    email: str
    intro: str
    about: list[str] = Field(default_factory=list)
    photo: str
    # Width-descriptor pairs ("path/to.jpg 1024w"), smallest first. Optional:
    # a site with one portrait size does not need a srcset.
    photo_srcset: list[str] = Field(default_factory=list)
    photo_alt: str = "Portrait of {name}"
    socials: list[Social] = Field(default_factory=list)
    cv: Cv = Field(default_factory=Cv)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        if not EMAIL_RE.match(v):
            raise ValueError(f"{v!r} is not a valid email address")
        return v

    @field_validator("photo_srcset")
    @classmethod
    def _srcset_shape(cls, v: list[str]) -> list[str]:
        for cand in v:
            parts = cand.split()
            if len(parts) != 2 or not parts[1].endswith("w") or not parts[1][:-1].isdigit():
                raise ValueError(
                    f"{cand!r} must be '<path> <width>w', e.g. 'images/me.jpg 1024w'"
                )
            if not parts[1][:-1].isdigit() or int(parts[1][:-1]) <= 0:
                raise ValueError(f"{cand!r} has a non-positive width descriptor")
        if v and len(v) > 1:
            widths = [int(c.split()[1][:-1]) for c in v]
            if widths != sorted(widths):
                raise ValueError("photo_srcset must be ordered smallest first")
        return v

    @field_validator("photo")
    @classmethod
    def _photo_relative(cls, v: str) -> str:
        if v.startswith(("http://", "https://", "//")):
            raise ValueError("photo must be a local file under static/")
        return v.lstrip("/")

    @field_validator("intro", "role", "org")
    @classmethod
    def _markdown_ok(cls, v: str) -> str:
        if v and _looks_like_html(v):
            raise ValueError(
                f"{v!r} contains HTML - use Markdown instead (e.g. [text](url))"
            )
        return v

    @property
    def first_name(self) -> str:
        return self.name.split()[0]

    @property
    def current_role_line(self) -> str:
        return f"{self.role} at {self.org}" + (f", {self.team}" if self.team else "")

    @property
    def photo_alt_text(self) -> str:
        return self.photo_alt.format(name=self.name)

    @property
    def me_key(self) -> str:
        """Normalised form of my own name, for matching against author lists."""
        return _normalise(self.name)

    def is_me(self, author: str) -> bool:
        return _normalise(author) == self.me_key


def _normalise(name: str) -> str:
    """Case- and punctuation-insensitive form, so 'O'Neil-Dunne' == 'o neil dunne'."""
    return re.sub(r"[^a-z]", "", name.lower())


class NavItem(Strict):
    label: str
    href: str
    #: shown as the active pill on the matching page
    key: str | None = None


class Analytics(Strict):
    """Free, self-hosted-friendly analytics. Left empty unless you want stats."""

    provider: str  # e.g. "plausible"
    domain: str
    script_url: str


class Site(Strict):
    title: str
    description: str
    url: str = "https://danielgordon10.github.io"
    locale: str = "en_US"
    theme_color: str = "#0b1120"
    hero_image: str | None = None
    nav: list[NavItem] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    analytics: Analytics | None = None
    #: where the CV lives relative to the site root
    default_theme: str = "dark"
    #: "system" follows the visitor's OS; "fixed" always uses default_theme
    theme_policy: str = "system"

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("default_theme")
    @classmethod
    def _theme(cls, v: str) -> str:
        if v not in {"dark", "light"}:
            raise ValueError("default_theme must be 'dark' or 'light'")
        return v

    @field_validator("theme_policy")
    @classmethod
    def _theme_policy(cls, v: str) -> str:
        if v not in {"system", "fixed"}:
            raise ValueError("theme_policy must be 'system' or 'fixed'")
        return v
