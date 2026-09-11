import asyncio
import json
import os
import unittest
import unittest.mock as mock

from claude_agent_a2a.backend import ClaudeAgentError, ClaudeCodeBackend


class _Process:
    pid = 123
    returncode = 0

    def __init__(self, payload=None):
        self.payload = payload or {"session_id": "session-1", "result": "reply"}
        self.input = None

    async def communicate(self, input=None):
        self.input = input
        return json.dumps(self.payload).encode(), b""

    async def wait(self):
        return self.returncode


class _TimeoutProcess(_Process):
    async def communicate(self, input=None):
        raise asyncio.TimeoutError


class BackendTests(unittest.IsolatedAsyncioTestCase):
    def test_tools_off_is_fail_closed(self):
        backend = ClaudeCodeBackend(claude_bin="/bin/claude", tools="off")
        cmd = backend._build_cmd(None)

        self.assertEqual(cmd[cmd.index("--tools") + 1], "")
        self.assertIn("--strict-mcp-config", cmd)
        self.assertEqual(cmd[cmd.index("--mcp-config") + 1], '{"mcpServers":{}}')
        self.assertIn("--disable-slash-commands", cmd)
        self.assertNotIn("--dangerously-skip-permissions", cmd)
        self.assertNotIn("--disallowedTools", cmd)

    def test_tools_on_requires_sandbox_marker(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "tools-on refused"):
                ClaudeCodeBackend(tools="on")

    def test_extra_args_cannot_override_tools_off(self):
        for option in ("--tools=default", "--mcp-config", "--dangerously-skip-permissions"):
            with self.subTest(option=option):
                with self.assertRaisesRegex(ValueError, "cannot override"):
                    ClaudeCodeBackend(tools="off", extra_args=[option])

    async def test_prompt_uses_stdin_and_session_is_resumed(self):
        first = _Process()
        second = _Process({"session_id": "session-1", "result": "again"})
        create = mock.AsyncMock(side_effect=[first, second])
        backend = ClaudeCodeBackend(claude_bin="/bin/claude", tools="off")

        with mock.patch("asyncio.create_subprocess_exec", create):
            self.assertEqual(await backend.send_and_wait("ctx", "--dangerous"), "reply")
            self.assertEqual(await backend.send_and_wait("ctx", "next"), "again")

        self.assertEqual(first.input, b"--dangerous")
        first_cmd = create.await_args_list[0].args
        second_cmd = create.await_args_list[1].args
        self.assertNotIn("--dangerous", first_cmd)
        self.assertEqual(second_cmd[second_cmd.index("--resume") + 1], "session-1")

    async def test_context_caches_remain_bounded(self):
        backend = ClaudeCodeBackend(claude_bin="/bin/claude")
        backend._sessions = {f"ctx-{i}": f"sid-{i}" for i in range(513)}
        backend._locks = {key: asyncio.Lock() for key in backend._sessions}

        backend._evict_stale("ctx-512")

        self.assertLessEqual(len(backend._sessions), 512)
        self.assertLessEqual(len(backend._locks), 512)

    async def test_timeout_kills_and_reaps_process_tree(self):
        process = _TimeoutProcess()
        backend = ClaudeCodeBackend(
            claude_bin="/bin/claude", turn_timeout=0.01
        )

        with (
            mock.patch(
                "asyncio.create_subprocess_exec",
                new=mock.AsyncMock(return_value=process),
            ),
            mock.patch(
                "claude_agent_a2a.backend._kill_tree", new=mock.AsyncMock()
            ) as kill_tree,
        ):
            with self.assertRaisesRegex(ClaudeAgentError, "timed out"):
                await backend.send_and_wait("ctx", "prompt")

        kill_tree.assert_awaited_once_with(process)


if __name__ == "__main__":
    unittest.main()
