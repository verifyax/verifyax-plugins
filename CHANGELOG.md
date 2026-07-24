# Changelog

All notable changes to the plugins in this marketplace are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the plugins follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Versions are tracked per plugin.

## verifyax-claude-agent

### [0.1.0] — 2026-07-24

Initial release. Expose your own Claude Code agent over A2A so VerifyAX can evaluate it —
the complement to `verifyax-api`/`verifyax-mcp` (which *drive* evaluations).

#### Added

- **Adapter** (`claude_agent_a2a`) that wraps the local `claude` CLI headlessly behind an
  A2A endpoint. Each A2A `context_id` maps to a resumable Claude session (`--resume`), so
  multi-turn evaluations keep state. Public agent card; bearer-gated `message/send`.
- **`connect-to-verifyax` skill**: guided flow — collect inputs → start adapter + tunnel →
  evaluate → report scores.
- **Reuses the `verifyax-api` skill** for all VerifyAX API work (register → tags → scenario →
  simulate → fetch evaluation). This plugin holds no copy of the API surface, so the contract
  stays in one place and can't drift. Declared as a **plugin dependency**, so `verifyax-api`
  auto-installs with this plugin.
- **Automated tunnel** (`scripts/tunnel.py`): ensures/downloads `cloudflared` and opens a
  Quick Tunnel, printing the public `TUNNEL_URL` — no manual tunnel setup.
- **Guided-flow guardrails**: previews credits and confirms before the paid run (and warns
  it spends Claude quota); defaults to a clean project dir and warns that pointing at a real
  project sends its `CLAUDE.md` + memory into VerifyAX-stored transcripts.
- **Two modes**: `tools-off` (pure conversation, no sandbox) and `tools-on` (autonomous tool
  use, via the disposable `sandbox/` container with the documented safety guardrails).
- **Security hardening**: tools-on is **enforced-gated** — the adapter refuses it unless
  `CVX_SANDBOX_CONFIRMED=1` (set by the sandbox image); the tunnel prints and can pin/verify
  the cloudflared SHA256 (`CLOUDFLARED_VERSION` / `CLOUDFLARED_SHA256`); timed-out `claude`
  children are reaped; and docs warn against reusing the VerifyAX key as the inbound bearer
  and about project memory reaching VerifyAX-stored transcripts.
- **Continuity**: supports a fixed `A2A_API_KEY` + a stable `PUBLIC_BASE_URL` (named tunnel or
  hosting) to register once and reconnect across restarts (`PATCH` to update); otherwise the
  default flow is register-then-delete per run.

## verifyax-api

### [0.3.0] — 2026-07-03

Rework the skill around the **canonical OpenAPI contract as the single source of truth**. The API
surface is no longer transcribed into the skill (where it drifted); it is fetched from
`console.verifyax.com/openapi.yaml` on demand.

#### Changed

- SKILL.md shrinks ~476 → ~130 lines: it keeps the **workflow and behavioural rules a spec can't
  express** (async `201`-then-`FAILED`, async tag-compatibility, open enums, error-status-is-truth,
  rate limits, base path) and instructs the agent to **download + grep `openapi.yaml`** for exact
  endpoint shapes. The canonical human-readable companion is served at `console.verifyax.com/SKILL.md`.
- Add explicit **secret-handling** guidance inside the skill (read the key from `VERIFYAX_API_KEY`,
  never inline/log/commit it) and a **robust polling example** with a deadline + backoff.
- Tighten the trigger `description`; add a note that the one-time-login token is a live credential.

### [0.2.0] — 2026-06-28

Expanded the API reference to match the current VerifyAX gateway surface. Additive
and backward-compatible — no breaking changes to existing workflows.

#### Added
- **Direct Line (Copilot Studio) agents** — `agent_type: DIRECTLINE`, with the
  `agent_parameters.directline { secret, region }` block, region→URL mapping, and the
  `api-agent-test-directline` probe.
- **MCP agents** — `agent_type: MCP`, with `agent_parameters.mcp { url, auth_method,
  token, transport, enabled_tools }` and the `mcp-connection` discovery/probe endpoint.
- Extra connectivity probes: `a2a-connection` and `a2a-message`.
- **`POST /v1/scenarios/generate-from-qna`** for inline Q&A interview scenarios.
- Simulation runs: batch `scenario_uuids` run groups and per-run `timeout_minutes`.
- Evaluation shortcuts (`…/evaluation`, `…/evaluation/scores`, batch `…/scores`) and
  structured JSON run output (`…/output`).
- New sections: `GET /v1/billing/balance`, audit logs (`GET /v1/logs`), and
  `POST /v1/client-tags/register-qna`.

#### Changed
- **Skill-tag discovery** moved from the browser-session `/web/api/v1/tags` route to the
  public **`GET /api/v1/tags`** (Bearer key). The response is now a **bare JSON array**,
  and the per-tag flag `client_specific` is renamed **`custom`**. All references updated.
- Documented that `POST /v1/scenarios/generate` and `/generate-from-qna` forward **only
  documented public fields** — internal engine/model/DAG knobs are stripped at the gateway.
- Run timeout (`timeout_minutes`) is now set on `POST /v1/engine/simulate/scenario`
  rather than on scenario generation.
- `agent_type` documented as the open set `A2A | API | DIRECTLINE | EXTENSION | MCP`.

### [0.1.0] — initial release

- First release of the `verifyax-api` skill: register agents, generate scenarios, trigger
  simulation runs, poll async jobs, and fetch evaluation results via the VerifyAX REST API.

## verifyax-mcp

### [0.2.1] — 2026-07-01

#### Changed
- **Pin the MCP server version.** The plugin now launches `@verifyax/mcp-server@0.2.1` instead of
  the floating `@verifyax/mcp-server` (which resolved to `latest`). This makes installs
  reproducible and honors the marketplace's versioning promise — users only get a new server build
  when the plugin version is bumped. **Plugin `0.2.x` ↔ server `0.2.1`.**

### [0.2.0] — 2026-06-28

#### Changed
- Tracked the `@verifyax/mcp-server` 0.2.0 release (Streamable HTTP transport + the broad API sync).
  The plugin still launched the server unpinned; pinning landed in 0.2.1.

### [0.1.0] — initial release

- First release of the `verifyax-mcp` plugin: conversational access to VerifyAX through the
  [`@verifyax/mcp-server`](https://www.npmjs.com/package/@verifyax/mcp-server) MCP server.
