"""Fetch the two self-hosted variable fonts used by the site.

Run once (or after changing FAMILIES) with `uv run python tools/fetch_fonts.py`.
The downloaded woff2 files are committed, so the site itself never talks to
Google - no third-party requests, no FOIT, works offline and under a strict
privacy policy.
"""

from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "static" / "fonts"
CSS_PATH = OUT_DIR / "fonts.css"

# Modern-Chrome UA: makes the Google Fonts API serve woff2 + variable ranges.
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

#: (css2 query, [(filename, style)], only the `latin` subset is downloaded)
FAMILIES = [
    (
        "Inter:wght@100..900",
        [("inter-latin-var.woff2", "normal")],
        "Inter",
    ),
    (
        "Newsreader:ital,opsz,wght@0,6..72,200..800;1,6..72,200..800",
        [
            ("newsreader-latin-var.woff2", "normal"),
            ("newsreader-latin-var-italic.woff2", "italic"),
        ],
        "Newsreader",
    ),
]

#: unicode-range for the `latin` subset
LATIN_RANGE = (
    "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, "
    "U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, "
    "U+2212, U+2215, U+FEFF, U+FFFD"
)


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def latin_url(css: str) -> str:
    """The woff2 URL for the last @font-face block, which is the latin subset."""
    urls = re.findall(r"url\((https://[^)]+\.woff2)\)", css)
    if not urls:
        raise SystemExit("no woff2 URLs in the Google Fonts response")
    return urls[-1]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rules: list[str] = [
        "/* Self-hosted variable fonts. Regenerate with tools/fetch_fonts.py. */",
        "",
    ]

    for query, files, family in FAMILIES:
        css = fetch(f"https://fonts.googleapis.com/css2?family={query}&display=swap").decode()
        url = latin_url(css)
        weight_match = re.search(r"font-weight:\s*([\d ]+);", css)
        weight = " ".join(weight_match.group(1).split()) if weight_match else "400"
        print(f"  {family}: {url}")
        for filename, style in files:
            target = OUT_DIR / filename
            if not target.exists() or "--force" in sys.argv:
                target.write_bytes(fetch(url))
            size_kb = target.stat().st_size / 1024
            print(f"    saved {filename} ({size_kb:.0f} KB)")
            rules += [
                "@font-face {",
                f"  font-family: '{family}';",
                "  font-style: " + style + ";",
                f"  font-weight: {weight};",
                "  font-display: swap;",
                f"  src: url('./{filename}') format('woff2');",
                f"  unicode-range: {LATIN_RANGE};",
                "}",
                "",
            ]

    CSS_PATH.write_text("\n".join(rules), encoding="utf-8")
    print(f"\nwrote {CSS_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
