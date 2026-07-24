---
name: connect-to-verifyax
description: Expose the user's own Claude Code agent over A2A and evaluate it in VerifyAX. Use when the user wants to test, benchmark, evaluate, or "run VerifyAX against" their Claude agent / their Claude Code project, or connect their Claude agent to VerifyAX. Starts the local adapter (claude_agent_a2a) + a public tunnel, then defers all VerifyAX API work (register -> scenario -> run -> results) to the `verifyax-api` skill.
---

# Connect a Claude agent to VerifyAX

Goal: take the user's **own Claude Code agent** (their project's `CLAUDE.md` + memory
+ persona), expose it over **A2A**, and evaluate it in **VerifyAX**. This skill owns
the *connector* half (adapter + tunnel + the A2A registration parameters); it **reuses
the `verifyax-api` skill** for every VerifyAX API call, so the API contract lives in one
place and never drifts.

## 0. Prerequisites (check, don't assume)
- `claude` CLI installed, authenticated, and `claude -p "hi" --output-format json` works.
- Adapter deps: `pip install -r "${CLAUDE_PLUGIN_ROOT}/adapter/requirements.txt"` (needs `a2a-sdk`, `starlette`, `uvicorn`).
- The **`verifyax-api` plugin** — declared as a dependency of this plugin, so it is
  auto-installed alongside it. This skill hands off all VerifyAX API work to it.
- A **working VerifyAX API key** (`VERIFYAX_API_KEY`) — used only by the `verifyax-api` steps.
- Inbound reach is **handled for you**: step 4 runs the bundled `tunnel.py`, which ensures
  `cloudflared` (downloading it if missing) and prints the public URL. No manual tunnel
  setup needed — bring your own hosting only if you prefer.

> Bundled files (`adapter/`) are referenced via `${CLAUDE_PLUGIN_ROOT}` — Claude Code
> sets it to this plugin's install dir. From a repo checkout, substitute
> `plugins/verifyax-claude-agent`.

## 1. Collect the inputs (ask the user)
- **VerifyAX API key**.
- **Which agent** = which project dir defines it (`CLAUDE_PROJECT_DIR`). **Default to a
  clean/empty dir for the first run.** Pointing at a real project loads its `CLAUDE.md` +
  memory into the agent — and every turn is **stored on VerifyAX**. If that memory holds
  secrets, prefer a clean or curated dir (true even for tools-off, since the agent can
  still *quote* memory). Only use the real project when the user explicitly wants full
  "their agent" fidelity and accepts that its context leaves the machine.
- **Model** (`CLAUDE_MODEL`): `claude-opus-4-8` | `claude-sonnet-5` | `claude-haiku-4-5-20251001`.
- **Tools mode** (`CLAUDE_TOOLS`): `off` (default, safe, no sandbox) or `on`.
- **Scenario**: skill tags + a `context_prompt`. Discover tags via the `verifyax-api`
  skill (it knows the tag catalogue). For a Claude Code agent (agentic/task-oriented
  persona), **reasoning/safety tags** (e.g. `task_decomposition`, `tradeoff_reasoning`,
  `goal_injection_resistance`, `data_hallucination_resistance`) fit better than
  empathy-style tags.

## 2. SAFETY GATE — tools-on requires a sandbox
If the user chose **`CLAUDE_TOOLS=on`**, STOP and confirm it will run in an isolated
sandbox (see `sandbox/`). In an automated eval there is **no human to approve tool
calls**, and VerifyAX runs **adversarial** scenarios — a simulated attacker can drive
real destructive actions or exfiltrate anything in the agent's context (including
secrets in memory). Do **not** run tools-on against a real machine / real data / real
credentials. Default to `off` unless the user has an isolated box and accepts the risk.
The adapter **enforces** this — tools-on is refused unless `CVX_SANDBOX_CONFIRMED=1`,
which the sandbox image sets. Never set that var outside a disposable sandbox.

## 3. Start the adapter
Create `.env` from `.env.example`, set a strong random `A2A_API_KEY`, then run
(use a port that is free — avoid ports already in use by the user):
```
cd "${CLAUDE_PLUGIN_ROOT}/adapter"
A2A_API_KEY=<key> CLAUDE_PROJECT_DIR=<dir> CLAUDE_MODEL=<model> CLAUDE_TOOLS=<off|on> \
  python -m uvicorn claude_agent_a2a.server:get_app --factory --host 127.0.0.1 --port 8091
```
Verify it's up: `GET http://127.0.0.1:8091/.well-known/agent-card.json`.

## 4. Expose it publicly (tunnel — automated)
Run the bundled helper in the background; it ensures `cloudflared` (downloads it if
missing) and opens a Quick Tunnel to the adapter port:
```
python "${CLAUDE_PLUGIN_ROOT}/scripts/tunnel.py" --port 8091
```
Read the `TUNNEL_URL=https://<...>.trycloudflare.com` line it prints — that's your
`<public-url>`. Confirm `<public-url>/.well-known/agent-card.json` is reachable.
(Bring-your-own hosting is fine too — just use that URL instead.)

## 5. Evaluate via the `verifyax-api` skill  ← the handoff
Do **not** call the VerifyAX API directly from here. **Use the `verifyax-api` skill**
for every step below (it fetches the canonical OpenAPI contract, handles async
`201`-then-poll, tag compatibility, rate limits, and error semantics). Give it the
connector's agent details:

- **Register the agent** as an **A2A** agent:
  - `agent_url` = the public tunnel URL from step 4
  - `agent_type` = `A2A`
  - `agent_parameters` = `{ "auth_method": "bearer", "token": "<A2A_API_KEY>", "timeout": 300000, "max_requests_per_minute": 4 }`
  - (`timeout` is in ms and **must exceed the adapter's `turn_timeout`** — default 240000 ms — so VerifyAX doesn't abandon a turn the adapter is still processing. Raise both for Opus / tools-on cold starts.)
- **Discover/validate tags** for `scenario_type` `info_exchange`.
- **Generate the scenario** with the chosen tags + `context_prompt`; poll its job to `COMPLETED`.
- **Preview credits and CONFIRM with the user before the paid run** (VerifyAX
  `workspace-credit-preview`). Also warn that the run spends the user's **Claude quota** —
  one `claude` invocation per simulated turn (many turns), on the chosen model. Only after
  they confirm, **trigger the simulation** with `evaluate_on_complete: true`.
- **Poll** the run to `COMPLETED`, then **fetch the evaluation**.

## 6. Report
Summarize to the user: per-tag grades, success verdict, and the executive summary.
Flag any tag that came back ungraded (the simulated user may not have exercised it).

## 7. Clean up
Stop the adapter and the tunnel. If tools-on ran, treat any credential the agent
could read as exposed and advise rotation. Optionally delete the VerifyAX agent
registration if it was a one-off.

## 8. Continuity (optional)
By default this is a **one-off**: a random `A2A_API_KEY` + an ephemeral tunnel URL, so
**register-then-delete** each run. To **reconnect the same registration** across
restarts instead:
1. Keep a **fixed `A2A_API_KEY`** — persist and reuse it (**never** the VerifyAX key;
   it's a public inbound credential).
2. Use a **stable URL** (`PUBLIC_BASE_URL` via a named tunnel or hosting) — quick-tunnel
   URLs change every run, which alone breaks the persisted registration.
3. If the URL or token does change, **`PATCH` the agent** (via `verifyax-api`) to update
   `agent_url` / token rather than re-registering.
Then register once and reuse it.

## Notes
- Multi-turn works: each A2A `context_id` maps to a resumable Claude session, so the
  agent keeps conversation state across the simulated turns.
- The adapter never ships credentials; each user brings their own Claude auth +
  VerifyAX key. This plugin deliberately holds **no** copy of the VerifyAX API surface —
  that lives in `verifyax-api`.
