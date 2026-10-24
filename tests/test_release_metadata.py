"""Release metadata must match the standard in AGENTS.md section 8.

`update.json` ships the one-line summary that root managers show in their
update prompt. It has to be the release notes intro paragraph verbatim, so the
two can never tell a different story about the same build.
"""

import os
import re
import json
import unittest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    with open(os.path.join(PROJECT_DIR, path), encoding="utf-8") as f:
        return f.read()


def current_version():
    match = re.search(r"^version=(.+)$", read("module.prop"), re.MULTILINE)
    return match.group(1).strip()


class TestUpdateJson(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(read("update.json"))

    def test_version_matches_module_prop(self):
        self.assertEqual(self.data["version"], current_version())

    def test_version_code_matches_module_prop(self):
        code = re.search(r"^versionCode=(\d+)$", read("module.prop"), re.MULTILINE)
        self.assertEqual(self.data["versionCode"], int(code.group(1)))

    def test_zip_url_points_at_the_current_tag(self):
        version = self.data["version"]
        self.assertEqual(
            self.data["zipUrl"],
            f"https://github.com/itswill00/HyperDL/releases/download/{version}/HyperDL-{version}.zip",
        )

    def test_changelog_points_at_the_source_repo(self):
        self.assertEqual(
            self.data["changelog"],
            "https://raw.githubusercontent.com/itswill00/HyperDL/main/README.md",
        )

    def test_notes_is_the_release_notes_intro_verbatim(self):
        # Regression: v1.3.54 paraphrased the intro instead of reusing it, so
        # the update prompt and the release page disagreed on wording.
        intro = release_intro(current_version())
        self.assertEqual(self.data["notes"], intro)


def release_intro(version):
    """Return the summary paragraph that follows the metadata blockquote."""
    lines = read(os.path.join("release_notes", f"{version}.md")).splitlines()
    for i, line in enumerate(lines):
        if line.startswith("> "):
            for candidate in lines[i + 1:]:
                if candidate.strip():
                    return candidate.strip()
    raise AssertionError(f"no intro paragraph found in release_notes/{version}.md")


class TestReleaseNotesStandard(unittest.TestCase):
    def setUp(self):
        self.version = current_version()
        self.notes = read(os.path.join("release_notes", f"{self.version}.md"))

    def test_exactly_one_h1(self):
        self.assertEqual(len(re.findall(r"^# ", self.notes, re.MULTILINE)), 1)

    def test_h1_is_the_version_heading(self):
        self.assertIn(f"# HyperDL {self.version}", self.notes)

    def test_metadata_blockquote_carries_the_version_code(self):
        code = re.search(r"^versionCode=(\d+)$", read("module.prop"), re.MULTILINE)
        self.assertIn(f"**b{code.group(1)}**", self.notes)

    def test_has_highlights_table(self):
        self.assertIn("## Highlights", self.notes)

    def test_closing_line_is_present(self):
        self.assertIn(
            f"Update from your root manager or flash `HyperDL-{self.version}.zip`.",
            self.notes,
        )

    def test_no_placeholder_text(self):
        for marker in ("TODO", "FIXME", "TBD", "Lorem ipsum"):
            self.assertNotIn(marker, self.notes)

    def test_telegram_post_exists_and_opens_with_the_version(self):
        tg = read(os.path.join("release_notes", f"{self.version}.tg.md"))
        self.assertTrue(tg.startswith(f"*HyperDL {self.version}*"))
        self.assertIn("*Changelog:*", tg)
        self.assertIn("*Notes:*", tg)
        self.assertIn("*Links:*", tg)


class TestModuleProp(unittest.TestCase):
    def test_update_json_points_at_the_source_repo(self):
        self.assertIn(
            "updateJson=https://raw.githubusercontent.com/itswill00/HyperDL/main/update.json",
            read("module.prop"),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
