# Tools-on sandbox

Run the adapter with **`CLAUDE_TOOLS=on`** only inside this disposable container.
In an automated VerifyAX eval there is no human to approve tool calls, and
adversarial scenarios can drive real destructive actions or exfiltrate anything in
the agent's context. Treat this box as throwaway.

## Build
```
docker build -t claude-verifyax-sandbox -f sandbox/Dockerfile .
```

## Run (ephemeral, disposable)
Start one throwaway container with an **ephemeral** (tmpfs) home — so nothing,
including any adversarial writes, persists across runs — authenticate inside it, then
start the adapter:
```
docker run -it --rm -p 127.0.0.1:8091:8091 \
  -e A2A_API_KEY="<long-random>" \
  -e CLAUDE_MODEL="claude-opus-4-8" \
  -v "$(pwd)/redacted-project:/work:rw" \
  --tmpfs /home/agent --read-only --tmpfs /tmp \
  --cap-drop ALL --pids-limit 256 --memory 2g \
  claude-verifyax-sandbox bash
# then, inside the container:
claude /login     # ephemeral auth — lives only for this container's lifetime
python -m uvicorn claude_agent_a2a.server:get_app --factory --host 0.0.0.0 --port 8091
```
The tmpfs home is writable (so `claude --resume` works within the run) but is
**discarded with the container**, keeping the sandbox truly disposable. Auth and any
state are per-run — re-auth in each fresh container; do **not** bake credentials into
the image, and prefer this over mounting your host `~/.claude` (a coaxed agent could
read/exfiltrate mounted credentials).

## Hardening checklist
- **Redacted project** mounted at `/work` — no real secrets in `CLAUDE.md`/memory
  (adversarial scenarios will try to extract them).
- **No production credentials** in the container env.
- **Restrict egress** to only what's needed (the model endpoint + VerifyAX + your
  tunnel). Easiest: put the container on a locked-down Docker network / host
  firewall; or run it on a throwaway VM.
- **Disposable:** `--rm`, and rebuild fresh next time.
- After a run, treat the CLI auth token as potentially exposed and **rotate** it.
- **tools-on gate:** this image sets `CVX_SANDBOX_CONFIRMED=1` — that's what lets the adapter
  run tools-on. Outside this image the adapter refuses tools-on, so don't set that var elsewhere.
- Optionally pin/verify the tunnel binary via `CLOUDFLARED_VERSION` / `CLOUDFLARED_SHA256`.

## Expose to VerifyAX
Run your tunnel against `127.0.0.1:8091` (e.g. `cloudflared tunnel --url http://127.0.0.1:8091`)
and give the public URL to the `verifyax-api` skill (via `connect-to-verifyax`) to register + run.
