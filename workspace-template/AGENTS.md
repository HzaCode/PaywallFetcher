# AGENTS.md — PaywallFetcher Workspace Template

## What this workspace is

A configured instance of the `paywall-fetcher` OpenClaw skill, ready to
execute against a specific target site.

## Skill contract

Read the canonical skill contract before running any command:

```
skills/site-content-downloader/SKILL.md
```

All execution decisions, flag choices, and fallback logic are documented there.

## Workspace-specific notes

Site configuration and environment-specific details are in `TOOLS.md`.
Do not put site-specific information in the shared skill file.

## Scheduling

Preferred: ask OpenClaw to register a cron job:

```
Create a daily cron job at 09:00 that runs:
  py -m paywallfetcher --json article fetch --new-only
Set the working directory to this workspace.
```

Fallback (no OpenClaw cron available): see the scheduled task setup section
in `skills/site-content-downloader/SKILL.md`.

## Decision policy

- Read the skill file before running anything.
- Prefer `py -m paywallfetcher` over the legacy wrapper scripts.
- Prefer incremental mode (`--new-only`) for repeat runs.
- Prefer browser auth over manual cookies.
- Use `py -m paywallfetcher doctor` before starting any new session.
