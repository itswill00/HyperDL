"""Standalone isolation checks for AGENTS.md section 10.

The module ships into /data/adb/modules/hyperdl and must not depend on the
builder machine. Two things are easy to break silently: a RUNPATH that points
back at the Termux toolchain, and stdlib modules that were never pruned from
the bundled Python zip. Both are checked against the built artifacts when they
exist, and skipped otherwise so a fresh clone can still run the suite.
"""

import os
import re
import shutil
import struct
import subprocess
import unittest
import zipfile

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BRIDGE = os.path.join(PROJECT_DIR, "bin", "libhyperdl.so")
PY_ZIP = os.path.join(PROJECT_DIR, "runtime", "lib", "python314.zip")
TERMUX_PREFIX = "/data/data/com.termux"

# Modules no device code path can reach. asyncio is deliberately absent:
# yt-dlp's websocket downloader imports it.
PRUNED_STDLIB = (
    "tkinter",
    "idlelib",
    "turtledemo",
    "pydoc_data",
    "ensurepip",
    "unittest/",
    "venv/",
    "distutils/",
    "lib2to3/",
    "test/",
)


def readelf_dynamic(path):
    """Return the raw output of `readelf -d`, or None when readelf is absent."""
    if not shutil.which("readelf"):
        return None
    out = subprocess.run(
        ["readelf", "-d", path], capture_output=True, text=True, timeout=30
    )
    return out.stdout


class TestBridgeIsolation(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(BRIDGE), "bridge not built yet")
    def test_no_termux_runpath(self):
        dynamic = readelf_dynamic(BRIDGE)
        if dynamic is None:
            self.skipTest("readelf unavailable")
        for line in dynamic.splitlines():
            if "PATH" not in line.upper():
                continue
            self.assertNotIn(
                TERMUX_PREFIX,
                line,
                "bridge must not resolve libraries through the Termux toolchain",
            )

    @unittest.skipUnless(os.path.exists(BRIDGE), "bridge not built yet")
    def test_bridge_needs_only_android_core_libraries(self):
        dynamic = readelf_dynamic(BRIDGE)
        if dynamic is None:
            self.skipTest("readelf unavailable")
        needed = re.findall(r"Shared library: \[(.+?)\]", dynamic)
        allowed = {"libc.so", "libdl.so", "libm.so", "liblog.so", "libandroid.so"}
        self.assertTrue(needed, "bridge declares no NEEDED entries")
        self.assertEqual(
            set(needed) - allowed,
            set(),
            "bridge links libraries the module does not bundle",
        )

    @unittest.skipUnless(os.path.exists(BRIDGE), "bridge not built yet")
    def test_bridge_is_aarch64(self):
        with open(BRIDGE, "rb") as f:
            header = f.read(20)
        self.assertEqual(header[:4], b"\x7fELF", "bridge is not an ELF")
        self.assertEqual(header[4], 2, "bridge must be 64-bit")
        self.assertEqual(struct.unpack("<H", header[18:20])[0], 183, "bridge must be aarch64")


class TestBundledStdlib(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(PY_ZIP), "runtime not bundled yet")
    def test_pruned_modules_are_absent(self):
        with zipfile.ZipFile(PY_ZIP) as z:
            names = z.namelist()
        leaked = sorted(
            n for n in names if any(n.startswith(m) or f"/{m}" in n for m in PRUNED_STDLIB)
        )
        self.assertEqual(leaked, [], f"stdlib zip still carries pruned modules: {leaked}")

    @unittest.skipUnless(os.path.exists(PY_ZIP), "runtime not bundled yet")
    def test_zip_holds_bytecode_only(self):
        with zipfile.ZipFile(PY_ZIP) as z:
            names = z.namelist()
        sources = [n for n in names if n.endswith(".py")]
        self.assertEqual(sources, [], f"stdlib zip ships source files: {sources[:5]}")

    @unittest.skipUnless(os.path.exists(PY_ZIP), "runtime not bundled yet")
    def test_zip_has_no_empty_entries(self):
        with zipfile.ZipFile(PY_ZIP) as z:
            empties = [i.filename for i in z.infolist() if i.file_size == 0]
        self.assertEqual(empties, [], "stdlib zip contains empty files")

    @unittest.skipUnless(os.path.exists(PY_ZIP), "runtime not bundled yet")
    def test_core_modules_survive_pruning(self):
        # asyncio is required by yt-dlp's websocket downloader; the rest are
        # imported on the normal download path.
        required = (
            "asyncio/",
            "json/",
            "urllib/",
            "http/",
            "ssl.pyc",
            "sqlite3/",
            "zipfile/",
            "subprocess.pyc",
        )
        with zipfile.ZipFile(PY_ZIP) as z:
            names = z.namelist()
        missing = [r for r in required if not any(r in n for n in names)]
        self.assertEqual(missing, [], f"stdlib zip lost required modules: {missing}")


class TestRuntimeSourcesStayClean(unittest.TestCase):
    RUNTIME_FILES = (
        "src/main.c",
        "engine/_impl.py",
        "src/sitecustomize.py",
        "bin/hyperdl_daemon",
        "webui/src/helpers/shell.js",
    )

    def test_no_termux_paths_in_runtime_code(self):
        offenders = []
        for rel in self.RUNTIME_FILES:
            path = os.path.join(PROJECT_DIR, rel)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8", errors="ignore") as f:
                if TERMUX_PREFIX in f.read():
                    offenders.append(rel)
        self.assertEqual(offenders, [], "runtime code must not reference Termux paths")


if __name__ == "__main__":
    unittest.main(verbosity=2)
