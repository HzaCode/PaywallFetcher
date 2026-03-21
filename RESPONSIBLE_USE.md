# Responsible Use

PaywallFetcher retrieves content using the credentials of an already-authenticated
browser session. This tool is designed exclusively for legitimate, authorized access.

## Intended use

- Retrieve articles and Q&A that the **authenticated account holder** is already
  authorized to access under their subscription or account.
- Archive content for personal offline use within the scope of the site's terms.

## Prohibited use

- Do not use this tool to access content that the account holder has not paid
  for or is not authorized to view.
- Do not use this tool to circumvent paywalls, subscriptions, or access restrictions
  in ways that violate the target site's terms of service.
- Do not redistribute retrieved content beyond the scope allowed by the site's
  terms of service or applicable copyright law.
- Do not use this tool to scrape content at scale for commercial purposes without
  explicit permission from the content owner.

## Rate limiting

Respect the target site's rate limits. The default delays (`delay_between_items`,
`delay_between_pages`) are set conservatively. Do not reduce them below the
site's acceptable threshold.

## Cookie security

This tool reads cookies from your local Chrome or Edge browser profile.
These cookies are sensitive authentication credentials.

- Never paste cookie values into public issues, chat, or documentation.
- Never commit `config.json` (it is excluded by `.gitignore`).
- Proxy credentials set in `network.proxy` are redacted from log output but
  should never be committed to source control.

## Legal notice

Use of this tool is the sole responsibility of the operator. The authors provide
no warranty and accept no liability for misuse. Ensure your use complies with all
applicable laws and the terms of service of the target site.
