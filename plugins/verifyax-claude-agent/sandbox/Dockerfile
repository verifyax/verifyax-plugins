# Disposable sandbox for running the Claude agent adapter with TOOLS ON.
# Tools-on lets the agent auto-run Bash/Edit/etc. during an automated eval with
# no human approval, and VerifyAX runs adversarial scenarios — so this MUST be a
# throwaway container with no real data/credentials and restricted egress.
#
# Build (from repo root):   docker build -t claude-verifyax-sandbox -f sandbox/Dockerfile .
# Run (see sandbox/README.md for the safe flags).

FROM node:20-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip ca-certificates git curl \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI (the engine that makes the agent "them").
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app
COPY adapter/ /app/adapter/
RUN pip3 install --no-cache-dir --break-system-packages -r /app/adapter/requirements.txt

# Non-root; the agent's working project is mounted read-write at /work.
RUN useradd -m agent && mkdir -p /work && chown -R agent /app /work
USER agent

ENV PYTHONPATH=/app/adapter \
    CLAUDE_TOOLS=on \
    CVX_SANDBOX_CONFIRMED=1 \
    CLAUDE_PROJECT_DIR=/work \
    CLAUDE_MODEL=claude-opus-4-8
WORKDIR /work
EXPOSE 8091

# A2A_API_KEY must be provided at run time. The Claude CLI must be authenticated
# inside the container (see README) before the adapter can answer.
CMD ["python3", "-m", "uvicorn", "claude_agent_a2a.server:get_app", \
     "--factory", "--host", "0.0.0.0", "--port", "8091", "--log-level", "warning"]
