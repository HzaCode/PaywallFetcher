# PaywallFetcher

> **Agent-first content fetching skill for Windows.**
>
> Skill contract: [`skills/site-content-downloader/SKILL.md`](skills/site-content-downloader/SKILL.md)
>
> Agent operating guide: [`AGENTS.md`](AGENTS.md)

PaywallFetcher is an agent-first repository for authenticated article fetching, Q&A retrieval, browser-assisted retrieval of authorized content, incremental polling, and scheduled collection.

## Primary entrypoints

| Entry | Purpose |
|---|---|
| [`skills/site-content-downloader/SKILL.md`](skills/site-content-downloader/SKILL.md) | Canonical skill contract |
| [`AGENTS.md`](AGENTS.md) | Agent operating guide |
| [`TOOLS.md`](TOOLS.md) | Workspace-specific site and environment configuration |
| [`skills/README.md`](skills/README.md) | Skill index |
| [`config.example.json`](config.example.json) | Execution template |

## What this repository is for

Use this repository when an agent needs to:

- list or fetch premium articles from a site the user is already logged into
- list or fetch already-accessible Q&A content
- retrieve authorized Q&A content via browser-assisted session
- run incremental polling jobs with `--new-only`
- install or invoke a reusable OpenClaw-compatible skill instead of ad hoc scripts

## Agent-first design

This repository is optimized for **agent execution** and reusable automated operation.

- **Authentication source**: local Chrome or Edge session via `browser_auto`
- **Canonical skill contract**: `skills/site-content-downloader/SKILL.md`
- **Canonical execution config**: `config.json` derived from `config.example.json`
- **Incremental polling model**: `output/_state.json` + `--new-only`
- **Scheduling model**: OpenClaw cron (preferred) or Windows Task Scheduler (fallback)

## Fast path for agents

### 1. Read the skill

Open [`skills/site-content-downloader/SKILL.md`](skills/site-content-downloader/SKILL.md).

### 2. Ensure config exists

If `config.json` is missing, create it from `config.example.json`.

### 3. Prefer browser auth

Keep `auth.mode` set to `browser_auto` unless debugging fallback auth.

### 4. Run a pre-flight check

```powershell
py -m paywallfetcher doctor
py -m paywallfetcher article list
```

### 5. For scheduled polling, prefer OpenClaw cron

```
Create a daily cron job at 09:00 that runs:
  py -m paywallfetcher --json article fetch --new-only
Set the working directory to this workspace.
```

## Capability map

| Capability | Preferred command | Transport |
|---|---|---|
| Pre-flight check | `py -m paywallfetcher doctor` | local |
| Auth check | `py -m paywallfetcher auth check` | local |
| Article listing | `py -m paywallfetcher article list` | requests |
| Article fetch (full) | `py -m paywallfetcher article fetch` | requests |
| Article fetch (incremental) | `py -m paywallfetcher article fetch --new-only` | requests |
| Q&A listing | `py -m paywallfetcher qa list` | requests |
| Q&A fetch (incremental) | `py -m paywallfetcher qa fetch --new-only` | requests |
| Browser-assisted Q&A retrieval | `py -m paywallfetcher qa browser-fetch` | Playwright |
| State inspect / reset | `py -m paywallfetcher state inspect` | local |
| Skill behavior contract | `skills/site-content-downloader/SKILL.md` | agent-facing |

## Repository map

```text
.
├── README.md
├── AGENTS.md
├── TOOLS.md
├── RESPONSIBLE_USE.md
├── SECURITY.md
├── pyproject.toml
├── auth_utils.py
├── config.example.json
├── downloader.py
├── qa/
│   ├── README.md
│   ├── qa_downloader.py
│   └── qa_unlock.py
├── src/
│   └── paywallfetcher/
│       ├── cli.py
│       ├── config.py
│       ├── state.py
│       ├── auth.py
│       ├── articles.py
│       ├── qa.py
│       ├── unlock.py
│       └── sites/
│           ├── base.py
│           └── generic.py
├── tests/
├── skills/
│   └── site-content-downloader/
│       └── SKILL.md
└── workspace-template/
    ├── AGENTS.md
    └── TOOLS.md
```

## Operational model

### Authentication

- Do not ask for pasted cookies unless browser-based auth fails.
- The expected runtime is Windows with `py` available.
- The expected browser state is an already-authenticated Chrome or Edge session.

### Incremental polling

- `--new-only` stops scanning once previously downloaded content is encountered.
- `output/_state.json` (v2) is the state boundary for repeat runs. Supports migration of v1 list-based state data format on load.
- This is the preferred mode for monitoring a target account over time.

### Scheduling

- **Preferred**: OpenClaw `cron` — ask OpenClaw to register a daily cron job.
- **Fallback**: Windows Task Scheduler — see `skills/site-content-downloader/SKILL.md` for setup commands.

### Workspace vs. shared skill

- `TOOLS.md` holds workspace-specific and site-specific configuration.
- `skills/site-content-downloader/SKILL.md` is the portable skill contract.
- This repository is a **self-contained skill + implementation bundle**. The skill execution depends on `src/paywallfetcher/` and the workspace scaffold. To reuse it, clone or fork the entire repository and update `config.json` for the new target site.

## Quick command reference

```powershell
py -m paywallfetcher doctor
py -m paywallfetcher article list
py -m paywallfetcher article fetch
py -m paywallfetcher article fetch --new-only
py -m paywallfetcher qa list
py -m paywallfetcher qa fetch --new-only
py -m paywallfetcher qa browser-fetch --batch-size 3
py -m paywallfetcher state inspect
```

## Requirements

- Windows
- Python available as `py`
- Chrome or Edge logged into the target site

## License

MIT
