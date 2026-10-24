"""Argument handling for scripts/bump_version.py.

The script writes to every versioned file as soon as parsing succeeds, so a
mistyped flag used to bump the version anyway. These tests pin the contract
that nothing reaches disk unless every argument is understood.
"""

import io
import os
import sys
import importlib.util
import unittest
from contextlib import redirect_stdout, redirect_stderr

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(PROJECT_DIR, "scripts", "bump_version.py")

spec = importlib.util.spec_from_file_location("bump_version", SCRIPT)
bump_version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bump_version)


class BumpVersionArgTests(unittest.TestCase):
    def parse(self, argv):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return bump_version.parse_args(argv)

    def parse_fails(self, argv):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                bump_version.parse_args(argv)
        return ctx.exception.code

    def test_no_arguments_defaults_to_patch(self):
        self.assertEqual(self.parse([]), ("patch", None, None))

    def test_bump_types_are_accepted(self):
        for kind in ("patch", "minor", "major"):
            self.assertEqual(self.parse([kind]), (kind, None, None))

    def test_explicit_version_is_normalised(self):
        self.assertEqual(self.parse(["v1.3.60"]), ("patch", "v1.3.60", None))
        self.assertEqual(self.parse(["1.3.60"]), ("patch", "v1.3.60", None))

    def test_notes_flag_takes_the_next_argument(self):
        self.assertEqual(
            self.parse(["--notes", "Scraper fix"]),
            ("patch", None, "Scraper fix"),
        )

    def test_version_and_notes_combine(self):
        self.assertEqual(
            self.parse(["v1.3.60", "--notes", "two words"]),
            ("patch", "v1.3.60", "two words"),
        )

    def test_help_exits_zero_without_bumping(self):
        for flag in ("-h", "--help"):
            self.assertEqual(self.parse_fails([flag]), 0)

    def test_unknown_flag_is_rejected(self):
        # Regression: --help used to be swallowed as an unknown token and the
        # script bumped the version instead of printing usage.
        for flag in ("--dry-run", "--force", "-x", "--Help"):
            self.assertEqual(self.parse_fails([flag]), 2)

    def test_stray_word_is_rejected(self):
        self.assertEqual(self.parse_fails(["patch", "extra"]), 2)

    def test_bump_type_and_version_cannot_combine(self):
        self.assertEqual(self.parse_fails(["1.3.60", "patch"]), 2)
        self.assertEqual(self.parse_fails(["patch", "1.3.60"]), 2)

    def test_repeated_bump_type_is_rejected(self):
        self.assertEqual(self.parse_fails(["patch", "minor"]), 2)

    def test_repeated_version_is_rejected(self):
        self.assertEqual(self.parse_fails(["v1.3.60", "v1.3.61"]), 2)

    def test_notes_without_value_is_rejected(self):
        self.assertEqual(self.parse_fails(["--notes"]), 2)

    def test_usage_mentions_no_dry_run(self):
        self.assertIn("no dry-run", bump_version.USAGE)


class BumpVersionCalcTests(unittest.TestCase):
    def test_patch_bump(self):
        self.assertEqual(
            bump_version.calculate_version("v1.3.54", 13540, "patch", None),
            ("v1.3.55", "1.3.55", 13550),
        )

    def test_minor_bump_resets_patch(self):
        self.assertEqual(
            bump_version.calculate_version("v1.3.54", 13540, "minor", None),
            ("v1.4.0", "1.4.0", 14000),
        )

    def test_major_bump_resets_minor_and_patch(self):
        self.assertEqual(
            bump_version.calculate_version("v1.3.54", 13540, "major", None),
            ("v2.0.0", "2.0.0", 20000),
        )

    def test_custom_version_wins_over_bump_type(self):
        # versionCode is major*10000 + minor*1000 + patch*10, so 1.3.60 is 13600.
        self.assertEqual(
            bump_version.calculate_version("v1.3.54", 13540, "patch", "v1.3.60"),
            ("v1.3.60", "1.3.60", 13600),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
