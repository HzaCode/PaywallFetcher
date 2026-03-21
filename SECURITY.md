# Security Policy

## Sensitive data handled by this tool

PaywallFetcher reads browser session cookies to authenticate with the target site.
These cookies are equivalent to a logged-in session and must be treated as secrets.

### What is sensitive

| Data | Risk | Mitigation |
|---|---|---|
| Browser cookies | Full account access | Never log, paste, or commit |
| `config.json` | Contains site URL and UID | Excluded by `.gitignore` |
| Proxy URL with credentials | Network credential exposure | Redacted in log output |
| `output/` and `qa/output/` | Downloaded content | Excluded by `.gitignore` |

## What NOT to do

- Do not paste cookie values into GitHub issues, pull requests, or chat.
- Do not commit `config.json`. It is excluded by `.gitignore`.
- Do not share `_progress.json` or `_state.json` files — they contain article IDs
  that reveal account activity.
- Do not include real site URLs or UIDs in bug reports.

## Reporting a vulnerability

If you discover a security issue in this project (e.g., credentials being written
to disk unintentionally, or a path traversal in output directory names), please
open a private security advisory on GitHub rather than a public issue.

## Dependency notes

| Dependency | Purpose | Risk surface |
|---|---|---|
| `browser-cookie3` | Reads local browser cookie database | Reads SQLite files from Chrome/Edge profile |
| `playwright` | Controls a local Chromium instance | Executes JavaScript in browser context |
| `requests` | HTTP client | Network requests to target site only |

`browser-cookie3` reads the local browser's encrypted cookie database. It does not
send data anywhere — all operations are local.

## Allowed base domains

You can restrict which domains the tool is allowed to contact by setting
`safety.allowed_base_domains` in `config.json`. If the `base_url` host is not
in this list, the tool will refuse to run.
