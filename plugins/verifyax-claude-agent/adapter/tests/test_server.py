import os
import unittest
import unittest.mock as mock

from a2a.utils import DEFAULT_RPC_URL
from starlette.testclient import TestClient

from claude_agent_a2a.server import create_app


class _Backend:
    async def send_and_wait(self, context_id, text, *, user_token=None):
        return "reply"


class ServerTests(unittest.TestCase):
    def test_auth_is_required_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "No inbound auth configured"):
                create_app(_Backend())

    def test_false_like_no_auth_value_does_not_disable_auth(self):
        with mock.patch.dict(os.environ, {"A2A_ALLOW_NO_AUTH": "0"}, clear=True):
            with self.assertRaises(RuntimeError):
                create_app(_Backend())

    def test_agent_card_is_public_but_rpc_requires_bearer(self):
        with mock.patch.dict(os.environ, {"A2A_API_KEY": "correct-token"}, clear=True):
            client = TestClient(create_app(_Backend()))
            card = client.get("/.well-known/agent-card.json")
            unauthorized = client.post("/", json={})
            authorized = client.post(
                "/", json={}, headers={"Authorization": "Bearer correct-token"}
            )

        self.assertEqual(card.status_code, 200)
        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(unauthorized.headers["www-authenticate"], "Bearer")
        self.assertNotEqual(authorized.status_code, 401)

    def test_forwarded_host_is_validated_before_advertising(self):
        with mock.patch.dict(os.environ, {"A2A_ALLOW_NO_AUTH": "1"}, clear=True):
            client = TestClient(create_app(_Backend()))
            valid = client.get(
                "/.well-known/agent-card.json",
                headers={"x-forwarded-proto": "https", "x-forwarded-host": "agent.example:443"},
            )
            invalid = client.get(
                "/.well-known/agent-card.json",
                headers={"x-forwarded-proto": "javascript", "x-forwarded-host": "evil.test/path"},
            )

        valid_url = valid.json()["supportedInterfaces"][0]["url"]
        invalid_url = invalid.json()["supportedInterfaces"][0]["url"]
        self.assertEqual(valid_url, "https://agent.example:443" + DEFAULT_RPC_URL)
        self.assertNotIn("evil.test", invalid_url)
        self.assertNotIn("javascript:", invalid_url)


if __name__ == "__main__":
    unittest.main()
