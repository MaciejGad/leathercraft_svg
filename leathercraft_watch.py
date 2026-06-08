"""
leathercraft_watch — file watcher for .lcraft pattern files.

Monitors a directory (recursively) for changes to .lcraft files and
automatically rebuilds SVG + PNG output whenever a file is saved.

Usage:
    python leathercraft_watch.py [directory]        # watch given dir (default: .)
    python leathercraft_watch.py . --build-all      # also build every file on startup
    python leathercraft_watch.py examples/dsl -i 2  # poll every 2 seconds

Press Ctrl+C to stop.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from leathercraft_dsl import DslError, build_file


# ---------------------------------------------------------------------------
# ANSI colour helpers (disabled automatically on Windows without ANSI support)
# ---------------------------------------------------------------------------

_USE_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def _green(t: str) -> str:   return _c("32", t)
def _red(t: str) -> str:     return _c("31", t)
def _yellow(t: str) -> str:  return _c("33", t)
def _bold(t: str) -> str:    return _c("1",  t)
def _dim(t: str) -> str:     return _c("2",  t)


# ---------------------------------------------------------------------------
# Build helper
# ---------------------------------------------------------------------------


def _build(path: Path) -> bool:
    """Compile one .lcraft file.  Returns True on success, False on error."""
    rel = path.name
    print(f"  {_bold('↺')}  {rel} ", end="", flush=True)
    try:
        build_file(path)
        print(_green("✓"))
        return True
    except DslError as exc:
        print(_red("✗"))
        # Indent each line of the error message for readability
        for line in str(exc).splitlines():
            print(f"     {_red(line)}")
        return False
    except Exception as exc:
        print(_red("✗"))
        print(f"     {_red(f'Unexpected error: {exc}')}")
        return False


# ---------------------------------------------------------------------------
# Watcher
# ---------------------------------------------------------------------------


def _scan(directory: Path) -> dict[Path, float]:
    """Return {path: mtime} for every .lcraft file found under directory."""
    result: dict[Path, float] = {}
    for p in sorted(directory.rglob("*.lcraft")):
        try:
            result[p] = p.stat().st_mtime
        except OSError:
            pass
    return result


def watch(directory: Path, poll_interval: float, build_all: bool) -> None:
    directory = directory.resolve()

    print(_bold(f"leathercraft_watch"))
    print(_dim(f"  Directory : {directory}"))
    print(_dim(f"  Pattern   : **/*.lcraft  (recursive)"))
    print(_dim(f"  Interval  : {poll_interval}s"))
    print()

    # Initial scan
    mtimes = _scan(directory)

    if not mtimes:
        print(_yellow(f"  No .lcraft files found in {directory}"))
    else:
        noun = "file" if len(mtimes) == 1 else "files"
        print(_dim(f"  Found {len(mtimes)} {noun}:"))
        for p in mtimes:
            print(_dim(f"    {p.relative_to(directory)}"))
        print()

    if build_all and mtimes:
        print(_bold("Building all files on startup…"))
        for path in mtimes:
            _build(path)
        print()

    print(_bold("Watching for changes…") + _dim("  (Ctrl+C to stop)"))
    print()

    try:
        while True:
            time.sleep(poll_interval)
            current = _scan(directory)

            # Detect new or modified files
            changed: list[Path] = []
            for path, mtime in current.items():
                if path not in mtimes or mtimes[path] != mtime:
                    changed.append(path)

            # Detect deleted files (report only, no rebuild)
            deleted = [p for p in mtimes if p not in current]
            for path in deleted:
                rel = path.relative_to(directory)
                print(_dim(f"  ✕  {rel} (deleted)"))

            # Update snapshot
            mtimes = current

            # Rebuild changed files
            for path in changed:
                rel = path.relative_to(directory)
                ts = time.strftime("%H:%M:%S")
                print(f"{_dim(ts)}  {_yellow(str(rel))}")
                _build(path)
                print()

    except KeyboardInterrupt:
        print()
        print(_dim("Stopped."))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="leathercraft_watch",
        description="Watch a directory and rebuild .lcraft files on change.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python leathercraft_watch.py .
  python leathercraft_watch.py examples/dsl --build-all
  python leathercraft_watch.py . -i 2
""",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to watch (default: current directory)",
    )
    parser.add_argument(
        "--build-all",
        action="store_true",
        help="Build every .lcraft file found at startup before watching",
    )
    parser.add_argument(
        "-i", "--interval",
        type=float,
        default=0.5,
        metavar="SECONDS",
        help="Polling interval in seconds (default: 0.5)",
    )

    args = parser.parse_args(argv)

    directory = Path(args.directory)
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
        return 1

    watch(directory, poll_interval=args.interval, build_all=args.build_all)
    return 0


if __name__ == "__main__":
    sys.exit(main())
