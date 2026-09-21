import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from engine._impl import (
    clean_media_url,
    sanitize_filename,
    humanize_error,
    decode_base64_padded,
    check_storage_space,
)


class TestCleanMediaUrl(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(clean_media_url(""), "")
        self.assertEqual(clean_media_url(None), "")

    def test_extracts_url_from_text(self):
        url = 'check this https://vt.tiktok.com/xyz/ out'
        self.assertEqual(clean_media_url(url), "https://vt.tiktok.com/xyz/")

    def test_strips_utm_params(self):
        out = clean_media_url("https://example.com/video?id=1&utm_source=wa&utm_medium=link")
        self.assertEqual(out, "https://example.com/video?id=1")

    def test_youtube_si_feature(self):
        out = clean_media_url("https://youtube.com/watch?v=abc&si=xyz&feature=share&pp=aaa")
        self.assertEqual(out, "https://youtube.com/watch?v=abc&pp=aaa")

    def test_instagram_igsh(self):
        out = clean_media_url("https://instagram.com/reel/abc/?igsh=xyz&utm_source=ig")
        self.assertEqual(out, "https://instagram.com/reel/abc/")

    def test_tiktok_tracking(self):
        out = clean_media_url("https://tiktok.com/@u/video/123?_t=abc&_r=1&is_copy=1")
        self.assertEqual(out, "https://tiktok.com/@u/video/123?is_copy=1")

    def test_twitter_s_and_t(self):
        out = clean_media_url("https://x.com/user/status/1?s=20&t=abc")
        self.assertEqual(out, "https://x.com/user/status/1")

    def test_preserves_fragment(self):
        out = clean_media_url("https://example.com/a?utm_source=x#frag")
        self.assertEqual(out, "https://example.com/a#frag")

    def test_keeps_unknown_query(self):
        out = clean_media_url("https://example.com/page?q=hello")
        self.assertEqual(out, "https://example.com/page?q=hello")


class TestSanitizeFilename(unittest.TestCase):
    def test_empty_defaults_to_media(self):
        self.assertEqual(sanitize_filename(""), "Media")
        self.assertEqual(sanitize_filename(None), "Media")

    def test_replaces_illegal_chars(self):
        out = sanitize_filename('video: "test" <1>/2\\3')
        for ch in '/\\:*?"<>':
            self.assertNotIn(ch, out)

    def test_collapses_whitespace(self):
        self.assertEqual(sanitize_filename("a   b\t\nc"), "a b c")

    def test_truncates_to_60(self):
        out = sanitize_filename("x" * 200)
        self.assertEqual(len(out), 60)

    def test_strips_trailing_junk(self):
        self.assertEqual(sanitize_filename("  title... "), "title")


class TestHumanizeError(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(humanize_error(""), "")
        self.assertEqual(humanize_error(None), "")

    def test_network_error(self):
        out = humanize_error("urlopen error Temporary failure in name resolution")
        self.assertIn("No internet", out)

    def test_ssl_error(self):
        out = humanize_error("ssl certificate_verify_failed")
        self.assertIn("SSL", out)

    def test_403(self):
        out = humanize_error("HTTP Error 403: Forbidden")
        self.assertIn("403", out)

    def test_passthrough_unknown(self):
        self.assertEqual(humanize_error("weird failure"), "weird failure")


class TestDecodeBase64Padded(unittest.TestCase):
    def test_roundtrip(self):
        import base64
        payload = b"hello world"
        raw = base64.b64encode(payload).decode()
        stripped = raw.rstrip("=")
        self.assertEqual(decode_base64_padded(stripped), payload)


class TestCheckStorageSpace(unittest.TestCase):
    def test_existing_dir_ok(self):
        ok, msg = check_storage_space(os.path.dirname(os.path.abspath(__file__)), 1024)
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_nonexistent_dir_fails_open(self):
        ok, msg = check_storage_space("/nonexistent/xyz/definitely", 1024)
        self.assertTrue(ok)
        self.assertEqual(msg, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
