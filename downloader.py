"""
downloader.py — backward-compatible article download entry point.

Delegates to the paywallfetcher package CLI.
Preferred usage: py -m paywallfetcher article fetch [flags]

Flags supported here mirror the new CLI for drop-in compatibility.
"""

from __future__ import annotations

import argparse
import os
import sys

DEFAULT_CONFIG_FILE = "config.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PaywallFetcher - Article Downloader")
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE, help="Path to config file")
    parser.add_argument("--list-only", action="store_true", help="List articles without downloading")
    parser.add_argument("--new-only", action="store_true", help="Incremental mode")
    parser.add_argument("--start", type=int, default=1, help="Start from Nth article")
    parser.add_argument("--no-images", action="store_true", help="Skip image downloads")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    return parser


def main(argv: list = None) -> int:
    args = build_parser().parse_args(argv)

    src_dir = os.path.join(os.path.dirname(__file__), "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    from paywallfetcher.cli import run

    cli_args = ["--config", args.config]
    if args.json:
        cli_args.append("--json")

    if args.list_only:
        cli_args += ["article", "list"]
    else:
        cli_args += ["article", "fetch"]
        if args.new_only:
            cli_args.append("--new-only")
        if args.start != 1:
            cli_args += ["--start", str(args.start)]
        if args.no_images:
            cli_args.append("--no-images")

    return run(cli_args)


if __name__ == "__main__":
    raise SystemExit(main())
