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


def _release_base() -> str:
    """cloudflared release base URL. Pin with CLOUDFLARED_VERSION; else 'latest'."""
    ver = os.environ.get("CLOUDFLARED_VERSION", "").strip()
    if ver:
        return f"https://github.com/cloudflare/cloudflared/releases/download/{ver}/"
    return "https://github.com/cloudflare/cloudflared/releases/latest/download/"


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_pin(path: str) -> None:
    """If CLOUDFLARED_SHA256 is set, verify this binary matches — applied to PATH
    hits and cached binaries too, not only fresh downloads."""
    expected = os.environ.get("CLOUDFLARED_SHA256", "").strip().lower()
    if expected:
        digest = _sha256(path)
        if digest != expected:
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
    on_path = shutil.which("cloudflared")
    if on_path:
        _verify_pin(on_path)  # verify a PATH binary too when a pin is set
        return on_path
    name, kind = _asset()
    os.makedirs(cache_dir, exist_ok=True)
    exe = os.path.join(cache_dir, "cloudflared.exe" if kind == "exe" else "cloudflared")
    if os.path.exists(exe):
        _verify_pin(exe)  # verify a cached binary too when a pin is set
        return exe
    url = _release_base() + name
    dl = os.path.join(cache_dir, name)
    print(f"Downloading cloudflared ({name})...", file=sys.stderr, flush=True)
    urllib.request.urlretrieve(url, dl)
    if kind == "tgz":
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
    # print its SHA256 (auditable), and enforce CLOUDFLARED_SHA256 if set.
    print(f"cloudflared SHA256={_sha256(exe)}", file=sys.stderr, flush=True)
    _verify_pin(exe)
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
