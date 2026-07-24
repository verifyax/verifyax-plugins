# Tools-on sandbox

Run the adapter with **`CLAUDE_TOOLS=on`** only inside this disposable container.
In an automated VerifyAX eval there is no human to approve tool calls, and
adversarial scenarios can drive real destructive actions or exfiltrate anything in
the agent's context. Treat this box as throwaway.

## Build
```
docker build -t claude-verifyax-sandbox -f sandbox/Dockerfile .
```

## Authenticate the Claude CLI inside (one-time, interactive)
```
docker run -it --rm --name cvx-auth claude-verifyax-sandbox claude /login
# ...or commit an authenticated image; do NOT bake credentials into the Dockerfile.
```
Prefer authenticating *inside* the container over mounting your host `~/.claude`:
with tools-on, a coaxed agent could read and exfiltrate mounted credentials.

## Run (safe flags)
```
docker run --rm -p 127.0.0.1:8091:8091 \
  -e A2A_API_KEY="<long-random>" \
  -e CLAUDE_MODEL="claude-opus-4-8" \
  -v "$(pwd)/redacted-project:/work:rw" \
  --read-only --tmpfs /tmp \
  --cap-drop ALL \
  --pids-limit 256 --memory 2g \
  claude-verifyax-sandbox
```

## Hardening checklist
- **Redacted project** mounted at `/work` — no real secrets in `CLAUDE.md`/memory
  (adversarial scenarios will try to extract them).
- **No production credentials** in the container env.
- **Restrict egress** to only what's needed (the model endpoint + VerifyAX + your
  tunnel). Easiest: put the container on a locked-down Docker network / host
  firewall; or run it on a throwaway VM.
- **Disposable:** `--rm`, and rebuild fresh next time.
- After a run, treat the CLI auth token as potentially exposed and **rotate** it.

## Expose to VerifyAX
Run your tunnel against `127.0.0.1:8091` (e.g. `cloudflared tunnel --url http://127.0.0.1:8091`)
and give the public URL to the `verifyax-api` skill (via `connect-to-verifyax`) to register + run.
