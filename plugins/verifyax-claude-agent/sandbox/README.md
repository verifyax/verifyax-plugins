# Tools-on sandbox

Run the adapter with **`CLAUDE_TOOLS=on`** only inside this disposable container.
In an automated VerifyAX eval there is no human to approve tool calls, and
adversarial scenarios can drive real destructive actions or exfiltrate anything in
the agent's context. Treat this box as throwaway.

## Build
```
docker build -t claude-verifyax-sandbox -f sandbox/Dockerfile .
```

## Run (ephemeral, read-only, network-denied by default)
Use the checked-in launcher. It mounts the redacted project read-only, creates a
dedicated writable `/scratch` tmpfs, uses an ephemeral home, drops all capabilities,
and attaches to no network unless you explicitly provide a restricted one:
```
chmod +x sandbox/run.sh
A2A_API_KEY="<long-random>" sandbox/run.sh "$(pwd)/redacted-project"
# then, inside the container:
claude /login     # ephemeral auth — lives only for this container's lifetime
python -m uvicorn claude_agent_a2a.server:get_app --factory --host 0.0.0.0 --port 8091
```
With the default `none` network, login and model calls intentionally cannot work.
For a live evaluation, put an allow-listing HTTPS proxy on an internal Docker
network, permit only the model/auth and required VerifyAX/tunnel destinations,
then mark that network only after the policy is active:
```
docker network create --internal verifyax-eval
# Attach a separately administered allow-list proxy to verifyax-eval and egress.
docker network update --label-add com.verifyax.egress-restricted=true verifyax-eval
CVX_SANDBOX_NETWORK=verifyax-eval HTTPS_PROXY=http://egress-proxy:3128 \
  A2A_API_KEY="<long-random>" sandbox/run.sh "$(pwd)/redacted-project"
```
The launcher refuses Docker's unrestricted default network and refuses any custom
network without that explicit label. The tmpfs home and scratch space are discarded
with the container. Re-authenticate for each run; never mount host `~/.claude`.

## Hardening checklist
- **Redacted project** mounted at `/work` — no real secrets in `CLAUDE.md`/memory
  (adversarial scenarios will try to extract them).
- **No production credentials** in the container env.
- **Restrict egress** with the launcher plus an allow-list proxy/firewall. The label
  is an operator assertion; apply it only after verifying the actual network policy.
- **Disposable:** `--rm`, and rebuild fresh next time.
- After a run, treat the CLI auth token as potentially exposed and **rotate** it.
- **tools-on gate:** this image sets `CVX_SANDBOX_CONFIRMED=1` — that's what lets the adapter
  run tools-on. Outside this image the adapter refuses tools-on, so don't set that var elsewhere.
- The bundled tunnel downloader pins cloudflared and per-platform SHA-256 values.
  A custom `CLOUDFLARED_VERSION` is accepted only with `CLOUDFLARED_SHA256`.

## Expose to VerifyAX
Run your tunnel against `127.0.0.1:8091` (e.g. `cloudflared tunnel --url http://127.0.0.1:8091`)
and give the public URL to the `verifyax-api` skill (via `connect-to-verifyax`) to register + run.
