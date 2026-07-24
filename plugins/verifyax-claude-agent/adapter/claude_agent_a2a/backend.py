"""ClaudeCodeBackend — wraps a local Claude Code agent (headless ``claude -p``)
as a turn-by-turn backend so it can be driven over A2A and evaluated by VerifyAX.

Each A2A ``context_id`` maps to one resumable Claude Code session (``--resume``),
so a multi-turn evaluation keeps conversation state. Run it in the user's project
directory so it loads THEIR ``CLAUDE.md`` + memory — i.e. *their* agent, not a
generic Claude.

Modes:
  tools="off" (default) -> ``--allowedTools ""`` : pure conversation, zero blast
      radius, no sandbox required.
  tools="on"            -> ``--dangerously-skip-permissions`` : autonomous tool
      use. ONLY run inside an isolated sandbox (see ``sandbox/``) — in an
      automated eval there is no human to approve tool calls, and adversarial
      scenarios can drive real, destructive actions.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil

logger = logging.getLogger(__name__)


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

    def _build_cmd(self, text: str, session_id: str | None) -> list[str]:
        cmd = [
            self._claude, "-p", text,
            "--output-format", "json",
            "--model", self._model,
        ]
        if session_id:
            cmd += ["--resume", session_id]
        if self._tools == "off":
            cmd += ["--allowedTools", ""]  # grant nothing -> pure conversation
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
            cmd = self._build_cmd(text, self._sessions.get(context_id))
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=self._project_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except FileNotFoundError as exc:
                raise ClaudeAgentError(
                    f"Could not launch {self._claude!r}. Is the Claude Code CLI "
                    "installed and on PATH?"
                ) from exc

            try:
                out, err = await asyncio.wait_for(
                    proc.communicate(), self._turn_timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                raise ClaudeAgentError(
                    f"Claude agent timed out after {self._turn_timeout}s "
                    "(raise turn_timeout or the VerifyAX agent timeout)."
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

            if data.get("is_error"):
                raise ClaudeAgentError(
                    str(data.get("result") or "claude reported an error")
                )
            sid = data.get("session_id")
            if sid:
                self._sessions[context_id] = sid
            reply = data.get("result")
            if not reply:
                raise ClaudeAgentError("Claude agent returned an empty reply.")
            return reply

    async def aclose(self) -> None:
        return None
