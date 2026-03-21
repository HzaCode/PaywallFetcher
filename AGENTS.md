# AGENTS.md

## Repository role

This repository is an **agent-operated content fetching workspace**.

Use it when an agent must:

- fetch premium articles from a logged-in target site
- fetch already-accessible Q&A content
- retrieve authorized content via browser session
- monitor a target account with incremental polling
- register scheduled jobs for repeat collection

## Canonical entrypoints

- **Primary skill contract**: skills/site-content-downloader/SKILL.md
- **Repository landing page**: README.md
- **Config template**: config.example.json
- **Workspace-specific config**: TOOLS.md
- **Article fetcher**: downloader.py
- **Q&A fetcher**: qa/qa_downloader.py
- **Q&A browser-assist**: qa/qa_unlock.py
- **Auth layer**: auth_utils.py

## Agent operating assumptions

- OS target is Windows.
- Python should be invoked as py.
- Authentication should come from the user's logged-in Chrome or Edge session.
- Manual cookie entry is fallback-only.
- config.json is the local execution contract.

## Preferred execution sequence

### 1. Validate config

- Ensure config.json exists. If not, create from config.example.json.
- Ensure base_url is a real site URL (not example.com).
- Ensure target_uid is populated (not YOUR_TARGET_UID).

### 2. Pre-flight check

`powershell
py -m paywallfetcher doctor
`

### 3. Lightweight verification

`powershell
py -m paywallfetcher article list
`

### 4. Choose execution mode

- **Full fetch**: py -m paywallfetcher article fetch
- **Incremental poll**: py -m paywallfetcher article fetch --new-only
- **Q&A incremental poll**: py -m paywallfetcher qa fetch --new-only
- **Browser-assisted retrieval**: py -m paywallfetcher qa browser-fetch --batch-size 3

## Scheduling

Preferred: ask OpenClaw to register a cron job:

`
Create a daily cron job at 09:00 that runs:
  py -m paywallfetcher --json article fetch --new-only
Set the working directory to this workspace.
`

Fallback: Windows Task Scheduler (see SKILL.md for setup commands).

## Output expectations

Successful runs should produce:

- authenticated verification output
- real listed items or downloaded files
- state written to output/_state.json
- saved outputs under output/ or qa/output/

## Decision policy

- Prefer py -m paywallfetcher over the legacy wrapper scripts.
- Prefer the reusable skill over ad hoc one-off shell logic.
- Prefer incremental mode for monitoring tasks.
- Prefer browser auth over manual cookies.
- Fall back to manual cookies only after browser auth failure is confirmed.

## Failure handling

| Failure | Action |
|---|---|
| config.json missing | Copy from config.example.json, then set base_url and target_uid |
| base_url is placeholder | Ask the user for the real site URL |
| target_uid is placeholder | Ask the user for the real target UID |
| Browser auth fails | Ask user to log into the target site in Chrome or Edge, then retry |
| Login verification: HTTP 401 or 403 | Session expired  ask user to re-login, then retry |
| HTTP 403 on article fetch | Possible rate limit or IP block  add proxy or add delay |
| Article list empty | Confirm target_uid and api_paths are correct for the target site |
| _state.json corrupted | Run py -m paywallfetcher state reset |
| Playwright not installed | Run py -m playwright install chromium |
