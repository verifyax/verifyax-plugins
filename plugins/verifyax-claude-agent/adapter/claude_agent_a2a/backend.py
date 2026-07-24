"""ClaudeCodeBackend — wraps a local Claude Code agent (headless ``claude -p``)
as a turn-by-turn backend so it can be driven over A2A and evaluated by VerifyAX.

Each A2A ``context_id`` maps to one resumable Claude Code session (``--resume``),
so a multi-turn evaluation keeps conversation state. Run it in the user's project
directory so it loads THEIR ``CLAUDE.md`` + memory — i.e. *their* agent, not a
generic Claude.

Modes:
  tools="off" (default) -> ``--disallowedTools <all built-in tools>`` +
      ``--strict-mcp-config`` : pure conversation, no host access, no sandbox
      required. (``--allowedTools`` does NOT stop execution — only disallowing does;
      ``--strict-mcp-config`` keeps the project's MCP tools from loading.)
  tools="on"            -> ``--dangerously-skip-permissions`` : autonomous tool
      use. ONLY run inside an isolated sandbox (see ``sandbox/``) — in an
      automated eval there is no human to approve tool calls, and adversarial
      scenarios can drive real, destructive actions.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import shutil
import signal
import subprocess

logger = logging.getLogger(__name__)


# Built-in tools removed in tools-off mode so the agent genuinely can't act on or
# read the host (pure conversation). NOTE: --allowedTools does NOT disable tools —
# only --disallowedTools removes availability (verified). Kept comprehensive.
_OFF_DISALLOWED_TOOLS = [
    "Task", "Bash", "BashOutput", "KillShell", "KillBash",
    "Glob", "Grep", "Read", "Edit", "Write", "NotebookEdit",
    "WebFetch", "WebSearch", "TodoWrite", "SlashCommand",
    "ExitPlanMode", "EnterPlanMode", "AskUserQuestion", "Skill",
    "TaskOutput", "TaskCreate", "TaskUpdate", "TaskGet", "TaskList", "TaskStop",
    "ListMcpResources", "ReadMcpResource",
]
# --disallowedTools ignores unknown names, so over-listing is safe and future-proofs
# against renames. MCP tools are named dynamically (mcp__*) and can't be enumerated —
# they're neutralized separately via --strict-mcp-config in _build_cmd. tools-off thus
# denies the full built-in set + blocks MCP; the sandbox remains the hard boundary.

# Bound the per-context session/lock caches so a long-lived server doesn't grow
# without limit.
_MAX_CONTEXTS = 512


async def _kill_tree(proc) -> None:
    """Kill the subprocess AND its children — the `claude` CLI spawns its own
    process tree, which a bare ``proc.kill()`` would orphan. Async so the Windows
    taskkill doesn't block the event loop."""
    try:
        if os.name == "nt":
            killer = await asyncio.create_subprocess_exec(
                "taskkill", "/F", "/T", "/PID", str(proc.pid),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await killer.wait()
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        with contextlib.suppress(Exception):
            proc.kill()


class ClaudeAgentError(RuntimeError):
    """The Claude Code agent failed to produce a reply."""


class ClaudeCodeBackend:
    """Backend protocol impl: ``send_and_wait(context_id, text) -> reply``."""

    def __init__(
        self,
        *,
        project_dir: str | None = None,
        model: str = "claude-opus-4-8",
        tools: str = "off",
        claude_bin: str = "claude",
        turn_timeout: float = 240.0,
        extra_args: list[str] | None = None,
    ) -> None:
        if tools not in ("off", "on"):
            raise ValueError("tools must be 'off' or 'on'")
        # Enforced gate: autonomous tool use (no human approval) is refused unless
        # the disposable sandbox marker is set. In an automated eval, adversarial
        # scenarios can drive destructive / exfiltration actions — so tools-on must
        # never run by accident on a real machine. The sandbox image sets
        # CVX_SANDBOX_CONFIRMED=1; set it yourself only if you fully accept the risk.
        _confirmed = os.environ.get("CVX_SANDBOX_CONFIRMED", "").strip().lower() in (
            "1", "true", "yes", "on",
        )
        if tools == "on" and not _confirmed:
            raise ValueError(
                "tools-on refused: run it only inside the disposable sandbox "
                "(sets CVX_SANDBOX_CONFIRMED=1). Automated evals have no human to "
                "approve tool calls and adversarial scenarios can drive destructive "
                "or data-exfiltration actions. Use tools-off, or the sandbox."
            )
        self._project_dir = project_dir or os.getcwd()
        self._model = model
        self._tools = tools
        self._claude = shutil.which(claude_bin) or claude_bin
        self._turn_timeout = turn_timeout
        self._extra_args = list(extra_args or [])
        # context_id -> Claude Code session id (for --resume multi-turn state)
        self._sessions: dict[str, str] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, context_id: str) -> asyncio.Lock:
        lock = self._locks.get(context_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[context_id] = lock
        return lock

    def _evict_stale(self, current: str) -> None:
        # Bound the caches WITHOUT evicting a context that has an in-flight turn
        # (its lock is held) — doing so would let a parallel turn create a fresh
        # lock and race --resume updates. Runs synchronously (no await), so it can't
        # interleave with another coroutine mid-eviction.
        if len(self._sessions) > _MAX_CONTEXTS:
            for k in list(self._sessions):
                lk = self._locks.get(k)
                if k != current and (lk is None or not lk.locked()):
                    self._sessions.pop(k, None)
                    self._locks.pop(k, None)
                    break
        # Also drop stray free locks for contexts that never stored a session.
        if len(self._locks) > _MAX_CONTEXTS:
            for k in list(self._locks):
                if k != current and k not in self._sessions and not self._locks[k].locked():
                    self._locks.pop(k, None)
                    if len(self._locks) <= _MAX_CONTEXTS:
                        break

    def _build_cmd(self, session_id: str | None) -> list[str]:
        # The prompt is fed on STDIN, never as an argv positional — otherwise turn
        # text starting with '-' is parsed as CLI options (breaks the turn) and
        # injects flags into the same argv that carries the security flags. So argv
        # holds only trusted flags.
        cmd = [self._claude, "-p", "--output-format", "json", "--model", self._model]
        if session_id:
            cmd += ["--resume", session_id]
        if self._tools == "off":
            # Remove tool AVAILABILITY (not just auto-approval): --allowedTools does
            # NOT stop execution, --disallowedTools does. --strict-mcp-config keeps
            # the project's/user's MCP servers (dynamically-named mcp__* tools the
            # static list can't cover) from loading — a genuine no-host-access mode.
            cmd += ["--strict-mcp-config", "--disallowedTools", *_OFF_DISALLOWED_TOOLS]
        else:
            cmd += ["--dangerously-skip-permissions"]  # autonomous — SANDBOX ONLY
        cmd += self._extra_args
        return cmd

    async def send_and_wait(
        self, context_id: str, text: str, *, user_token: str | None = None
    ) -> str:
        """Send one turn to the Claude agent and return its reply text.

        Serialized per context so turns keep order and the resumed session id is
        never raced. ``user_token`` is accepted for Backend-protocol parity and
        ignored (the agent's identity is the local CLI auth)."""
        async with self._lock(context_id):
            cmd = self._build_cmd(self._sessions.get(context_id))
            # New process group/session so a timeout can kill claude's whole child
            # tree, not just the direct process.
            create_kwargs = (
                {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                if os.name == "nt"
                else {"start_new_session": True}
            )
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=self._project_dir,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    **create_kwargs,
                )
            except FileNotFoundError as exc:
                raise ClaudeAgentError(
                    f"Could not launch {self._claude!r}. Is the Claude Code CLI "
                    "installed and on PATH?"
                ) from exc

            try:
                out, err = await asyncio.wait_for(
                    proc.communicate(input=text.encode("utf-8")), self._turn_timeout
                )
            except asyncio.TimeoutError:
                # Kill claude's whole process tree (it spawns children), then reap
                # so nothing lingers as a zombie / leaks PIDs under --pids-limit.
                await _kill_tree(proc)
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(proc.wait(), 10)
                raise ClaudeAgentError(
                    f"Claude agent timed out after {self._turn_timeout}s "
                    "(raise turn_timeout, and keep the VerifyAX agent timeout above it)."
                )

            if proc.returncode != 0:
                detail = err.decode("utf-8", "replace")[:300]
                raise ClaudeAgentError(f"claude exited {proc.returncode}: {detail}")

            try:
                data = json.loads(out.decode("utf-8", "replace"))
            except (json.JSONDecodeError, ValueError) as exc:
                raise ClaudeAgentError(
                    f"Unparseable claude output: {out[:200]!r}"
                ) from exc

            # Store the session id BEFORE any error check so a turn that advanced
            # the session is still resumable next time.
            sid = data.get("session_id")
            if sid:
                self._sessions[context_id] = sid
                self._evict_stale(context_id)
            if data.get("is_error"):
                raise ClaudeAgentError(
                    str(data.get("result") or "claude reported an error")
                )
            reply = data.get("result")
            if not reply:
                raise ClaudeAgentError("Claude agent returned an empty reply.")
            return reply

    async def aclose(self) -> None:
        return None
