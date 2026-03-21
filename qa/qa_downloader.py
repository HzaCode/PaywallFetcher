"""
qa_downloader.py -- backward-compatible Q&A download entry point.

Delegates to the paywallfetcher package CLI.
Preferred usage: py -m paywallfetcher qa fetch [flags]

For browser-assisted retrieval of restricted content, use qa_unlock.py
or: py -m paywallfetcher qa browser-fetch
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_CONFIG_FILE = os.path.join(ROOT_DIR, "config.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PaywallFetcher - Q&A Downloader")
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE, help="Path to config file")
    parser.add_argument("--list-only", action="store_true", help="List Q&A without downloading")
    parser.add_argument("--new-only", action="store_true", help="Incremental mode")
    parser.add_argument("--start", type=int, default=1, help="Start from Nth item")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    return parser


def main(argv: list = None) -> int:
    args = build_parser().parse_args(argv)

    src_dir = os.path.join(ROOT_DIR, "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    from paywallfetcher.cli import run

    cli_args = ["--config", args.config]
    if args.json:
        cli_args.append("--json")

    if args.list_only:
        cli_args += ["qa", "list"]
    else:
        cli_args += ["qa", "fetch"]
        if args.new_only:
            cli_args.append("--new-only")
        if args.start != 1:
            cli_args += ["--start", str(args.start)]

    return run(cli_args)


if __name__ == "__main__":
    raise SystemExit(main())
