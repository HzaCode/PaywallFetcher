# Skills Index

## Available skills

### `paywall-fetcher`

- **Primary skill file**: [`site-content-downloader/SKILL.md`](site-content-downloader/SKILL.md)
- **Purpose**: authenticated article fetching, Q&A fetching, browser-assisted Q&A retrieval, incremental polling, and scheduled retrieval
- **Runtime**: Windows + `py`
- **Auth model**: browser session reuse from Chrome or Edge

## Agent routing rule

If an agent arrives at this repository root and needs the canonical contract, it should read:

```text
skills/site-content-downloader/SKILL.md
```

before attempting any ad hoc command execution.
