---
name: verifyax-api
description: Drive the VerifyAX agent-evaluation platform via its REST API — register agents (A2A, REST, Direct Line, MCP), generate tagged test scenarios, run simulations, poll async jobs, and fetch evaluation results. Use when the user wants to evaluate, benchmark, simulate, or test an AI agent against scenarios via the VerifyAX API or console.verifyax.com, or to script the register → generate → run → evaluate → fetch pipeline. For no-code conversational use, prefer the verifyax-mcp plugin (the @verifyax/mcp-server MCP server).
---

# VerifyAX API Skill

Drive the VerifyAX platform API — register agents, create scenarios, run simulations, poll jobs, and
fetch evaluations. This guide carries the **workflow and behavioural rules a spec can't express**;
for the **exact, current shape** of any endpoint (parameters, request/response fields, enums, status
codes), read the canonical contract rather than guessing.

## Get the exact contract (do this before calling an endpoint)

The machine-readable spec is the source of truth and is always current:

```bash
curl -s https://console.verifyax.com/openapi.yaml -o /tmp/verifyax-openapi.yaml
# then grep for the operation you need, e.g.:
grep -n "scenarios/generate" /tmp/verifyax-openapi.yaml
```

Grep the spec for the operation, read its request/response schema, and use those exact field names —
**do not invent field names or assume a shape.** A human-readable companion to this guide is served
at `https://console.verifyax.com/SKILL.md`.

## Base URL & authentication

All endpoints live under **`{origin}/api/v1`** (production: `https://console.verifyax.com/api/v1`).
Every request needs a Bearer token:

```
Authorization: Bearer <api-key>      # keys look like sk-ver-api-...
Content-Type: application/json        # on POST/PUT/PATCH with a body
```

The **API key encodes tenant context** — never send `organization_uuid`, `workspace_uuid`, or
`user_uuid`; the gateway injects them from your key and overwrites any client-supplied values. Get
keys from **Settings → API Keys** (shown once at creation).

### Handle the key as a secret

- Read it from the **`VERIFYAX_API_KEY` environment variable**; never hard-code it, log it, write it
  to disk, or paste it into a chat. Source it in code (`os.environ["VERIFYAX_API_KEY"]`), don't inline it.
- Rotate immediately if it may have been exposed.

## Core workflow

Register agent → discover compatible tags → generate scenario (async) → poll job → preview credits →
trigger simulation → poll run → evaluate → fetch results → track spend.

## Behavioural rules the spec doesn't capture

- **Async is two-phase.** Many `POST`s return **`201 Created` + a `job_uuid`**, then the *job* can
  still **`FAIL`**. Always poll `GET /api/v1/jobs/{job_uuid}` to a terminal state and read
  `error_details` on failure. **Branch on the HTTP status code, not the response body.**
- **IDs come back in the `uuid` field** of responses; path params use prefixed names
  (`{scenario_uuid}`) but you supply the `uuid` value.
- **Statuses are UPPERCASE** (`PENDING`/`PROCESSING`/`COMPLETED`/`FAILED`/`CANCELLED`; runs also use
  `CREATED`/`IN_PROGRESS`; scenarios use `INIT`/`PROCESSING`/`SUCCESS`/`FAILED`/`CANCELLED`).
  `agent_type` ∈ `A2A`/`API`/`DIRECTLINE`/`MCP`.
- **Treat enums as open and tolerate unknown fields** — new values/keys ship without a version bump.
  Treat an unrecognised status as "not yet terminal," not an error.
- **List endpoints return bare JSON arrays** (no envelope). Paginate with `limit` (default 100, max
  1000) and `offset`.
- **Errors: the HTTP status is the source of truth.** Body shape varies by origin — read whichever of
  `message` / `detail` / `error` is present; don't rely on a `statusCode` field (only rate-limit
  responses carry one).
- **Rate limit: ~300 req/min per workspace.** Honour `Retry-After` on `429`; otherwise back off
  exponentially and pace polling loops well below the limit.

## Tags (discover before generating)

Skill tags select what a scenario measures. Fetch the catalogue with your key:

```
GET /api/v1/tags        # authed; returns a BARE JSON ARRAY (global catalogue + your org overlay)
```

Each tag has `name`, `category`, `description`, `benchmark_family`, `allowed_scenario_types`, `custom`.
**Compatibility is enforced asynchronously by the worker, not at `POST`** — so filter **client-side**
before generating:

- Pass each tag's exact **`name`** in `tags` / `tag_pool`.
- Keep only tags whose `allowed_scenario_types` includes your `scenario_type` (omitted ⇒ both; `[]` ⇒ not selectable).
- **Benchmark tags** (`benchmark_family` set, except `qna`) → **`info_exchange` only**.
- **QnA tags** (`benchmark_family: "qna"`) → **`interview` only, and must be the sole tag**.
- Unknown tag names ⇒ the generation **job fails** (201 then FAILED). Caps: ≤5 `info_exchange`, ≤2 `interview`.

## Robust polling (Python)

```python
import os, time, requests

BASE = "https://console.verifyax.com/api/v1"
H = {"Authorization": f"Bearer {os.environ['VERIFYAX_API_KEY']}"}

def wait_for_job(job_uuid, deadline_s=1800):
    deadline, delay = time.time() + deadline_s, 5
    while time.time() < deadline:
        r = requests.get(f"{BASE}/jobs/{job_uuid}", headers=H, timeout=30)
        r.raise_for_status()
        status = str(r.json().get("current_status", "")).upper()
        if status == "COMPLETED":
            return r.json()
        if status in ("FAILED", "CANCELLED"):
            raise RuntimeError(r.json().get("error_details") or status)
        time.sleep(delay)
        delay = min(delay * 2, 30)   # backoff, capped; stay under the rate limit
    raise TimeoutError(f"job {job_uuid} did not finish within {deadline_s}s")
```

## Common async failures (poll the job, read `error_details`)

| `error_details` pattern | Fix |
|---|---|
| `tags do not exist in the skill tags registry` | Re-fetch `GET /api/v1/tags`; use exact `name` values |
| `does not support … benchmark tags` | Use `info_exchange`, or pick non-benchmark tags |
| `QnA tags are only supported for 'interview'` | Switch to `interview` or drop the QnA tag |
| mentions `--list-tags` | Ignore the CLI hint; use the tags endpoint |

## Security note

`POST /api/v1/auth/one-time-login-token` returns a **live, redeemable browser-session link** — treat
the returned token/URL as a credential (short-lived and single-use, but sensitive); don't log or share it.

---

For everything else — exact endpoint paths, request/response fields, and enums — **grep the
`openapi.yaml` you downloaded above.** It is the authoritative, current contract.
