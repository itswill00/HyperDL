import os
import sys
import json
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from engine._impl import (
    clean_media_url,
    sanitize_filename,
    humanize_error,
    decode_base64_padded,
    check_storage_space,
    _is_range_error,
    _purge_stale_partials,
    get_ffmpeg_env,
    get_ffmpeg_binary,
    get_ffprobe_binary,
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

    def test_403_no_cookies_points_to_optional(self):
        out = humanize_error("HTTP Error 403: Forbidden")
        self.assertIn("without cookies", out)

    def test_403_with_cookies_points_to_expiry(self):
        import engine._impl as impl
        orig_url = impl.CURRENT_URL
        orig_load = impl.load_cookies
        try:
            impl.CURRENT_URL = "https://www.instagram.com/reel/abc123/"
            impl.load_cookies = lambda domain="": {"sessionid": "x"}
            out = humanize_error("HTTP Error 403: Forbidden")
            self.assertIn("expired", out)
        finally:
            impl.CURRENT_URL = orig_url
            impl.load_cookies = orig_load

    def test_private_no_cookies_points_to_optional(self):
        out = humanize_error("Login required")
        self.assertIn("without cookies", out)

    def test_private_with_cookies_points_to_expiry(self):
        import engine._impl as impl
        orig_url = impl.CURRENT_URL
        orig_load = impl.load_cookies
        try:
            impl.CURRENT_URL = "https://x.com/user/status/123"
            impl.load_cookies = lambda domain="": {"auth_token": "x"}
            out = humanize_error("Login required to view this private video")
            self.assertIn("expired", out)
        finally:
            impl.CURRENT_URL = orig_url
            impl.load_cookies = orig_load

    def test_passthrough_unknown(self):
        self.assertEqual(humanize_error("weird failure"), "weird failure")

    def test_ffmpeg_ytdlp_message_maps_to_install_hint(self):
        err = "ERROR: ffmpeg and ffprobe not found - please install or provide the path using --ffmpeg-location"
        self.assertIn("verify module installation", humanize_error(err))

    def test_ffprobe_missing_maps_to_install_hint(self):
        self.assertIn("verify module installation", humanize_error("ffprobe not found in PATH"))

    def test_postprocessing_failure_maps_to_install_hint(self):
        err = "ERROR: Postprocessing: ffprobe and ffmpeg not found. Install ffmpeg."
        self.assertIn("verify module installation", humanize_error(err))


class TestFfmpegDetection(unittest.TestCase):
    def test_env_prefers_system_lib(self):
        import engine._impl as impl
        orig = impl._resolve_runtime_dir
        try:
            impl._resolve_runtime_dir = lambda: "/data/adb/modules/hyperdl/runtime"
            env = get_ffmpeg_env()
            self.assertTrue(env["LD_LIBRARY_PATH"].startswith("/system/lib64"))
            self.assertIn("/data/adb/modules/hyperdl/runtime/lib", env["LD_LIBRARY_PATH"])
            self.assertIn("/data/adb/modules/hyperdl/runtime/bin", env["PATH"])
        finally:
            impl._resolve_runtime_dir = orig

    def test_ffprobe_probe_fails_open_when_absent(self):
        import engine._impl as impl
        from unittest import mock
        with mock.patch.object(impl.os.path, "isfile", return_value=False), \
             mock.patch.object(impl.shutil, "which", return_value=None):
            self.assertIsNone(get_ffprobe_binary())
            self.assertIsNone(get_ffmpeg_binary())

    def test_audio_fails_fast_without_ffmpeg(self):
        import engine._impl as impl
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(impl, "check_storage_space", return_value=(True, "")), \
                 mock.patch.object(impl, "get_or_download_ytdlp", return_value="/fake/yt-dlp"), \
                 mock.patch.object(impl, "get_python_binary", return_value="/fake/python3"), \
                 mock.patch.object(impl, "get_ffmpeg_binary", return_value=None):
                with self.assertRaises(RuntimeError) as ctx:
                    impl.download_with_ytdlp_direct("https://youtu.be/abc", tmp, fmt="audio")
                self.assertIn("FFmpeg", str(ctx.exception))

    def test_audio_fails_fast_without_ffprobe(self):
        import engine._impl as impl
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(impl, "check_storage_space", return_value=(True, "")), \
                 mock.patch.object(impl, "get_or_download_ytdlp", return_value="/fake/yt-dlp"), \
                 mock.patch.object(impl, "get_python_binary", return_value="/fake/python3"), \
                 mock.patch.object(impl, "get_ffmpeg_binary", return_value="/fake/ffmpeg"), \
                 mock.patch.object(impl, "get_ffprobe_binary", return_value=None):
                with self.assertRaises(RuntimeError) as ctx:
                    impl.download_with_ytdlp_direct("https://youtu.be/abc", tmp, fmt="audio")
                self.assertIn("FFprobe", str(ctx.exception))


class TestProbeCache(unittest.TestCase):
    def setUp(self):
        import engine._impl as impl
        self.orig_dir = impl.CACHE_DIR
        self.orig_ttl = impl.PROBE_CACHE_TTL
        self.tmp = tempfile.mkdtemp()
        impl.CACHE_DIR = self.tmp
        self.impl = impl

    def tearDown(self):
        self.impl.CACHE_DIR = self.orig_dir
        self.impl.PROBE_CACHE_TTL = self.orig_ttl
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_roundtrip(self):
        res = [{"height": 1080, "label": "1080p", "filesize": 123}]
        self.impl._cache_put_probe("https://youtu.be/abc", res,
                                   thumbnail="https://i.ytimg.com/max.jpg",
                                   subtitles=["id", "en"])
        got = self.impl._cache_get_probe("https://youtu.be/abc")
        self.assertEqual(got["resolutions"], res)
        self.assertEqual(got["thumbnail"], "https://i.ytimg.com/max.jpg")
        self.assertEqual(got["subtitles"], ["id", "en"])

    def test_miss_on_unknown_url(self):
        self.assertIsNone(self.impl._cache_get_probe("https://youtu.be/nope"))

    def test_expired_entry_is_a_miss(self):
        self.impl._cache_put_probe("https://youtu.be/abc", [{"height": 720}])
        path = self.impl._probe_cache_path()
        with open(path) as f:
            data = json.load(f)
        for k in data:
            data[k]["ts"] = 0
        with open(path, "w") as f:
            json.dump(data, f)
        self.assertIsNone(self.impl._cache_get_probe("https://youtu.be/abc"))

    def test_empty_resolutions_not_cached(self):
        self.impl._cache_put_probe("https://youtu.be/empty", [])
        self.assertIsNone(self.impl._cache_get_probe("https://youtu.be/empty"))

    def test_cache_is_pruned_to_size_cap(self):
        import time
        base = time.time()
        for i in range(260):
            self.impl._cache_put_probe(f"https://youtu.be/v{i}", [{"height": 144 + i}])
        cache = self.impl._load_probe_cache()
        self.assertLessEqual(len(cache), 200)
        self.assertIn("https://youtu.be/v259", cache)
        self.assertNotIn("https://youtu.be/v0", cache)

    def test_corrupt_cache_file_fails_open(self):
        with open(self.impl._probe_cache_path(), "w") as f:
            f.write("{not valid json")
        self.assertEqual(self.impl._load_probe_cache(), {})
        self.assertIsNone(self.impl._cache_get_probe("https://youtu.be/abc"))


class TestProbePayloadHelpers(unittest.TestCase):
    def setUp(self):
        import engine._impl as impl
        self.impl = impl

    def test_pick_thumbnail_prefers_largest(self):
        data = {"thumbnails": [
            {"url": "https://i.ytimg.com/small.jpg", "width": 120, "height": 90},
            {"url": "https://i.ytimg.com/big.jpg", "width": 1280, "height": 720},
            {"url": "not-a-url", "width": 9999, "height": 9999},
        ]}
        self.assertEqual(self.impl._pick_thumbnail(data), "https://i.ytimg.com/big.jpg")

    def test_pick_thumbnail_falls_back_to_direct(self):
        self.assertEqual(
            self.impl._pick_thumbnail({"thumbnails": [], "thumbnail": "https://i.ytimg.com/d.jpg"}),
            "https://i.ytimg.com/d.jpg")

    def test_pick_thumbnail_rejects_garbage(self):
        self.assertEqual(self.impl._pick_thumbnail({}), "")
        self.assertEqual(self.impl._pick_thumbnail({"thumbnails": [{"url": ""}]}), "")
        self.assertEqual(self.impl._pick_thumbnail(None), "")

    def test_pick_subtitle_langs_manual_first(self):
        data = {"subtitles": {"id": [{}], "en": [{}]},
                "automatic_captions": {"en": [{}], "es": [{}]}}
        langs = self.impl._pick_subtitle_langs(data)
        self.assertEqual(langs[:2], ["id", "en"])
        self.assertIn("es", langs)
        self.assertEqual(len(langs), len(set(langs)))

    def test_pick_subtitle_langs_empty(self):
        self.assertEqual(self.impl._pick_subtitle_langs({}), [])
        self.assertEqual(self.impl._pick_subtitle_langs(None), [])


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


class TestRangeErrorRecovery(unittest.TestCase):
    def test_detects_reported_416_message(self):
        err = "yt-dlp failed: ERROR: unable to download video data: HTTP Error 416: Requested range not satisfiable"
        self.assertTrue(_is_range_error(err))

    def test_ignores_other_http_errors(self):
        self.assertFalse(_is_range_error("HTTP Error 403: Forbidden"))
        self.assertFalse(_is_range_error("HTTP Error 500: Internal Server Error"))

    def test_ignores_empty(self):
        self.assertFalse(_is_range_error(""))
        self.assertFalse(_is_range_error(None))

    def test_purge_removes_only_fresh_partials(self):
        import tempfile
        import time
        with tempfile.TemporaryDirectory() as tmp:
            fresh_part = os.path.join(tmp, "video.webm.part")
            old_part = os.path.join(tmp, "other.webm.part")
            final_file = os.path.join(tmp, "done.mp4")
            for p in (fresh_part, old_part, final_file):
                with open(p, "w") as f:
                    f.write("x" * 1024)
            old_mtime = time.time() - 3600
            os.utime(old_part, (old_mtime, old_mtime))
            _purge_stale_partials(tmp, time.time())
            self.assertFalse(os.path.exists(fresh_part))
            self.assertTrue(os.path.exists(old_part))
            self.assertTrue(os.path.exists(final_file))


if __name__ == "__main__":
    unittest.main(verbosity=2)
