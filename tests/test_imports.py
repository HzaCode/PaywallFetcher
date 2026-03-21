"""Smoke tests: verify all modules import cleanly and entry points compile."""

import importlib
import py_compile
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_entry_points_compile():
    for script in ["downloader.py", "qa/qa_downloader.py", "qa/qa_unlock.py"]:
        py_compile.compile(str(ROOT / script), doraise=True)


def test_package_imports():
    for mod in [
        "paywallfetcher",
        "paywallfetcher.errors",
        "paywallfetcher.config",
        "paywallfetcher.state",
        "paywallfetcher.auth",
        "paywallfetcher.output",
        "paywallfetcher.articles",
        "paywallfetcher.qa",
        "paywallfetcher.cli",
        "paywallfetcher.sites.base",
        "paywallfetcher.sites.generic",
    ]:
        importlib.import_module(mod)


def test_cli_help_exits_zero():
    from paywallfetcher.cli import run
    with pytest.raises(SystemExit) as exc:
        run(["--help"])
    assert exc.value.code == 0
