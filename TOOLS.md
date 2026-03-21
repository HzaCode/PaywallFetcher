# TOOLS.md

## Workspace-specific configuration

This file contains site-specific and environment-specific information that
belongs to the workspace, not to the shared skill.

Edit this file when you set up PaywallFetcher for a specific target site.

---

## Active target

| Field | Value |
|---|---|
| Site kind | (set `site.kind` in config.json — e.g., `generic`) |
| Base URL | (set `site.base_url` in config.json) |
| Target UID | (set `site.target_uid` in config.json) |
| Auth mode | `browser_auto` (reads Chrome or Edge session) |
| Output root | `./output` |
| Q&A output | `./qa/output` |

---

## Site adapter: `generic`

Default API path templates (override via `site.api_paths` in `config.json`):

| Path key | Template |
|---|---|
| `profile` | `/ajax/profile/info?uid={uid}` |
| `articles` | `/ajax/statuses/articles?uid={uid}&page={page}&feature=10` |
| `article_page` | `/article/p/show?id={article_id}` |
| `qa_page` | `/p/{qa_id}` |

Override these under `site.api_paths` in `config.json` if the target site uses different paths.

---

## Required cookies

Populate these under `cookies` in `config.json` as a fallback if browser auth is unavailable:

- `SESSION`
- `XSRF-TOKEN`

Preferred: keep `auth.mode = browser_auto` and stay logged in through Chrome or Edge.

---

## Proxy

If a proxy is required, set it in `config.json`:

```json
"network": {
  "proxy": "http://proxy.example.com:8080"
}
```

Credentials in the proxy URL are redacted in log output.

---

## Workspace path (for scheduled tasks)

When setting up a scheduled task, replace the placeholder below with the
actual workspace path:

```
C:\PATH\TO\PaywallFetcher
```

---

## Responsible use

This workspace is configured for content the account holder is already
authorized to access. See `RESPONSIBLE_USE.md` for the full policy.
