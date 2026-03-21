"""
qa_unlock.py -- backward-compatible browser-assisted Q&A retrieval entry point.

Delegates to the paywallfetcher package CLI.
Preferred usage: py -m paywallfetcher qa browser-fetch [flags]

Only retrieves content the logged-in user is already authorized to access.
Requires: py -m playwright install chromium
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_CONFIG_FILE = os.path.join(ROOT_DIR, "config.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PaywallFetcher - Browser-assisted Q&A retrieval"
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE, help="Path to config file")
    parser.add_argument("--batch-size", type=int, default=5, help="Parallel batch size")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--no-screenshots", action="store_true", help="Disable failure screenshots")
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

    cli_args += ["qa", "browser-fetch", "--batch-size", str(args.batch_size)]
    if args.headless:
        cli_args.append("--headless")
    if args.no_screenshots:
        cli_args.append("--no-screenshots")

    return run(cli_args)


if __name__ == "__main__":
    raise SystemExit(main())
