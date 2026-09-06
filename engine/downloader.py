#!/usr/bin/env python3

import os
import sys
import re
import json
import time
import uuid
import base64
import hashlib
import argparse
import urllib.request
import urllib.parse
import urllib.error

STATUS_FILE = "/data/local/tmp/hyperdl_status.json"
DEFAULT_OUTDIR = "/storage/emulated/0/Download/HyperDL"
CONF_DIR = "/data/adb/hyperdl"
COOKIES_PATH = "/data/adb/hyperdl/cookies.txt"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"

def update_status(status, percent=0, speed="", downloaded="", total="", title="", file_path="", error=""):
    data = {
        "status": status,
        "percent": percent,
        "speed": speed,
        "downloaded": downloaded,
        "total": total,
        "title": title,
        "file_path": file_path,
        "error": error,
        "timestamp": int(time.time())
    }
    try:
        os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
        with open(STATUS_FILE, "w") as f:
            json.dump(data, f)
        try:
            os.chmod(STATUS_FILE, 0o666)
        except Exception:
            pass
    except Exception:
        pass
    print(json.dumps(data), flush=True)

def sanitize_filename(name):
    if not name:
        return "Media"
    clean = name.replace('#', ' ')
    clean = re.sub(r'[/\\:*?"<>|\n\r\t%&+=`$\'{}\[\]@;]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip(' ._-')
    return clean[:60] if clean else "Media"

def scan_media_file(file_path):
    if not file_path or not os.path.exists(file_path):
        return
    try:
        quoted = urllib.parse.quote(file_path)
        os.system(f'am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file://{quoted}" >/dev/null 2>&1')
    except Exception:
        pass

def send_android_notification(title, text):
    try:
        os.system(f'cmd notification post -S bigtext -t "{title}" "HyperDL" "{text}" >/dev/null 2>&1')
    except Exception:
        pass

def load_cookies(domain=""):
    if not os.path.exists(COOKIES_PATH):
        return {}
    
    cookies = {}
    try:
        with open(COOKIES_PATH, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    c_domain = parts[0].strip().lower()
                    c_name = parts[5].strip()
                    c_val = parts[6].strip()
                    if domain and not (domain in c_domain or c_domain.endswith(domain)):
                        continue
                    if c_name and c_val:
                        cookies[c_name] = c_val
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    cookies[k.strip()] = v.strip()
    except Exception as e:
        print(f"Failed to read cookies: {e}", file=sys.stderr)
    return cookies

def get_cookie_header(domain=""):
    c = load_cookies(domain)
    return "; ".join(f"{k}={v}" for k, v in c.items()) if c else ""

def decode_base64_padded(val):
    padding = (4 - len(val) % 4) % 4
    return base64.b64decode(val + ("=" * padding))

def solve_tiktok_challenge(html_text):
    wci = re.search(r'(?is)<[^>]+\bid="wci"[^>]*\bclass="([^"]*)"', html_text)
    cs = re.search(r'(?is)<[^>]+\bid="cs"[^>]*\bclass="([^"]*)"', html_text)
    rci = re.search(r'(?is)<[^>]+\bid="rci"[^>]*\bclass="([^"]*)"', html_text)
    rs = re.search(r'(?is)<[^>]+\bid="rs"[^>]*\bclass="([^"]*)"', html_text)

    if not wci or not cs:
        return ""

    chal_name = wci.group(1).strip()
    chal_enc = cs.group(1).strip()

    try:
        chal_data = json.loads(decode_base64_padded(chal_enc))
        v = chal_data.get("v", {})
        base_val = decode_base64_padded(v.get("a", ""))
        expected_digest = decode_base64_padded(v.get("c", ""))

        solution = ""
        for i in range(1_000_001):
            candidate = base_val + str(i).encode('utf-8')
            if hashlib.sha256(candidate).digest() == expected_digest:
                solution = str(i)
                break

        if not solution:
            return ""

        chal_data["d"] = base64.b64encode(solution.encode('utf-8')).decode('utf-8')
        chal_val = base64.b64encode(json.dumps(chal_data, separators=(',', ':')).encode('utf-8')).decode('utf-8')
        cookies = [f"{chal_name}={chal_val}"]
        if rci and rs and rci.group(1).strip():
            cookies.append(f"{rci.group(1).strip()}={rs.group(1).strip()}")
        return "; ".join(cookies)
    except Exception as e:
        print(f"PoW challenge solver error: {e}", file=sys.stderr)
        return ""

def download_file(url, out_path, title="Media", headers=None, emit_error=True):
    hdrs = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Connection": "keep-alive"
    }
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            total_bytes = 0
            cr = resp.headers.get('content-range')
            if cr and '/' in cr:
                tot_str = cr.split('/')[-1].strip()
                if tot_str.isdigit():
                    total_bytes = int(tot_str)
            if not total_bytes:
                total_bytes = int(resp.headers.get('content-length', 0) or 0)

            downloaded = 0
            start_time = time.time()
            last_update = 0

            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as f:
                while True:
                    chunk = resp.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    if now - last_update >= 0.25:
                        last_update = now
                        elapsed = max(now - start_time, 0.001)
                        speed_bps = downloaded / elapsed
                        speed_str = f"{speed_bps / (1024*1024):.1f} MB/s" if speed_bps >= 1024*1024 else f"{speed_bps / 1024:.0f} KB/s"
                        
                        pct = int((downloaded / total_bytes * 100)) if total_bytes > 0 else 50
                        dl_str = f"{downloaded / (1024*1024):.1f} MB"
                        tot_str = f"{total_bytes / (1024*1024):.1f} MB" if total_bytes > 0 else "?"
                        
                        update_status("downloading", percent=pct, speed=speed_str, downloaded=dl_str, total=tot_str, title=title)

            if os.path.exists(out_path) and os.path.getsize(out_path) < 1024:
                raise RuntimeError("Downloaded file is incomplete or empty")

            try:
                os.chmod(out_path, 0o666)
            except Exception:
                pass

            scan_media_file(out_path)

            update_status("completed", percent=100, title=title, file_path=out_path)
            send_android_notification("Download complete", f"{title} saved to Download/HyperDL")
            return out_path
    except Exception as e:
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except Exception:
                pass
        if emit_error:
            update_status("error", error=str(e), title=title)
        raise

def download_media_candidates(item, out_path, title):
    candidates = item.get("candidates", [])
    if "url" in item and not candidates:
        candidates = [{"url": item["url"], "headers": item.get("headers"), "label": "Primary"}]

    last_err = None
    for idx, cand in enumerate(candidates, start=1):
        url = cand.get("url")
        if not url:
            continue
        hdrs = cand.get("headers") or item.get("headers") or {}
        label = cand.get("label", f"Candidate {idx}")
        print(f"Attempting stream source [{label}]...", file=sys.stderr)
        try:
            return download_file(url, out_path, title=title, headers=hdrs, emit_error=False)
        except Exception as e:
            last_err = e
            print(f"Stream source [{label}] failed: {e}", file=sys.stderr)
            continue

    fallback_func = item.get("fallback")
    if callable(fallback_func):
        print("Direct stream sources failed. Invoking mirror resolver...", file=sys.stderr)
        update_status("resolving", title="Connecting to mirror stream...")
        try:
            fb_item = fallback_func()
            if fb_item:
                return download_media_candidates(fb_item, out_path, title)
        except Exception as fe:
            last_err = fe
            print(f"Mirror resolver failed: {fe}", file=sys.stderr)

    raise RuntimeError(f"Unable to download stream: {last_err}")

def fetch_tikwm(clean_url, fmt="video"):
    endpoints = [
        "https://www.tikwm.com/api/",
        "https://tikwm.com/api/"
    ]
    last_err = None
    for ep in endpoints:
        try:
            req = urllib.request.Request(
                ep,
                data=urllib.parse.urlencode({"url": clean_url, "hd": 1}).encode("utf-8"),
                headers={
                    "User-Agent": USER_AGENT,
                    "Referer": "https://www.tikwm.com/"
                }
            )
            with urllib.request.urlopen(req, timeout=7) as resp:
                res = json.loads(resp.read().decode("utf-8"))
            if res.get("code") == 0 and res.get("data"):
                d = res["data"]
                title = d.get("title") or "TikTok Media"
                
                if fmt == "audio":
                    music_url = d.get("music") or (d.get("music_info") or {}).get("play")
                    if music_url:
                        return {
                            "title": title,
                            "ext": "mp3",
                            "kind": "audio",
                            "candidates": [{"url": music_url, "headers": {"User-Agent": USER_AGENT, "Referer": "https://www.tikwm.com/"}, "label": "TikWM Audio"}]
                        }
                elif fmt == "album" and d.get("images"):
                    return {
                        "title": title,
                        "ext": "jpg",
                        "kind": "album",
                        "images": d.get("images"),
                        "headers": {"User-Agent": USER_AGENT, "Referer": "https://www.tikwm.com/"}
                    }
                else:
                    candidates = []
                    hdplay = d.get("hdplay")
                    if hdplay:
                        if hdplay.startswith("/"):
                            hdplay = "https://www.tikwm.com" + hdplay
                        candidates.append({
                            "url": hdplay,
                            "headers": {"User-Agent": USER_AGENT, "Referer": "https://www.tikwm.com/", "Range": "bytes=0-"},
                            "label": "TikWM HD Mirror"
                        })
                    play = d.get("play")
                    if play:
                        if play.startswith("/"):
                            play = "https://www.tikwm.com" + play
                        candidates.append({
                            "url": play,
                            "headers": {"User-Agent": USER_AGENT, "Referer": "https://www.tikwm.com/", "Range": "bytes=0-"},
                            "label": "TikWM Standard Mirror"
                        })
                    wmplay = d.get("wmplay")
                    if wmplay:
                        if wmplay.startswith("/"):
                            wmplay = "https://www.tikwm.com" + wmplay
                        candidates.append({
                            "url": wmplay,
                            "headers": {"User-Agent": USER_AGENT, "Referer": "https://www.tikwm.com/", "Range": "bytes=0-"},
                            "label": "TikWM Backup Mirror"
                        })
                    if candidates:
                        return {
                            "title": title,
                            "ext": "mp4",
                            "kind": "video",
                            "candidates": candidates
                        }
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"TikWM mirror failed: {last_err}")

def resolve_tiktok(url, fmt="video"):
    update_status("resolving", title="Resolving TikTok media...")
    cookie_hdr = get_cookie_header("tiktok.com")

    if not cookie_hdr:
        try:
            return fetch_tikwm(url, fmt)
        except Exception as e:
            print(f"Fast TikWM path note: {e}, attempting direct scrape...", file=sys.stderr)

    clean_url = url
    if "vt.tiktok.com" in url or "vm.tiktok.com" in url:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=5) as r:
                clean_url = r.geturl()
        except Exception as e:
            print(f"Shortlink expansion note: {e}", file=sys.stderr)

    hdrs = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.tiktok.com/"
    }
    if cookie_hdr:
        hdrs["Cookie"] = cookie_hdr

    try:
        req = urllib.request.Request(clean_url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=7) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        if 'id="cs"' in html and 'id="wci"' in html:
            chal_cookie = solve_tiktok_challenge(html)
            if chal_cookie:
                hdrs["Cookie"] = f"{cookie_hdr}; {chal_cookie}" if cookie_hdr else chal_cookie
                req = urllib.request.Request(clean_url, headers=hdrs)
                with urllib.request.urlopen(req, timeout=7) as resp2:
                    html = resp2.read().decode("utf-8", errors="ignore")

        m = re.search(r'<script[^>]+id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', html, re.S)
        if m:
            data = json.loads(m.group(1))
            scope = data.get("__DEFAULT_SCOPE__", {})
            detail = scope.get("webapp.video-detail", {})
            item = detail.get("itemInfo", {}).get("itemStruct", {})

            if item:
                title = item.get("desc") or "TikTok Video"
                
                image_post = item.get("imagePost", {})
                if image_post and image_post.get("images"):
                    images = []
                    for img in image_post.get("images", []):
                        url_list = img.get("imageURL", {}).get("urlList") or img.get("displayImage", {}).get("urlList")
                        if url_list:
                            images.append(url_list[0])
                    if images:
                        return {
                            "images": images,
                            "title": title,
                            "ext": "jpg",
                            "kind": "album",
                            "headers": {"User-Agent": USER_AGENT, "Referer": "https://www.tiktok.com/"}
                        }

                tt_headers = {
                    "User-Agent": USER_AGENT,
                    "Referer": "https://www.tiktok.com/",
                    "Origin": "https://www.tiktok.com",
                    "Range": "bytes=0-",
                    "Accept": "*/*",
                    "Connection": "keep-alive"
                }
                if cookie_hdr:
                    tt_headers["Cookie"] = cookie_hdr

                if fmt == "audio":
                    music = item.get("music", {})
                    music_url = music.get("playUrl") or music.get("play_url")
                    if music_url:
                        return {
                            "title": title,
                            "ext": "mp3",
                            "kind": "audio",
                            "candidates": [{"url": music_url, "headers": tt_headers, "label": "Direct Audio"}],
                            "fallback": lambda: fetch_tikwm(clean_url, "audio")
                        }

                video = item.get("video", {})
                candidates = []
                seen_urls = set()

                bitrates = video.get("bitrateInfo", [])
                if bitrates:
                    bitrates.sort(key=lambda x: x.get("Bitrate", 0), reverse=True)
                    for b in bitrates:
                        p_addr = b.get("PlayAddr") or b.get("playAddr") or {}
                        if isinstance(p_addr, dict):
                            for u in p_addr.get("UrlList", []) or p_addr.get("urlList", []):
                                if u and u not in seen_urls:
                                    seen_urls.add(u)
                                    candidates.append({"url": u, "headers": tt_headers, "label": f"Direct Bitrate ({b.get('Bitrate', '')})"})

                for k in ("playAddr", "downloadAddr"):
                    u = video.get(k)
                    if u and u not in seen_urls:
                        seen_urls.add(u)
                        candidates.append({"url": u, "headers": tt_headers, "label": f"Direct {k}"})

                if candidates:
                    return {
                        "title": title,
                        "ext": "mp4",
                        "kind": "video",
                        "candidates": candidates,
                        "fallback": lambda: fetch_tikwm(clean_url, fmt)
                    }
    except Exception as e:
        print(f"Direct TikTok scrape note: {e}, using mirror resolver...", file=sys.stderr)

    return fetch_tikwm(clean_url, fmt)

def resolve_instagram(url):
    update_status("resolving", title="Resolving Instagram media...")
    shortcode_match = re.search(r'/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)', url)
    if not shortcode_match:
        raise RuntimeError("Invalid Instagram URL format")
    shortcode = shortcode_match.group(1)

    cookie_hdr = get_cookie_header("instagram.com")
    hdrs = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.instagram.com/"
    }
    if cookie_hdr:
        hdrs["Cookie"] = cookie_hdr

    if cookie_hdr and "sessionid=" in cookie_hdr:
        try:
            gql_url = f"https://www.instagram.com/graphql/query/?doc_id=8845758582119845&variables=%7B%22shortcode%22%3A%22{shortcode}%22%7D"
            req = urllib.request.Request(gql_url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            media = data.get("data", {}).get("xdt_shortcode_media", {})
            if media:
                title = f"Instagram_{shortcode}"
                if media.get("is_video"):
                    return {"url": media.get("video_url"), "title": title, "ext": "mp4", "kind": "video"}
                elif media.get("display_url"):
                    return {"url": media.get("display_url"), "title": title, "ext": "jpg", "kind": "image"}
        except Exception as e:
            print(f"Instagram GraphQL query failed: {e}", file=sys.stderr)

    try:
        embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
        req = urllib.request.Request(embed_url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        
        vid_match = re.search(r'"video_url"\s*:\s*"([^"]+)"', html)
        if vid_match:
            vurl = vid_match.group(1).replace("\\u0026", "&").replace("\\", "")
            return {"url": vurl, "title": f"Instagram_{shortcode}", "ext": "mp4", "kind": "video"}

        img_match = re.search(r'"display_url"\s*:\s*"([^"]+)"', html)
        if img_match:
            iurl = img_match.group(1).replace("\\u0026", "&").replace("\\", "")
            return {"url": iurl, "title": f"Instagram_{shortcode}", "ext": "jpg", "kind": "image"}
    except Exception as e:
        print(f"Instagram embed extraction failed: {e}", file=sys.stderr)

    try:
        return resolve_youtube(url, fmt="video")
    except Exception as ye:
        print(f"Instagram yt-dlp fallback note: {ye}", file=sys.stderr)

    raise RuntimeError("Unable to load Instagram media (try adding cookies in Settings)")

def resolve_twitter(url):
    update_status("resolving", title="Resolving X/Twitter post...")
    status_id_match = re.search(r'status/(\d+)', url)
    if not status_id_match:
        raise RuntimeError("Invalid X/Twitter link")
    status_id = status_id_match.group(1)

    try:
        req = urllib.request.Request(f"https://api.vxtwitter.com/Twitter/status/{status_id}", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        title = data.get("text") or f"Post_{status_id}"
        if data.get("video_url"):
            return {"url": data.get("video_url"), "title": title, "ext": "mp4", "kind": "video"}
        elif data.get("mediaURLs"):
            return {"images": data.get("mediaURLs"), "title": title, "ext": "jpg", "kind": "album"}
    except Exception as e:
        print(f"VxTwitter resolution failed: {e}", file=sys.stderr)

    try:
        req = urllib.request.Request(f"https://api.fxtwitter.com/status/{status_id}", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tweet = data.get("tweet", {})
        media = tweet.get("media", {})
        videos = media.get("videos", [])
        if videos and videos[0].get("url"):
            return {"url": videos[0]["url"], "title": tweet.get("text") or f"Post_{status_id}", "ext": "mp4", "kind": "video"}
    except Exception as e:
        print(f"FxTwitter resolution failed: {e}", file=sys.stderr)

    try:
        return resolve_youtube(url, fmt="video")
    except Exception as ye:
        print(f"Twitter yt-dlp fallback note: {ye}", file=sys.stderr)

    raise RuntimeError("Unable to extract media from this post")

YTDLP_DOWNLOAD_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"

def get_or_download_ytdlp():
    candidates = [
        "/data/adb/modules/hyperdl/system/bin/yt-dlp",
        "/data/data/com.termux/files/home/HyperDL_Module/system/bin/yt-dlp",
        os.path.join(CONF_DIR, "bin", "yt-dlp"),
        os.path.join(CONF_DIR, "yt-dlp"),
        "/data/data/com.termux/files/usr/bin/yt-dlp"
    ]
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c

    import shutil
    p = shutil.which("yt-dlp")
    if p:
        return p

    target_dir = os.path.join(CONF_DIR, "bin")
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, "yt-dlp")
    tmp_path = target_path + ".downloading"

    update_status("resolving", title="Downloading yt-dlp engine (2.9 MB)...")
    print(f"Downloading standalone yt-dlp to {target_path}...", file=sys.stderr)
    req = urllib.request.Request(
        YTDLP_DOWNLOAD_URL,
        headers={"User-Agent": "Mozilla/5.0 (Android; Mobile; rv:130.0)"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp, open(tmp_path, "wb") as f:
        f.write(resp.read())

    try:
        import tempfile, compileall, zipfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(tmp_path, "r") as z:
                z.extractall(tmpdir)
            compileall.compile_dir(tmpdir, force=True, quiet=1, legacy=True)
            for root, dirs, files in os.walk(tmpdir):
                for file in files:
                    if file.endswith(".py"):
                        os.remove(os.path.join(root, file))
            opt_path = tmp_path + ".opt"
            with open(opt_path, "wb") as of:
                of.write(b"#!/usr/bin/env python3\n")
                with zipfile.ZipFile(of, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                    for root, dirs, files in os.walk(tmpdir):
                        for file in files:
                            full = os.path.join(root, file)
                            rel = os.path.relpath(full, tmpdir)
                            z.write(full, rel)
            os.replace(opt_path, tmp_path)
    except Exception as opt_err:
        print(f"Bytecode optimizer note: {opt_err}", file=sys.stderr)

    os.chmod(tmp_path, 0o755)
    os.replace(tmp_path, target_path)
    return target_path

def resolve_youtube(url, fmt="video"):
    update_status("resolving", title="Resolving YouTube stream...")
    import subprocess

    ytdlp_bin = get_or_download_ytdlp()

    py_candidates = [
        "/data/data/com.termux/files/usr/bin/python3",
        "/data/adb/modules/hyperdl/runtime/bin/python3",
        "/data/data/com.termux/files/home/HyperDL_Module/runtime/bin/python3",
        sys.executable,
        "python3"
    ]
    py_bin = None
    for p in py_candidates:
        if p and os.path.isfile(p) and os.access(p, os.X_OK):
            py_bin = p
            break
    if not py_bin:
        py_bin = "python3"

    cookie_arg = ["--cookies", COOKIES_PATH] if os.path.exists(COOKIES_PATH) else []
    format_arg = ["-f", "ba/b"] if fmt == "audio" else ["-f", "best[ext=mp4]/best"]

    cmd_fast = [
        py_bin,
        ytdlp_bin,
        "--extractor-args",
        "youtube:player_client=android",
        "--no-warnings",
        "--no-check-certificates",
        "--socket-timeout",
        "6",
        "--no-playlist",
        "-e",
        "-g",
    ] + format_arg + cookie_arg + [url]

    env = dict(os.environ)
    runtime_dir = "/data/adb/modules/hyperdl/runtime"
    if os.path.isdir(runtime_dir):
        env["PATH"] = f"{runtime_dir}/bin:" + env.get("PATH", "/system/bin")
        env["LD_LIBRARY_PATH"] = f"{runtime_dir}/lib"
        env["PYTHONHOME"] = runtime_dir
        env["PYTHONPATH"] = f"{runtime_dir}/lib/python314.zip:{runtime_dir}/lib/python3.14/lib-dynload"
        env["SSL_CERT_FILE"] = f"{runtime_dir}/lib/cacert.pem"

    res = subprocess.run(cmd_fast, env=env, capture_output=True, text=True, timeout=25)
    if res.returncode == 0 and res.stdout.strip():
        lines = [l.strip() for l in res.stdout.strip().split("\n") if l.strip()]
        title = lines[0] if len(lines) > 1 else "YouTube Media"
        stream_url = lines[1] if len(lines) > 1 else lines[0]
        ext = "mp3" if fmt == "audio" else "mp4"
        return {"url": stream_url, "title": title, "ext": ext, "kind": fmt}

    cmd_fallback = [
        py_bin,
        ytdlp_bin,
        "--no-warnings",
        "--no-check-certificates",
        "--socket-timeout",
        "8",
        "--no-playlist",
        "-e",
        "-g",
    ] + format_arg + cookie_arg + [url]

    res_fb = subprocess.run(cmd_fallback, env=env, capture_output=True, text=True, timeout=30)
    if res_fb.returncode == 0 and res_fb.stdout.strip():
        lines = [l.strip() for l in res_fb.stdout.strip().split("\n") if l.strip()]
        title = lines[0] if len(lines) > 1 else "Media"
        stream_url = lines[1] if len(lines) > 1 else lines[0]
        ext = "mp3" if fmt == "audio" else "mp4"
        return {"url": stream_url, "title": title, "ext": ext, "kind": fmt}

    err = res.stderr.strip() or res_fb.stderr.strip() or "Failed to resolve stream"
    print(f"yt-dlp error: {err}", file=sys.stderr)
    raise RuntimeError(f"Resolution failed: {err[-200:]}")

def main():
    parser = argparse.ArgumentParser(description="HyperDL Downloader")
    parser.add_argument("url", help="Media link")
    parser.add_argument("--format", default="video", choices=["video", "audio", "album"], help="Output format")
    parser.add_argument("--outdir", default=DEFAULT_OUTDIR, help="Output directory")
    args = parser.parse_args()

    url = args.url.strip()
    fmt = args.format
    outdir = args.outdir

    try:
        update_status("resolving", title="Connecting to platform...")
        low_url = url.lower()
        if "tiktok.com" in low_url:
            info = resolve_tiktok(url, fmt)
        elif "twitter.com" in low_url or "x.com" in low_url:
            info = resolve_twitter(url)
        elif "instagram.com" in low_url:
            info = resolve_instagram(url)
        elif "youtube.com" in low_url or "youtu.be" in low_url:
            info = resolve_youtube(url, fmt)
        else:
            info = resolve_youtube(url, fmt)

        title = sanitize_filename(info.get("title", "Media"))
        ext = info.get("ext", "mp4")
        hdrs = info.get("headers", {})

        if info.get("kind") == "album" and info.get("images"):
            images = info["images"]
            total = len(images)
            for idx, img_url in enumerate(images):
                img_path = os.path.join(outdir, f"{title}_{idx+1}.{ext}")
                update_status("downloading", percent=int((idx+1)/total*100), title=f"{title} ({idx+1}/{total})")
                download_file(img_url, img_path, title=f"{title}_{idx+1}", headers=info.get("headers"), emit_error=True)
            update_status("completed", percent=100, title=title, file_path=outdir)
            send_android_notification("Download complete", f"{title} saved ({total} items)")
        else:
            filename = f"{title}_{int(time.time())}.{ext}"
            out_path = os.path.join(outdir, filename)
            download_media_candidates(info, out_path, title=title)

    except Exception as e:
        print(f"Download Error: {e}", file=sys.stderr)
        update_status("error", error=str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
