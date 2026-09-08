#!/bin/sh
set -eu

project=${1:-}
network=${CVX_SANDBOX_NETWORK:-none}
image=${CVX_SANDBOX_IMAGE:-claude-verifyax-sandbox}

if [ -z "$project" ] || [ ! -d "$project" ]; then
  echo "usage: A2A_API_KEY=... $0 /path/to/redacted-project" >&2
  exit 2
fi
if [ -z "${A2A_API_KEY:-}" ]; then
  echo "A2A_API_KEY is required." >&2
  exit 2
fi

# Never silently attach an autonomous agent to Docker's unrestricted default
# network. A usable egress network must be explicitly marked after its firewall
# or allow-list policy has been configured by the operator.
if [ "$network" != "none" ]; then
  restricted=$(
    docker network inspect "$network" \
      --format '{{ index .Labels "com.verifyax.egress-restricted" }}' 2>/dev/null || true
  )
  if [ "$restricted" != "true" ]; then
    echo "Refusing network '$network': it lacks com.verifyax.egress-restricted=true." >&2
    echo "Configure an allow-listed egress network, label it, then set CVX_SANDBOX_NETWORK." >&2
    exit 2
  fi
fi

exec docker run -it --rm \
  --network "$network" \
  -p 127.0.0.1:8091:8091 \
  -e A2A_API_KEY \
  -e CLAUDE_MODEL="${CLAUDE_MODEL:-claude-opus-4-8}" \
  -e HTTPS_PROXY="${HTTPS_PROXY:-}" \
  -e NO_PROXY="${NO_PROXY:-127.0.0.1,localhost}" \
  -v "$(cd "$project" && pwd):/work:ro" \
  --tmpfs /home/agent:rw,nosuid,nodev,noexec,mode=700,uid=1000,gid=1000 \
  --tmpfs /scratch:rw,nosuid,nodev,mode=700,uid=1000,gid=1000 \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --pids-limit 256 \
  --memory 2g \
  "$image" bash
