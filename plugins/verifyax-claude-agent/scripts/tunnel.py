#!/usr/bin/env python3
"""Open a public HTTPS tunnel to the local adapter so VerifyAX (cloud) can reach it.

Ensures `cloudflared` is available (uses one on PATH, else downloads the right
release into a cache dir), starts a Quick Tunnel to the given local port, prints
the public URL as `TUNNEL_URL=https://...trycloudflare.com`, then stays running to
keep the tunnel alive. The connect-to-verifyax skill runs this in the background
and reads that line — so users don't have to install or manage a tunnel.

    python tunnel.py --port 8091

Stop it by killing the process (the skill does this at cleanup).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
_PINNED_VERSION = "2026.8.3"
# SHA-256 of the *installed executable* (extracted `cloudflared` / `.exe`).
# For Darwin the GitHub asset is a `.tgz`, so this is NOT the archive digest.
_PINNED_BINARY_SHA256 = {
    "cloudflared-darwin-amd64.tgz": "936aa4ed783b0e191fac48e7140c34605b25d8d5c0495c3599c90e350ae6e4c4",
    "cloudflared-darwin-arm64.tgz": "50a04624531e7a98ddb65f1223905e32f84e7488ed3ee8dadcd3260aa8932603",
    "cloudflared-linux-amd64": "f29324fe934d1e100617484c78deef803c4dc2cd351d645bbde42e96b4fccc5e",
    "cloudflared-linux-arm64": "4bcfd35521a7cbc545ebfd5d57334a71ee180e2a64874981f374c81472118391",
    "cloudflared-windows-amd64.exe": "83e726ed18ea78c5ad5213c4c3a3a27051393950d2bc8ed4de69bec12d14eaae",
}
# SHA-256 of the GitHub release *archive* (Darwin `.tgz` only). Linux/Windows
# assets are already the raw binary, so they are checked via _PINNED_BINARY_SHA256.
_PINNED_ASSET_SHA256 = {
    "cloudflared-darwin-amd64.tgz": "61e1316266a00fd70ce40da011d612badc805367fb65293dd1925f938f704c99",
    "cloudflared-darwin-arm64.tgz": "40c9144d86df8937c5b43293a1f7d2d2107029aa74725023dd46b1b27154352f",
}


def _release_base() -> str:
    """Return an immutable release URL; custom versions require a custom digest."""
    ver = os.environ.get("CLOUDFLARED_VERSION", "").strip() or _PINNED_VERSION
    if ver != _PINNED_VERSION and not os.environ.get("CLOUDFLARED_SHA256", "").strip():
        sys.exit("A custom CLOUDFLARED_VERSION requires CLOUDFLARED_SHA256.")
    return f"https://github.com/cloudflare/cloudflared/releases/download/{ver}/"


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _expected_binary_sha(asset_name: str) -> str:
    override = os.environ.get("CLOUDFLARED_SHA256", "").strip().lower()
    if override:
        return override
    try:
        return _PINNED_BINARY_SHA256[asset_name]
    except KeyError:
        sys.exit(f"Unsupported cloudflared platform asset: {asset_name}")


def _verify_sha(path: str, expected: str, *, remove_on_fail: bool = False) -> None:
    """Verify every executable/cache hit, failing closed on any mismatch."""
    digest = _sha256(path)
    if digest != expected:
        if remove_on_fail:
            with contextlib.suppress(OSError):
                os.remove(path)
        sys.exit(f"cloudflared checksum mismatch at {path}: expected {expected}, got {digest}")


def _asset() -> tuple[str, str]:
    """Return (release asset name, kind) for this OS/arch. kind: exe|tgz|bin."""
    sysname = platform.system().lower()
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "amd64" if machine in ("x86_64", "amd64") else machine
    if sysname == "windows":
        return f"cloudflared-windows-{arch}.exe", "exe"
    if sysname == "darwin":
        return f"cloudflared-darwin-{arch}.tgz", "tgz"
    return f"cloudflared-linux-{arch}", "bin"


def _ensure_cloudflared(cache_dir: str) -> str:
    name, kind = _asset()
    expected = _expected_binary_sha(name)
    on_path = shutil.which("cloudflared")
    if on_path:
        _verify_sha(on_path, expected)
        return on_path
    version = os.environ.get("CLOUDFLARED_VERSION", "").strip() or _PINNED_VERSION
    cache_dir = os.path.join(cache_dir, version)
    os.makedirs(cache_dir, mode=0o700, exist_ok=True)
    exe = os.path.join(cache_dir, "cloudflared.exe" if kind == "exe" else "cloudflared")
    if os.path.exists(exe):
        _verify_sha(exe, expected, remove_on_fail=True)
        return exe
    url = _release_base() + name
    dl = os.path.join(cache_dir, name)
    print(f"Downloading cloudflared ({name})...", file=sys.stderr, flush=True)
    urllib.request.urlretrieve(url, dl)
    if kind == "tgz":
        asset_sha = _PINNED_ASSET_SHA256.get(name)
        if asset_sha and version == _PINNED_VERSION:
            _verify_sha(dl, asset_sha, remove_on_fail=True)
        with tarfile.open(dl) as tf:
            member = next((m for m in tf.getmembers() if m.name.rsplit("/", 1)[-1] == "cloudflared"), None)
            if member is None:
                sys.exit("cloudflared binary not found in the downloaded archive.")
            if not member.isreg():
                sys.exit("unexpected cloudflared archive member type (not a regular file).")
            member.name = "cloudflared"
            tf.extract(member, cache_dir)
        os.remove(dl)
    else:
        os.replace(dl, exe)
    if kind in ("tgz", "bin"):
        os.chmod(exe, os.stat(exe).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    # Integrity: verify the INSTALLED binary (consistent across download/cache/PATH),
    # print its SHA256 (auditable), and enforce the source-controlled platform pin.
    print(f"cloudflared SHA256={_sha256(exe)}", file=sys.stderr, flush=True)
    _verify_sha(exe, expected, remove_on_fail=True)
    return exe


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8091)
    ap.add_argument(
        "--cache-dir",
        default=os.path.join(tempfile.gettempdir(), "verifyax-cloudflared"),
        help="Where to cache a downloaded cloudflared binary.",
    )
    args = ap.parse_args()

    cf = _ensure_cloudflared(args.cache_dir)
    proc = subprocess.Popen(
        [cf, "tunnel", "--url", f"http://127.0.0.1:{args.port}", "--no-autoupdate"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    printed = False
    assert proc.stdout is not None
    for line in proc.stdout:
        if not printed:
            m = _URL_RE.search(line)
            if m:
                print(f"TUNNEL_URL={m.group(0)}", flush=True)
                printed = True
        # keep draining so the pipe never blocks and the tunnel stays up
    return proc.wait()


if __name__ == "__main__":
    raise SystemExit(main())
