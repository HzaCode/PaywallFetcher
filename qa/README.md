# Q&A

This directory contains the backward-compatible Q&A entry points (`qa_downloader.py`, `qa_unlock.py`).

**Prefer the unified CLI** (`py -m paywallfetcher`) over the legacy scripts directly.
See `skills/site-content-downloader/SKILL.md` for the canonical agent contract.

## Recommended commands

### 1. List Q&A without downloading

```powershell
py -m paywallfetcher qa list
```

### 2. Download all Q&A

```powershell
py -m paywallfetcher qa fetch
```

### 3. Incremental polling (preferred for repeat runs)

```powershell
py -m paywallfetcher qa fetch --new-only
```

### 4. Browser-assisted retrieval (when answer is not in server-rendered response)

```powershell
py -m paywallfetcher qa browser-fetch --batch-size 3
```

```powershell
py -m paywallfetcher qa browser-fetch --headless
```

## Execution contract

- All commands read from the project root `config.json`.
- `api_paths.qa_page` must be set for Q&A page resolution.
- Authentication comes from the shared browser-based auth flow (`browser_auto`).
- Manual cookies are fallback-only.

## Runtime requirements

- Windows
- Python available as `py`
- Chrome or Edge logged into the target site
- Playwright required only for `qa browser-fetch`:

```powershell
py -m pip install playwright
py -m playwright install chromium
```

## Output

```
qa/output/
├── _qa_list.json
├── _state.json
├── <question-id>/
│   ├── qa.html
│   └── qa.txt
└── ...
```
