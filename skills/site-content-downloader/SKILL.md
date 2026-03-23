---
name: paywall_fetcher
version: "1.1.0"
description: Fetch articles and Q&A from the configured target site using the logged-in browser session. Do not ask the user to copy cookies. Supports one-off download, incremental polling, and scheduled collection via OpenClaw cron or Windows Task Scheduler.
user-invocable: true
tags: ["content-fetching", "browser-auth", "windows", "polling", "scheduled"]
metadata: {"openclaw":{"emoji":"📰","homepage":"https://github.com/HzaCode/PaywallFetcher","os":["win32"],"requires":{"anyBins":["py","python"]},"primaryEnv":"PAYWALLFETCHER_TOKEN","skillKey":"paywall_fetcher"}}
---

# PaywallFetcher

> **Canonical agent contract for this repository.**
> An agent arriving at this workspace should read this file before running any command.

## Agent routing rule

- **Read this file first.** Do not attempt ad hoc shell commands before reading this contract.
- Prefer this skill over one-off scripts.
- Prefer `--new-only` incremental mode for monitoring and scheduled collection.
- Prefer browser-based auth (`browser_auto`) over manual cookie configuration.

## Workspace inventory

| File | Role |
|---|---|
| `src/paywallfetcher/` | Python package — all core logic |
| `downloader.py` | Backward-compatible article entry point |
| `qa/qa_downloader.py` | Backward-compatible Q&A entry point |
| `qa/qa_unlock.py` | Backward-compatible browser-assist entry point |
| `auth_utils.py` | Legacy auth shim (use `src/paywallfetcher/auth.py`) |
| `config.json` | Runtime execution config (created from template) |
| `config.example.json` | Config template — copy to `config.json` to start |
| `TOOLS.md` | Workspace-specific site and environment configuration |
| `output/_state.json` | Download state for incremental runs |

## Repository role

Treat this repository as an agent-operated workspace for:

- authenticated article fetching from the configured target site
- already-accessible Q&A retrieval
- browser-assisted retrieval of authorized content
- incremental polling with `--new-only`
- scheduled collection through Windows task automation

## Authentication rules

- Prefer `auth.mode = browser_auto` — reads cookies from local Chrome or Edge automatically.
- Do not ask the user to paste cookies unless automatic browser auth fails.
- Assume the user is already logged into the target site in their local browser.
- If login verification returns HTTP 401 or 403, instruct the user to log into the target site in Chrome or Edge, then retry.
- Fall back to manual `cookies` in `config.json` only after browser auth failure is confirmed and reported.

## Configuration rules

1. Check if `config.json` exists in the workspace root.
2. If not, create it: `copy config.example.json config.json`
3. Verify `base_url` is set to the real target site URL (not `example.com`).
4. Verify `target_uid` is set to the real target user ID (not `YOUR_TARGET_UID`).
5. Verify `api_paths` match the site's actual API structure.
6. Keep `auth.mode` as `browser_auto` unless explicitly debugging fallback auth.
7. Set `proxy` only if the user has a proxy requirement.

## Capability map

| Capability | Preferred command | Transport |
|---|---|---|
| Auth check | `py -m paywallfetcher auth check` | local |
| Pre-flight check | `py -m paywallfetcher doctor` | local |
| List articles | `py -m paywallfetcher article list` | requests |
| Download all articles | `py -m paywallfetcher article fetch` | requests |
| Incremental article poll | `py -m paywallfetcher article fetch --new-only` | requests |
| Resume from offset | `py -m paywallfetcher article fetch --start N` | requests |
| Skip images | `py -m paywallfetcher article fetch --no-images` | requests |
| List Q&A | `py -m paywallfetcher qa list` | requests |
| Download all Q&A | `py -m paywallfetcher qa fetch` | requests |
| Incremental Q&A poll | `py -m paywallfetcher qa fetch --new-only` | requests |
| Browser-assisted Q&A retrieval | `py -m paywallfetcher qa browser-fetch --batch-size 3` | Playwright |
| Headless browser retrieval | `py -m paywallfetcher qa browser-fetch --headless` | Playwright |
| Inspect state | `py -m paywallfetcher state inspect` | local |
| Reset state | `py -m paywallfetcher state reset` | local |

## Flag reference

### Global flags (must appear before the subcommand)

| Flag | Type | Description |
|---|---|---|
| `--json` | bool | Machine-readable JSON output — must precede the subcommand |
| `--config FILE` | str | Path to config file — must precede the subcommand |

```
Correct: py -m paywallfetcher --json article fetch --new-only
Correct: py -m paywallfetcher --config path/config.json article fetch
Wrong:   py -m paywallfetcher article fetch --new-only --json
```

### `py -m paywallfetcher article fetch`

| Flag | Type | Description |
|---|---|---|
| `--new-only` | bool | Incremental mode — stop at first known article |
| `--start N` | int | Start from Nth article (1-based, for resume) |
| `--no-images` | bool | Skip image downloads |
| `--dry-run` | bool | List without saving |
| `--fail-on-empty` | bool | Exit 10 if no new content in incremental mode |

### `py -m paywallfetcher qa fetch`

| Flag | Type | Description |
|---|---|---|
| `--new-only` | bool | Incremental mode |
| `--start N` | int | Start from Nth item |

### `py -m paywallfetcher qa browser-fetch`

| Flag | Type | Description |
|---|---|---|
| `--batch-size N` | int | Pages open in parallel (default 5) |
| `--headless` | bool | Headless mode (default: headed for debug) |
| `--no-screenshots` | bool | Disable failure screenshots |

## State model

- `output/_state.json` — v2 state: per-article dict with `first_seen_at`, `last_downloaded_at`, title, content hash. Supports migration of v1 list-based state data format on load.
- `qa/output/_state.json` — same for Q&A items, including `answer_status`.
- `--new-only` reads this at startup and stops scanning as soon as a known ID is seen.
- Delete `_state.json` to force a full re-scan on next run.
- `output/_article_list.json` — article index from the last full scan.
- State writes are atomic (write to `.tmp` then rename). Not safe for concurrent write access.

## Operating procedure

1. Check whether `config.json` exists. If not, create it from `config.example.json`.
2. Confirm `base_url` and `target_uid` are not placeholder values.
3. Assume the user is logged into the target site in Chrome or Edge.
4. Run a pre-flight check and lightweight verification first:
   ```powershell
   py -m paywallfetcher doctor
   py -m paywallfetcher article list
   ```
5. Read the output. Confirm:
   - `Auth: browser:chrome` or `Auth: browser:edge` (not `config`)
   - Login verification shows the target user name
   - Article list returns real items
6. If listing succeeds, proceed with the requested download mode.
7. If browser auth fails, report the failure and fall back to manual cookie configuration.

## Error handling

| Symptom | Likely cause | Corrective action |
|---|---|---|
| `[Error] 'base_url' must be set` | `config.json` still has placeholder | Set `base_url` to the real site URL |
| `[Error] 'target_uid' is required` | `config.json` still has placeholder | Set `target_uid` to the real user ID |
| `[Warn] Browser auth unavailable` | Chrome/Edge cookies not found | Ensure the user is logged into the target site in Chrome or Edge |
| Login verification: HTTP 401/403 | Session expired | Ask user to log into the target site again, then retry |
| Login verification: HTTP 403 | IP blocked or rate limited | Add `proxy` to config or wait before retrying |
| `No articles found` | Wrong UID or empty account | Confirm `target_uid` is correct |
| Article content empty | Content is client-side rendered | May require Playwright-based fetching instead of requests |
| `[Error] No cookies found` | `auth.mode = config` and no cookies set | Switch to `browser_auto` or populate `cookies` in config |
| Playwright error on browser-fetch | Chromium not installed | Run `py -m playwright install chromium` |
| `browser-assisted retrieval` fails | Session expired or site changed | Check `failure.png` in the output folder |

## Scheduling

### Preferred: OpenClaw cron (native)

OpenClaw's `cron` is a first-class typed tool and is the preferred scheduling path.
It persists jobs in the Gateway and wakes the agent at the scheduled time.

Ask OpenClaw:

```
Create a daily cron job at 09:00 that runs:
  py -m paywallfetcher --json article fetch --new-only
Set the working directory to this workspace.
Do not deliver if the output contains no new items.
```

### Fallback: Windows Task Scheduler

Use this only when OpenClaw cron is not available.

```powershell
$action = New-ScheduledTaskAction -Execute "py" `
    -Argument "-m paywallfetcher article fetch --new-only" `
    -WorkingDirectory "C:\PATH\TO\PaywallFetcher"
$trigger = New-ScheduledTaskTrigger -Daily -At "09:00"
Register-ScheduledTask -TaskName "PaywallFetcher-Daily" `
    -Action $action -Trigger $trigger -RunLevel Highest
```

Manage the task:

```powershell
Get-ScheduledTask -TaskName "PaywallFetcher-Daily"
Start-ScheduledTask -TaskName "PaywallFetcher-Daily"
Unregister-ScheduledTask -TaskName "PaywallFetcher-Daily" -Confirm:$false
```

## Success signals

Treat the skill as working when all of the following appear in command output:

- Login verification: status OK and real target user name shown
- Auth source: `browser:chrome` or `browser:edge`
- Article or Q&A listing: returns real items with titles and dates
- Output files written to `output/` or `qa/output/`
- `_state.json` updated with new IDs and `last_successful_run_at` timestamp
