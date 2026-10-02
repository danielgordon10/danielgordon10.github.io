"""Command line entry point: ``uv run site <command>``."""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import sys
import threading
import webbrowser
from pathlib import Path

from .build import ROOT, build, tree_size
from .data import DataError
from .render import file_size

BOLD, DIM, RED, GREEN, YELLOW, RESET = (
    "\033[1m",
    "\033[2m",
    "\033[31m",
    "\033[32m",
    "\033[33m",
    "\033[0m",
)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def cmd_build(args: argparse.Namespace) -> int:
    out = Path(args.out).resolve() if args.out else ROOT / "dist"
    result = build(
        out_dir=out,
        force_ts=args.force,
        include_unreferenced=args.all_assets,
    )
    files, size = tree_size(out)
    print(f"{GREEN}built{RESET} {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    print(f"  {_plural(result.pages, 'file')} written, {_plural(files, 'file')} total, {file_size(size)}")
    print(f"  finished in {result.seconds:.2f}s")
    print(f"\n{DIM}preview with:  uv run site serve{RESET}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    from .data import STATIC_DIR, SiteContext

    ctx = SiteContext()
    print(f"{GREEN}ok{RESET} {len(ctx.published)} items, {len(ctx.tags)} tags, "
          f"{len(ctx.education)} education entries")
    print(f"  {len(ctx.static_refs)} static files referenced")
    if ctx.unreferenced_static:
        total = sum(p.stat().st_size for p in ctx.unreferenced_static)
        print(f"\n{YELLOW}note{RESET} {len(ctx.unreferenced_static)} files in static/ are "
              f"not referenced by any item ({file_size(total)}):")
        for path in ctx.unreferenced_static[:12]:
            print(f"    static/{path.relative_to(STATIC_DIR)}")
        if len(ctx.unreferenced_static) > 12:
            print(f"    ... and {len(ctx.unreferenced_static) - 12} more")
    if ctx.missing_thumbnails:
        print(f"\n{YELLOW}note{RESET} no poster still vendored for "
              f"{len(ctx.missing_thumbnails)} video(s); they use the gradient fallback:")
        for video_id in ctx.missing_thumbnails:
            print(f"    static/images/video/{video_id}.jpg  <- i.ytimg.com/vi/{video_id}/maxresdefault.jpg")

    # The CV lives twice: cv.pdf in the repository root is the one you edit and
    # replace, static/cv.pdf is the one the build serves. Nothing in the build
    # reads the root copy, so dropping a new version there and rebuilding left
    # the old PDF live with no error anywhere. This is an error rather than a
    # note: shipping a CV you did not mean to publish is worse than a failed
    # check.
    root_cv = ROOT / "cv.pdf"
    served_cv = STATIC_DIR / "cv.pdf"
    if root_cv.is_file() and served_cv.is_file():
        if root_cv.read_bytes() != served_cv.read_bytes():
            print(f"\n{RED}error{RESET} cv.pdf differs from static/cv.pdf.")
            print(f"  {file_size(root_cv.stat().st_size)} cv.pdf (root, the one you edit)")
            print(f"  {file_size(served_cv.stat().st_size)} static/cv.pdf (the one that is served)")
            print("  run: cp cv.pdf static/cv.pdf")
            return 1
    elif root_cv.is_file() and not served_cv.is_file():
        print(f"\n{RED}error{RESET} cv.pdf exists but static/cv.pdf does not.")
        print("  run: cp cv.pdf static/cv.pdf")
        return 1

    return 0


class _Handler(http.server.SimpleHTTPRequestHandler):
    """Serves a directory with caching turned off so a rebuild shows up on refresh.

    ``directory`` is bound with ``functools.partial`` below rather than set here:
    ``SimpleHTTPRequestHandler.__init__`` defaults ``directory`` to ``os.getcwd()``,
    so a class attribute would be silently overwritten and the server would end up
    publishing whatever shell the command was launched from.
    """

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:  # type: ignore[no-untyped-def]
        sys.stderr.write(f"  {DIM}{fmt % args}{RESET}\n")


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def cmd_serve(args: argparse.Namespace) -> int:
    out = ROOT / "dist"
    if not (out / "index.html").exists():
        build(out_dir=out)

    handler = functools.partial(_Handler, directory=str(out))

    port = args.port
    for _ in range(20):
        try:
            httpd = _Server(("127.0.0.1", port), handler)
            break
        except OSError:
            port += 1
    else:  # pragma: no cover
        print(f"{RED}could not find a free port{RESET}", file=sys.stderr)
        return 1

    url = f"http://127.0.0.1:{port}/"
    print(f"{GREEN}serving{RESET} {out.relative_to(ROOT)} at {BOLD}{url}{RESET}")
    print(f"{DIM}  routes:  {url}  |  {url}work/  |  {url}about/{RESET}")
    print(f"{DIM}  ctrl-c to stop{RESET}\n")

    if args.open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="site",
        description="Generate the personal website from data/ and templates/.",
    )
    sub = parser.add_subparsers(dest="command")

    build_cmd = sub.add_parser("build", help="generate the site into dist/")
    build_cmd.add_argument("--out", help="output directory (default: dist/)")
    build_cmd.add_argument(
        "--force", action="store_true", help="recompile the TypeScript client"
    )
    build_cmd.add_argument(
        "--all-assets",
        action="store_true",
        help="also copy files in static/ that nothing references",
    )
    build_cmd.set_defaults(func=cmd_build)

    check_cmd = sub.add_parser(
        "check", help="validate the data without writing any files"
    )
    check_cmd.set_defaults(func=cmd_check)

    serve_cmd = sub.add_parser("serve", help="build, then serve dist/ locally")
    serve_cmd.add_argument("--port", type=int, default=8000)
    serve_cmd.add_argument("--open", action="store_true", help="open a browser")
    serve_cmd.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        args = parser.parse_args((argv or []) + ["build"])

    try:
        return args.func(args)
    except DataError as exc:
        print(f"{RED}data error{RESET}\n\n{exc}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
