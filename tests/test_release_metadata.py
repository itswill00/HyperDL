"""Release metadata must match the standard in AGENTS.md section 8.

`update.json` ships the one-line summary that root managers show in their
update prompt. It has to be the release notes intro paragraph verbatim, so the
two can never tell a different story about the same build.
"""

import os
import re
import json
import subprocess
import unittest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    with open(os.path.join(PROJECT_DIR, path), encoding="utf-8") as f:
        return f.read()


def current_version():
    match = re.search(r"^version=(.+)$", read("module.prop"), re.MULTILINE)
    return match.group(1).strip()


def version_tuple(version):
    return tuple(int(part) for part in version.lstrip("v").split("."))


def version_code(version):
    """Return the versionCode that scripts/bump_version.py derives from a version."""
    major, minor, patch = version_tuple(version)
    return major * 10000 + minor * 1000 + patch * 10


def release_tag_exists(version):
    """Return True once the version's git tag exists, meaning its release was cut."""
    try:
        listed = subprocess.run(
            ["git", "tag", "--list", version],
            cwd=PROJECT_DIR, capture_output=True, text=True, check=False,
        ).stdout
    except OSError:
        return False
    return version in listed.split()


def previous_release(version):
    """Return the newest vX.Y.Z below version that has release notes, or None."""
    older = []
    for name in os.listdir(os.path.join(PROJECT_DIR, "release_notes")):
        if re.fullmatch(r"v\d+\.\d+\.\d+\.md", name):
            tag = name[:-len(".md")]
            if version_tuple(tag) < version_tuple(version):
                older.append((version_tuple(tag), tag))
    return max(older)[1] if older else None


class TestUpdateJson(unittest.TestCase):
    """update.json is the public feed and must only describe a published release.

    Until the GitHub Release for module.prop's version exists, the feed keeps the
    previous release, so no root manager is offered a ZIP that was never uploaded.
    Once the tag exists, re-sync the feed with
    `scripts/bump_version.py <version> --notes "<intro>"`.
    """

    def setUp(self):
        self.data = json.loads(read("update.json"))

    def test_feed_describes_current_release_or_pending_predecessor(self):
        version = current_version()
        allowed = [version] if release_tag_exists(version) else [version, previous_release(version)]
        self.assertIn(self.data["version"], allowed)

    def test_version_code_matches_feed_version(self):
        self.assertEqual(self.data["versionCode"], version_code(self.data["version"]))

    def test_zip_url_points_at_the_feed_tag(self):
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

    def test_notes_is_the_feed_release_intro_verbatim(self):
        # Regression: v1.3.54 paraphrased the intro instead of reusing it, so
        # the update prompt and the release page disagreed on wording.
        self.assertEqual(self.data["notes"], release_intro(self.data["version"]))


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

    def test_version_code_matches_version(self):
        code = re.search(r"^versionCode=(\d+)$", read("module.prop"), re.MULTILINE)
        self.assertEqual(int(code.group(1)), version_code(current_version()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
