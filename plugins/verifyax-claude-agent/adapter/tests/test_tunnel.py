import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
import unittest.mock as mock


_TUNNEL_PATH = Path(__file__).parents[2] / "scripts" / "tunnel.py"
_SPEC = importlib.util.spec_from_file_location("verifyax_tunnel", _TUNNEL_PATH)
tunnel = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(tunnel)


class TunnelTests(unittest.TestCase):
    def test_supported_assets_have_source_controlled_binary_digests(self):
        for asset in (
            "cloudflared-darwin-amd64.tgz",
            "cloudflared-darwin-arm64.tgz",
            "cloudflared-linux-amd64",
            "cloudflared-linux-arm64",
            "cloudflared-windows-amd64.exe",
        ):
            self.assertRegex(tunnel._PINNED_BINARY_SHA256[asset], r"^[0-9a-f]{64}$")
        # Darwin GitHub assets are archives; binary and archive digests must differ.
        for archive in (
            "cloudflared-darwin-amd64.tgz",
            "cloudflared-darwin-arm64.tgz",
        ):
            self.assertNotEqual(
                tunnel._PINNED_BINARY_SHA256[archive],
                tunnel._PINNED_ASSET_SHA256[archive],
            )

    def test_release_url_is_immutable_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                tunnel._release_base(),
                "https://github.com/cloudflare/cloudflared/releases/download/2026.8.3/",
            )

    def test_custom_version_requires_checksum(self):
        with mock.patch.dict(
            os.environ, {"CLOUDFLARED_VERSION": "future-version"}, clear=True
        ):
            with self.assertRaises(SystemExit):
                tunnel._release_base()

    def test_checksum_mismatch_fails_closed_and_removes_cache_file(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "cloudflared"
            candidate.write_bytes(b"tampered")
            with self.assertRaises(SystemExit):
                tunnel._verify_sha(
                    str(candidate), "0" * 64, remove_on_fail=True
                )
            self.assertFalse(candidate.exists())


if __name__ == "__main__":
    unittest.main()
