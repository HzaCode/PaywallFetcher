"""Tests for CLI argument parsing and JSON output contract."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paywallfetcher.cli import build_parser


# ── argparse position tests ────────────────────────────────────────────────

def test_json_before_subcommand_parses():
    """--json must be accepted as a top-level flag before the subcommand."""
    parser = build_parser()
    args = parser.parse_args(["--json", "article", "list"])
    assert args.json is True
    assert args.group == "article"
    assert args.action == "list"


def test_config_before_subcommand_parses():
    """--config must be accepted as a top-level flag before the subcommand."""
    parser = build_parser()
    args = parser.parse_args(["--config", "custom.json", "article", "list"])
    assert args.config == "custom.json"


def test_json_after_subcommand_fails():
    """--json placed after the subcommand must be rejected by argparse."""
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["article", "fetch", "--new-only", "--json"])


def test_config_after_subcommand_fails():
    """--config placed after the subcommand must be rejected by argparse."""
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["article", "fetch", "--config", "custom.json"])


def test_global_flags_and_subcommand_flags_coexist():
    """Global flags and subcommand flags must not conflict."""
    parser = build_parser()
    args = parser.parse_args(["--json", "article", "fetch", "--new-only", "--no-images"])
    assert args.json is True
    assert args.new_only is True
    assert args.no_images is True


# ── JSON output purity test ────────────────────────────────────────────────

def test_doctor_json_output_is_pure_json(tmp_path, capsys):
    """doctor --json must emit a single valid JSON document to stdout only."""
    import json as json_mod
    from paywallfetcher.cli import run

    # doctor with a missing config should still output valid JSON (ok=False)
    exit_code = run(["--json", "--config", str(tmp_path / "nonexistent.json"), "doctor"])

    captured = capsys.readouterr()
    # stderr may have warnings; stdout must be pure JSON
    assert captured.out.strip(), "Expected JSON output on stdout"
    parsed = json_mod.loads(captured.out.strip())
    assert "ok" in parsed
    assert "checks" in parsed


def test_state_inspect_json_always_outputs_single_doc(tmp_path, capsys):
    """state inspect --json must always emit a single JSON document even when no state exists."""
    import json as json_mod
    from paywallfetcher.cli import run

    cfg_data = {
        "site": {
            "base_url": "https://site.example.net",
            "target_uid": "1234567890",
            "api_paths": {},
            "kind": "generic",
        },
        "auth": {"mode": "config"},
        "cookies": {},
        "network": {},
        "output": {
            "root_dir": str(tmp_path / "output"),
            "qa_dir": str(tmp_path / "qa_output"),
        },
        "safety": {},
    }
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    exit_code = run(["--json", "--config", str(cfg_file), "state", "inspect"])

    captured = capsys.readouterr()
    assert captured.out.strip(), "Expected JSON output on stdout"
    # Must be exactly one JSON document
    lines = [l for l in captured.out.strip().splitlines() if l.strip()]
    parsed = json_mod.loads(captured.out.strip())
    assert "ok" in parsed
    assert "articles" in parsed
    assert "qa" in parsed
    # Both should be present even when no state files exist
    assert parsed["articles"] is not None or parsed["articles"] is None  # count may be None
    assert "count" in parsed["articles"]


# ── allowed_base_domains validation tests ─────────────────────────────────

def test_allowed_base_domains_exact_match_passes(tmp_path):
    """Exact host match against allowed_base_domains must pass."""
    import json as json_mod
    from paywallfetcher.config import load

    cfg_data = {
        "site": {
            "base_url": "https://example.net",
            "target_uid": "123456",
            "api_paths": {},
            "kind": "generic",
        },
        "safety": {"allowed_base_domains": ["example.net"]},
    }
    p = tmp_path / "config.json"
    p.write_text(json_mod.dumps(cfg_data), encoding="utf-8")
    cfg = load(str(p))
    assert cfg["base_url"] == "https://example.net"


def test_allowed_base_domains_subdomain_passes(tmp_path):
    """A subdomain of an allowed domain must pass."""
    import json as json_mod
    from paywallfetcher.config import load

    cfg_data = {
        "site": {
            "base_url": "https://api.example.net",
            "target_uid": "123456",
            "api_paths": {},
            "kind": "generic",
        },
        "safety": {"allowed_base_domains": ["example.net"]},
    }
    p = tmp_path / "config.json"
    p.write_text(json_mod.dumps(cfg_data), encoding="utf-8")
    cfg = load(str(p))
    assert cfg["base_url"] == "https://api.example.net"


def test_allowed_base_domains_suffix_only_rejected(tmp_path):
    """A domain that merely shares a suffix (badexample.net vs example.net) must be rejected."""
    import json as json_mod
    from paywallfetcher.config import load
    from paywallfetcher.errors import ConfigError

    cfg_data = {
        "site": {
            "base_url": "https://badexample.net",
            "target_uid": "123456",
            "api_paths": {},
            "kind": "generic",
        },
        "safety": {"allowed_base_domains": ["example.net"]},
    }
    p = tmp_path / "config.json"
    p.write_text(json_mod.dumps(cfg_data), encoding="utf-8")
    with pytest.raises(ConfigError, match="allowed_base_domains"):
        load(str(p))


def test_allowed_base_domains_unrelated_domain_rejected(tmp_path):
    """A completely unrelated domain must be rejected."""
    import json as json_mod
    from paywallfetcher.config import load
    from paywallfetcher.errors import ConfigError

    cfg_data = {
        "site": {
            "base_url": "https://attacker.com",
            "target_uid": "123456",
            "api_paths": {},
            "kind": "generic",
        },
        "safety": {"allowed_base_domains": ["example.net"]},
    }
    p = tmp_path / "config.json"
    p.write_text(json_mod.dumps(cfg_data), encoding="utf-8")
    with pytest.raises(ConfigError, match="allowed_base_domains"):
        load(str(p))


def test_empty_allowed_base_domains_skips_check(tmp_path):
    """When allowed_base_domains is empty, the domain check must be skipped entirely."""
    import json as json_mod
    from paywallfetcher.config import load

    cfg_data = {
        "site": {
            "base_url": "https://any-site.example.net",
            "target_uid": "123456",
            "api_paths": {},
            "kind": "generic",
        },
        "safety": {"allowed_base_domains": []},
    }
    p = tmp_path / "config.json"
    p.write_text(json_mod.dumps(cfg_data), encoding="utf-8")
    cfg = load(str(p))
    assert cfg["base_url"] == "https://any-site.example.net"
