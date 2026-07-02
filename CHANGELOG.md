# Changelog

All notable changes to the plugins in this marketplace are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the plugins follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Versions are tracked per plugin.

## verifyax-api

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
