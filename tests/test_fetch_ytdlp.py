"""Pin verification for scripts/fetch_ytdlp.py.

The build must never ship an extractor whose version it cannot read: an
unreadable archive is exactly the case where a tampered or truncated payload
would otherwise pass the gate.
"""

import importlib.util
import os
import tempfile
import unittest
import zipfile

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(PROJECT_DIR, "scripts", "fetch_ytdlp.py")


def load_script():
    spec = importlib.util.spec_from_file_location("fetch_ytdlp", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestVerifyInstalled(unittest.TestCase):
    def setUp(self):
        self.script = load_script()
        self.tmp = tempfile.mkdtemp()
        self.original_target = self.script.TARGET
        self.script.TARGET = os.path.join(self.tmp, "yt-dlp")

    def tearDown(self):
        self.script.TARGET = self.original_target
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_missing_target_fails(self):
        ok, detail = self.script.verify_installed("2026.10.21")
        self.assertFalse(ok)
        self.assertIn("missing", detail.lower())

    def test_unreadable_target_fails(self):
        with open(self.script.TARGET, "wb") as f:
            f.write(b"not a zipapp")
        ok, detail = self.script.verify_installed("2026.10.21")
        self.assertFalse(ok)
        self.assertIn("cannot determine", detail.lower())

    def test_matching_version_passes(self):
        with zipfile.ZipFile(self.script.TARGET, "w") as z:
            z.writestr("yt_dlp/version.py", "__version__ = '2026.10.21'\n")
        ok, detail = self.script.verify_installed("2026.10.21")
        self.assertTrue(ok, detail)

    def test_mismatched_version_fails(self):
        with zipfile.ZipFile(self.script.TARGET, "w") as z:
            z.writestr("yt_dlp/version.py", "__version__ = '2026.01.01'\n")
        ok, detail = self.script.verify_installed("2026.10.21")
        self.assertFalse(ok)
        self.assertIn("2026.01.01", detail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
