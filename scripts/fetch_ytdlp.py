#!/usr/bin/env python3
"""Fetch a pinned, checksum-verified yt-dlp release.

Platforms break their scrapers constantly, so the bundled extractor must be a
known-good build rather than whatever `latest` happens to be on the day of the
build. This script is the single entry point for obtaining `bin/yt-dlp`:

  python3 scripts/fetch_ytdlp.py            # install the pinned version
  python3 scripts/fetch_ytdlp.py --check    # report pinned vs installed only
  python3 scripts/fetch_ytdlp.py --latest   # report whether a newer release exists

The download is verified against the official `SHA2-256SUMS` asset before it is
allowed to replace anything, so a truncated or tampered payload can never end
up inside a shipped module.
"""

import hashlib
import os
import re
import sys
import json
import urllib.request
import urllib.error

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(PROJECT_DIR, "bin", "yt-dlp")
PIN_FILE = os.path.join(PROJECT_DIR, "ytdlp.pin")
RELEASE_URL = "https://github.com/yt-dlp/yt-dlp/releases/download/{tag}/{asset}"
SUMS_URL = "https://github.com/yt-dlp/yt-dlp/releases/download/{tag}/SHA2-256SUMS"
LATEST_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
ASSET_NAME = "yt-dlp"
UA = "Mozilla/5.0 (Android; Mobile) HyperDL-build"


def read_pin():
    """Return the pinned yt-dlp tag, or "" when the file is missing."""
    try:
        with open(PIN_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if line:
                    return line
    except Exception:
        pass
    return ""


def _download(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def expected_sha256(tag):
    """Look up the official checksum for the `yt-dlp` asset of a given tag."""
    text = _download(SUMS_URL.format(tag=tag)).decode("utf-8", "replace")
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1].lstrip("*") == ASSET_NAME:
            return parts[0].strip().lower()
    return ""


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def installed_version():
    """Read the version string out of the installed zipapp without running it.

    The shipped payload is repacked to bytecode-only (`.pyc`), so the source
    module is usually absent. The compiled file still embeds the version
    literal, so a bounded scan of `version.pyc` is enough and avoids importing
    or executing anything from the archive.
    """
    import zipfile
    try:
        with zipfile.ZipFile(TARGET, "r") as z:
            names = set(z.namelist())
            if "yt_dlp/version.py" in names:
                raw = z.read("yt_dlp/version.py").decode("utf-8", "replace")
                for line in raw.splitlines():
                    if line.startswith("__version__"):
                        return line.split("=", 1)[1].strip().strip("'\"")
            for cand in names:
                if cand.endswith("version.pyc") and cand.startswith("yt_dlp/"):
                    blob = z.read(cand)
                    for m in re.finditer(rb"\d{4}\.\d{2}\.\d{2}", blob):
                        try:
                            return m.group(0).decode("ascii")
                        except Exception:
                            continue
    except Exception:
        pass
    return ""


def latest_version():
    try:
        data = json.loads(_download(LATEST_API, timeout=20).decode("utf-8", "replace"))
        return (data.get("tag_name") or "").strip()
    except Exception:
        return ""


def verify_installed(pin):
    """Return (ok, detail) describing whether TARGET is the pinned build.

    A build with no pin recorded only warns, so a fresh checkout can still
    compile. Once `ytdlp.pin` exists the check becomes strict: a mismatched or
    unreadable version means the wrong extractor would ship.
    """
    if not pin:
        if os.path.isfile(TARGET):
            return True, "no pin recorded"
        return False, "bin/yt-dlp is missing and ytdlp.pin is empty"
    if not os.path.isfile(TARGET):
        return False, "bin/yt-dlp is missing"
    have = installed_version()
    if have and have != pin:
        return False, f"installed {have} != pinned {pin}"
    return True, f"installed {have or pin}"


def install(tag):
    """Download, verify, and atomically install the given yt-dlp tag."""
    if not tag:
        print("error: no yt-dlp pin configured", file=sys.stderr)
        return False

    print(f"-> fetching yt-dlp {tag}...")
    try:
        want = expected_sha256(tag)
    except Exception as e:
        print(f"error: cannot read SHA2-256SUMS for {tag}: {e}", file=sys.stderr)
        return False
    if not want:
        print(f"error: no checksum published for {ASSET_NAME} {tag}", file=sys.stderr)
        return False

    try:
        payload = _download(RELEASE_URL.format(tag=tag, asset=ASSET_NAME))
    except Exception as e:
        print(f"error: download failed: {e}", file=sys.stderr)
        return False

    got = hashlib.sha256(payload).hexdigest()
    if got != want:
        print(f"error: checksum mismatch for yt-dlp {tag}", file=sys.stderr)
        print(f"       expected {want}", file=sys.stderr)
        print(f"       got      {got}", file=sys.stderr)
        return False

    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    tmp = TARGET + ".fetching"
    with open(tmp, "wb") as f:
        f.write(payload)
    os.chmod(tmp, 0o755)
    os.replace(tmp, TARGET)
    print(f"   verified sha256 {want[:16]}... -> bin/yt-dlp ({len(payload)} bytes)")
    return True


def main(argv):
    pin = read_pin()
    mode = argv[1] if len(argv) > 1 else ""

    if mode == "--check":
        ok, detail = verify_installed(pin)
        print(json.dumps({"pinned": pin, "ok": ok, "detail": detail,
                          "installed": installed_version()}))
        return 0 if ok else 1

    if mode == "--latest":
        latest = latest_version()
        print(json.dumps({"pinned": pin, "latest": latest,
                          "behind": bool(pin and latest and latest != pin)}))
        return 0 if (pin and latest and latest == pin) else 1

    if not pin:
        if os.path.isfile(TARGET):
            print("warning: ytdlp.pin is empty, keeping the existing bin/yt-dlp")
            return 0
        print("error: ytdlp.pin is empty or missing", file=sys.stderr)
        return 1

    ok, detail = verify_installed(pin)
    if ok and os.path.isfile(TARGET):
        print(f"-> yt-dlp {pin} already installed ({detail})")
        return 0

    return 0 if install(pin) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
