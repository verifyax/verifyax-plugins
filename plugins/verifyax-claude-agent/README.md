# Claude → VerifyAX connector

Expose **your own Claude Code agent** over the **A2A protocol** and evaluate it in
**VerifyAX**. The agent-under-test is driven through the headless `claude` CLI in
*your* project directory, so it behaves as **your** agent (your `CLAUDE.md` +
memory + persona) — not a generic Claude.

```
VerifyAX  ──A2A message/send──▶  adapter (this kit)  ──`claude -p --resume`──▶  your Claude agent
```

## Why an adapter
VerifyAX evaluates **A2A** or **REST** agents. A Claude Code agent isn't an A2A
server, so this kit wraps it: each A2A `context_id` maps to one resumable Claude
session (`--resume`), giving VerifyAX a normal multi-turn agent to score.

## What's in the box
| Path | Role |
|------|------|
| `adapter/claude_agent_a2a/backend.py` | `ClaudeCodeBackend` — wraps `claude -p` per context (tools off/on) |
| `adapter/claude_agent_a2a/server.py` | A2A server: public agent card + bearer-gated `message/send` |
| `scripts/verifyax_run.py` | register → scenario → run → results (standalone CLI) |
| `skills/connect-to-verifyax/SKILL.md` | the **guided** flow (invoke with Claude Code) |
| `sandbox/` | disposable container for **tools-on** runs |
| `.claude-plugin/plugin.json` | Claude Code plugin manifest |

## Two modes
- **tools-off** (default) — `--allowedTools ""`: pure conversation, **zero blast
  radius, no sandbox**. Faithful to how your agent reasons and what it knows.
- **tools-on** — `--dangerously-skip-permissions`: the agent can use tools during
  the eval. **Only run inside `sandbox/`** — an automated eval has no human to
  approve tool calls, and adversarial scenarios can drive destructive actions or
  exfiltrate secrets in your agent's context.

## Prerequisites
- The **`claude` CLI** installed + authenticated (`claude -p "hi" --output-format json` works).
- `pip install -r adapter/requirements.txt`
- A **VerifyAX API key**.
- A way to expose the local port publicly (a **tunnel** like `cloudflared`, or hosting) —
  VerifyAX is cloud and must reach the adapter inbound.

## Guided path (recommended)
Install as a Claude Code plugin and run the skill:
```
/connect-to-verifyax
```
Claude collects your inputs (VerifyAX key, project, model, tools mode, tags),
starts the adapter + tunnel, registers, runs the scenario, and reports the scores.

## Standalone path
```bash
# 1. Start the adapter (tools-off; pick a free port)
cd adapter
A2A_API_KEY="<long-random>" CLAUDE_PROJECT_DIR="/path/to/your/agent" \
CLAUDE_MODEL="claude-opus-4-8" CLAUDE_TOOLS="off" \
  python -m uvicorn claude_agent_a2a.server:get_app --factory --host 127.0.0.1 --port 8091

# 2. Expose it (new terminal)
cloudflared tunnel --url http://127.0.0.1:8091      # -> https://<public-url>

# 3. Run the evaluation
export VERIFYAX_API_KEY="sk-ver-api-..."
python scripts/verifyax_run.py \
  --agent-url "https://<public-url>" --agent-key "<A2A_API_KEY>" \
  --name "My Claude Agent (opus, tools-off)" \
  --tags task_decomposition tradeoff_reasoning \
  --context "A user brings a complex, multi-part planning problem and expects the agent to decompose it and reason about trade-offs." \
  --timeout-ms 180000

# List selectable tags:
python scripts/verifyax_run.py --list-tags --scenario-type info_exchange
```

## Configuration (env)
See `.env.example`. Key ones: `A2A_API_KEY`, `CLAUDE_PROJECT_DIR`, `CLAUDE_MODEL`,
`CLAUDE_TOOLS`, `AGENT_NAME`, `PUBLIC_BASE_URL`, `VERIFYAX_API_KEY`.

## Fidelity note
The adapter runs a **fresh** headless session, so it loads your **persisted**
context (`CLAUDE.md` + memory) — not your current live chat. It's faithful to how
your agent *reasons* and what it *knows persistently*; the persona is the agentic
Claude Code one, so reasoning/safety tags fit better than empathy-style tags.

## Security
- Each user brings their **own** Claude auth + VerifyAX key — the kit ships no credentials.
- Set a strong `A2A_API_KEY`; the agent card is public but `message/send` requires it.
- **tools-on ⇒ sandbox only** (see `sandbox/README.md`); rotate the CLI auth after such a run.
- Raise the VerifyAX agent `timeout` for tools-on / Opus (headless cold-start per turn).
