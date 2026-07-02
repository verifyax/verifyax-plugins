# Security Policy

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue or PR.

- Preferred: open a [GitHub private security advisory](https://github.com/verifyax/verifyax-plugins/security/advisories/new).
- Or email **security@conscium.com** (subject: `verifyax-plugins security`).

Include enough detail to reproduce (which plugin, steps, and impact). We'll acknowledge your report and keep you posted on remediation.

## What these plugins handle

Both plugins work with a user's **VerifyAX API key** (`sk-ver-api-...`):

- **`verifyax-mcp`** — stores the key via the plugin's `sensitive` user-config field and passes it to the pinned [`@verifyax/mcp-server`](https://www.npmjs.com/package/@verifyax/mcp-server) as an environment variable.
- **`verifyax-api`** (skill) — reads the key from the `VERIFYAX_API_KEY` environment variable; it is never requested in chat.

## Handling API keys

- Never paste a key into a chat, issue, log, or commit. Treat keys as sensitive end to end.
- Rotate a key immediately if it may have been exposed (VerifyAX console → **Settings → API Keys**).

## Supported versions

Fixes land on the latest released version of each plugin (see [`CHANGELOG.md`](CHANGELOG.md)).
