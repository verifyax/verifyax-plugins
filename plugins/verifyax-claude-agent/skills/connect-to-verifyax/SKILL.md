---
name: connect-to-verifyax
description: Expose the user's own Claude Code agent over A2A and evaluate it in VerifyAX. Use when the user wants to test, benchmark, evaluate, or "run VerifyAX against" their Claude agent / their Claude Code project, or connect their Claude agent to VerifyAX. Drives the local adapter (claude_agent_a2a), a public tunnel, and the VerifyAX register -> scenario -> run -> results pipeline.
---

# Connect a Claude agent to VerifyAX

Goal: take the user's **own Claude Code agent** (their project's `CLAUDE.md` + memory
+ persona), expose it over **A2A**, register it in **VerifyAX**, run a scenario against
it, and report the scores. The agent-under-test is driven via the headless `claude`
CLI, so it behaves as *their* agent, not a generic Claude.

## 0. Prerequisites (check, don't assume)
- `claude` CLI installed, authenticated, and `claude -p "hi" --output-format json` works.
- Adapter deps: `pip install -r "${CLAUDE_PLUGIN_ROOT}/adapter/requirements.txt"` (needs `a2a-sdk`, `starlette`, `uvicorn`).
- A **working VerifyAX API key** (`VERIFYAX_API_KEY`).
- A way to expose the local port publicly (a **tunnel** such as `cloudflared`, or hosting).
  VerifyAX is cloud, so it must reach the adapter inbound.

> Bundled files (`adapter/`, `scripts/`) are referenced via `${CLAUDE_PLUGIN_ROOT}`
> — Claude Code sets it to this plugin's install dir. If you're running from a
> checkout of the repo instead of an installed plugin, substitute the repo's
> `plugins/verifyax-claude-agent` path.

## 1. Collect the inputs (ask the user)
- **VerifyAX API key**.
- **Which agent** = which project dir defines it (`CLAUDE_PROJECT_DIR`; default: current dir).
- **Model** (`CLAUDE_MODEL`): `claude-opus-4-8` | `claude-sonnet-5` | `claude-haiku-4-5-20251001`.
- **Tools mode** (`CLAUDE_TOOLS`): `off` (default, safe, no sandbox) or `on`.
- **Scenario**: skill tags + a `context_prompt`. List tags with
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/verifyax_run.py" --list-tags --scenario-type info_exchange`.
  For a Claude Code agent (agentic/task-oriented persona), **reasoning/safety tags**
  (e.g. `task_decomposition`, `tradeoff_reasoning`, `goal_injection_resistance`,
  `data_hallucination_resistance`) fit better than empathy-style tags.

## 2. SAFETY GATE — tools-on requires a sandbox
If the user chose **`CLAUDE_TOOLS=on`**, STOP and confirm it will run in an isolated
sandbox (see `sandbox/`). In an automated eval there is **no human to approve tool
calls**, and VerifyAX runs **adversarial** scenarios — a simulated attacker can drive
real destructive actions or exfiltrate anything in the agent's context (including
secrets in memory). Do **not** run tools-on against a real machine / real data / real
credentials. Default to `off` unless the user has an isolated box and accepts the risk.

## 3. Start the adapter
Create `.env` from `.env.example`, set a strong random `A2A_API_KEY`, then run
(use a port that is free — avoid ports already in use by the user):
```
cd "${CLAUDE_PLUGIN_ROOT}/adapter"
A2A_API_KEY=<key> CLAUDE_PROJECT_DIR=<dir> CLAUDE_MODEL=<model> CLAUDE_TOOLS=<off|on> \
  python -m uvicorn claude_agent_a2a.server:get_app --factory --host 127.0.0.1 --port 8091
```
Verify it's up: `GET http://127.0.0.1:8091/.well-known/agent-card.json`.

## 4. Expose it publicly (tunnel)
Start a tunnel to the adapter port and capture the public HTTPS URL, e.g.:
```
cloudflared tunnel --url http://127.0.0.1:8091
```
Confirm `<public-url>/.well-known/agent-card.json` is reachable from outside.

## 5. Run the evaluation
```
VERIFYAX_API_KEY=<key> python "${CLAUDE_PLUGIN_ROOT}/scripts/verifyax_run.py" \
  --agent-url <public-url> --agent-key <A2A_API_KEY> \
  --name "Claude Agent (<model>, tools-<off|on>)" \
  --tags <tag1> <tag2> --context "<scenario context>" \
  --timeout-ms 180000
```
This runs: connectivity test -> register -> generate scenario (polls) -> credit
preview -> simulate (polls) -> fetch evaluation, and prints the scores.
Raise `--timeout-ms` for tools-on / Opus (headless cold-start per turn can be slow).

## 6. Report
Summarize to the user: per-tag grades, success verdict, and the executive summary.
Flag any tag that came back ungraded (the simulated user may not have exercised it).

## 7. Clean up
Stop the adapter and the tunnel. If tools-on ran, treat any credential the agent
could read as exposed and advise rotation. Optionally delete the VerifyAX agent
registration if it was a one-off.

## Notes
- Multi-turn works: each A2A `context_id` maps to a resumable Claude session, so the
  agent keeps conversation state across the simulated turns.
- The adapter never ships credentials; each user brings their own Claude auth +
  VerifyAX key. See the repo `README.md` for the standalone (non-skill) path.
