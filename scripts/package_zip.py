#!/usr/bin/env python3
"""Package the HyperDL module into a single Full Zip.

Written in Python because Termux no longer ships a real `zip` binary, and the
common shims only understand a subset of the flags. This keeps packaging
identical on every machine and lets us exclude build junk precisely.
"""

import os
import sys
import zipfile

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Order matters: the zip mirrors the on-device module root.
PAYLOAD = [
    "module.prop",
    "customize.sh",
    "service.sh",
    "uninstall.sh",
    "bin",
    "runtime",
    "webroot",
]

# Directories that must never end up in a flashable package.
SKIP_DIRS = {"__pycache__", ".git", ".vite", "node_modules"}
SKIP_SUFFIXES = (".pyc", ".pyo", ".log", ".tmp", ".sock", ".pid", ".map")
SKIP_PREFIXES = (".DS_Store", ".#")


def _should_skip(rel_path):
    parts = rel_path.split(os.sep)
    if any(p in SKIP_DIRS for p in parts):
        return True
    name = parts[-1]
    if name.endswith(SKIP_SUFFIXES):
        return True
    return name.startswith(SKIP_PREFIXES)


def collect(src):
    """Yield (absolute_path, archive_name) pairs under src."""
    if os.path.isfile(src):
        yield src, src
        return
    for root, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for fn in sorted(files):
            abs_p = os.path.join(root, fn)
            rel = os.path.relpath(abs_p, PROJECT_DIR)
            if _should_skip(rel):
                continue
            yield abs_p, rel


def main():
    if len(sys.argv) < 3:
        print("usage: package_zip.py <output-zip> <entry> [entry...]", file=sys.stderr)
        return 1

    out_zip = sys.argv[1]
    entries = sys.argv[2:]

    os.makedirs(os.path.dirname(out_zip) or ".", exist_ok=True)
    if os.path.exists(out_zip):
        os.remove(out_zip)

    count = 0
    raw_bytes = 0
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for entry in entries:
            for abs_p, arc in collect(entry):
                try:
                    z.write(abs_p, arc)
                    count += 1
                    raw_bytes += os.path.getsize(abs_p)
                except OSError as e:
                    print(f"warning: skipping {arc} ({e})", file=sys.stderr)

    size_mb = os.path.getsize(out_zip) / (1024 * 1024)
    print(f"packed {count} files ({raw_bytes / (1024 * 1024):.1f} MB raw) -> {size_mb:.1f} MB compressed")

    required = ["module.prop", "customize.sh", "service.sh", "uninstall.sh",
                "webroot/index.html", "bin/libhyperdl.so", "bin/hyperdl.bundle",
                "bin/hyperdl_daemon", "bin/yt-dlp", "runtime/bin/python3",
                "runtime/bin/ffmpeg", "runtime/bin/ffmpeg.bin",
                "runtime/bin/ffprobe", "runtime/bin/ffprobe.bin"]
    with zipfile.ZipFile(out_zip) as z:
        names = set(z.namelist())
    missing = [r for r in required if r not in names]
    if missing:
        print(f"error: package is incomplete, missing: {', '.join(missing)}", file=sys.stderr)
        return 1

    print(f"verified: {len(required)} required entries present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
