#!/usr/bin/env python3
"""
HyperDL Core Downloader Engine
Mature, multi-platform media downloader for TikTok, Instagram, X, and YouTube.
Supports custom cookies, PoW challenge bypass, and fallback mirrors.
"""

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
COOKIES_PATH = "/data/adb/hyperdl/cookies.txt"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"

def update_status(status, percent=0, speed="", downloaded="", total="", title="", file_path="", error=""):
    data = {
        "status": status, # idle, resolving, downloading, completed, error
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
    except Exception:
        pass
    print(json.dumps(data), flush=True)

def sanitize_filename(name):
    clean = re.sub(r'[/\\:*?"<>|\n\r\t]', '_', name).strip()
    return clean[:70] if clean else "Media"

def send_android_notification(title, text):
    try:
        os.system(f'cmd notification post -S bigtext -t "{title}" "HyperDL" "{text}" >/dev/null 2>&1')
    except Exception:
        pass

# Cookie Management
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
                # Netscape tab-separated format
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
                # key=value format
                if "=" in line:
                    k, v = line.split("=", 1)
                    cookies[k.strip()] = v.strip()
    except Exception as e:
        print(f"Failed to read cookies: {e}", file=sys.stderr)
    return cookies

def get_cookie_header(domain=""):
    c = load_cookies(domain)
    return "; ".join(f"{k}={v}" for k, v in c.items()) if c else ""

# PoW Challenge Solver for TikTok
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

# Streaming File Downloader
def download_file(url, out_path, title="Media", headers=None):
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            total_bytes = int(resp.headers.get('content-length', 0))
            downloaded = 0
            start_time = time.time()
            last_update = 0

            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as f:
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    if now - last_update >= 0.4:
                        last_update = now
                        elapsed = max(now - start_time, 0.001)
                        speed_bps = downloaded / elapsed
                        speed_str = f"{speed_bps / (1024*1024):.1f} MB/s" if speed_bps >= 1024*1024 else f"{speed_bps / 1024:.0f} KB/s"
                        
                        pct = int((downloaded / total_bytes * 100)) if total_bytes > 0 else 50
                        dl_str = f"{downloaded / (1024*1024):.1f} MB"
                        tot_str = f"{total_bytes / (1024*1024):.1f} MB" if total_bytes > 0 else "?"
                        
                        update_status("downloading", percent=pct, speed=speed_str, downloaded=dl_str, total=tot_str, title=title)

            update_status("completed", percent=100, title=title, file_path=out_path)
            send_android_notification("Download Complete", f"{title} saved to /Download/HyperDL")
            return out_path
    except Exception as e:
        update_status("error", error=str(e), title=title)
        raise

# TikTok Resolver
def resolve_tiktok(url, fmt="video"):
    update_status("resolving", title="Connecting to TikTok...")
    
    # 1. Expand shortlinks if needed
    clean_url = url
    if "vt.tiktok.com" in url or "vm.tiktok.com" in url:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=12) as r:
            clean_url = r.geturl()

    cookie_hdr = get_cookie_header("tiktok.com")
    hdrs = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.tiktok.com/"
    }
    if cookie_hdr:
        hdrs["Cookie"] = cookie_hdr

    # Try Direct SSR Page Rehydration
    try:
        req = urllib.request.Request(clean_url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Solve PoW if challenge presented
        if 'id="cs"' in html and 'id="wci"' in html:
            chal_cookie = solve_tiktok_challenge(html)
            if chal_cookie:
                hdrs["Cookie"] = f"{cookie_hdr}; {chal_cookie}" if cookie_hdr else chal_cookie
                req = urllib.request.Request(clean_url, headers=hdrs)
                with urllib.request.urlopen(req, timeout=15) as resp2:
                    html = resp2.read().decode("utf-8", errors="ignore")

        m = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', html, re.S)
        if m:
            data = json.loads(m.group(1))
            scope = data.get("__DEFAULT_SCOPE__", {})
            detail = scope.get("webapp.video-detail", {})
            item = detail.get("itemInfo", {}).get("itemStruct", {})

            if item:
                title = item.get("desc") or "TikTok Video"
                
                # Photos / Album
                image_post = item.get("imagePost", {})
                if image_post and image_post.get("images"):
                    images = []
                    for img in image_post.get("images", []):
                        url_list = img.get("imageURL", {}).get("urlList") or img.get("displayImage", {}).get("urlList")
                        if url_list:
                            images.append(url_list[0])
                    if images:
                        return {"images": images, "title": title, "ext": "jpg", "kind": "album"}

                # Audio Only
                if fmt == "audio":
                    music = item.get("music", {})
                    music_url = music.get("playUrl") or music.get("play_url")
                    if music_url:
                        return {"url": music_url, "title": title, "ext": "mp3", "kind": "audio"}

                # Video
                video = item.get("video", {})
                video_url = video.get("playAddr") or video.get("downloadAddr")
                bitrates = video.get("bitrateInfo", [])
                if bitrates and not video_url:
                    bitrates.sort(key=lambda x: x.get("Bitrate", 0), reverse=True)
                    url_list = bitrates[0].get("PlayAddr", {}).get("UrlList", [])
                    if url_list:
                        video_url = url_list[0]

                if video_url:
                    return {"url": video_url, "title": title, "ext": "mp4", "kind": "video", "headers": {"Referer": "https://www.tiktok.com/"}}
    except Exception as e:
        print(f"Direct TikTok scrape failed: {e}, attempting mirror fallback...", file=sys.stderr)

    # 2. TikWM Fallback
    try:
        req = urllib.request.Request(
            "https://www.tikwm.com/api/",
            data=urllib.parse.urlencode({"url": clean_url, "hd": 1}).encode("utf-8"),
            headers={"User-Agent": USER_AGENT, "Referer": "https://www.tikwm.com/"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode("utf-8"))
        if res.get("code") == 0 and res.get("data"):
            d = res["data"]
            title = d.get("title") or "TikTok Video"
            if fmt == "audio":
                return {"url": d.get("music"), "title": title, "ext": "mp3", "kind": "audio"}
            elif fmt == "album" and d.get("images"):
                return {"images": d.get("images"), "title": title, "ext": "jpg", "kind": "album"}
            else:
                return {"url": d.get("play") or d.get("hdplay"), "title": title, "ext": "mp4", "kind": "video"}
    except Exception as e:
        print(f"TikWM mirror failed: {e}", file=sys.stderr)

    raise RuntimeError("Unable to resolve TikTok video stream")

# Instagram Resolver
def resolve_instagram(url):
    update_status("resolving", title="Connecting to Instagram...")
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

    # 1. Direct GraphQL API (with user sessionid if available)
    if cookie_hdr and "sessionid=" in cookie_hdr:
        try:
            gql_url = f"https://www.instagram.com/graphql/query/?doc_id=8845758582119845&variables=%7B%22shortcode%22%3A%22{shortcode}%22%7D"
            req = urllib.request.Request(gql_url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=15) as resp:
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

    # 2. Public Embed Extraction Fallback
    try:
        embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
        req = urllib.request.Request(embed_url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        
        # Look for video URL in embed script
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

    raise RuntimeError("Unable to load Instagram media (try adding cookies in Settings)")

# X (Twitter) Resolver
def resolve_twitter(url):
    update_status("resolving", title="Connecting to X...")
    status_id_match = re.search(r'status/(\d+)', url)
    if not status_id_match:
        raise RuntimeError("Invalid X/Twitter link")
    status_id = status_id_match.group(1)

    cookie_hdr = get_cookie_header("x.com") or get_cookie_header("twitter.com")

    # 1. VxTwitter API Mirror
    try:
        req = urllib.request.Request(f"https://api.vxtwitter.com/Twitter/status/{status_id}", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        title = data.get("text") or f"Post_{status_id}"
        if data.get("video_url"):
            return {"url": data.get("video_url"), "title": title, "ext": "mp4", "kind": "video"}
        elif data.get("mediaURLs"):
            return {"images": data.get("mediaURLs"), "title": title, "ext": "jpg", "kind": "album"}
    except Exception as e:
        print(f"VxTwitter resolution failed: {e}", file=sys.stderr)

    # 2. FxTwitter API Mirror
    try:
        req = urllib.request.Request(f"https://api.fxtwitter.com/status/{status_id}", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tweet = data.get("tweet", {})
        media = tweet.get("media", {})
        videos = media.get("videos", [])
        if videos and videos[0].get("url"):
            return {"url": videos[0]["url"], "title": tweet.get("text") or f"Post_{status_id}", "ext": "mp4", "kind": "video"}
    except Exception as e:
        print(f"FxTwitter resolution failed: {e}", file=sys.stderr)

    raise RuntimeError("Unable to extract media from this post")

# YouTube Resolver
def resolve_youtube(url, fmt="video"):
    update_status("resolving", title="Connecting to YouTube...")
    
    # Try yt-dlp first if available
    yt_dlp_path = "/data/data/com.termux/files/usr/bin/yt-dlp"
    if os.path.exists(yt_dlp_path):
        import subprocess
        cookie_arg = ["--cookies", COOKIES_PATH] if os.path.exists(COOKIES_PATH) else []
        cmd = [yt_dlp_path, "-g", "-f", "best[ext=mp4]/best", url] + cookie_arg
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if res.returncode == 0 and res.stdout.strip():
            stream_url = res.stdout.strip().split("\n")[0]
            return {"url": stream_url, "title": "YouTube Video", "ext": "mp4", "kind": fmt}

    raise RuntimeError("YouTube stream resolution requires yt-dlp or cookies")

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
        if "tiktok.com" in url:
            info = resolve_tiktok(url, fmt)
        elif "twitter.com" in url or "x.com" in url:
            info = resolve_twitter(url)
        elif "instagram.com" in url:
            info = resolve_instagram(url)
        elif "youtube.com" in url or "youtu.be" in url:
            info = resolve_youtube(url, fmt)
        else:
            # Universal fallback
            try:
                info = resolve_tiktok(url, fmt)
            except Exception:
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
                download_file(img_url, img_path, title=f"{title}_{idx+1}", headers=hdrs)
            update_status("completed", percent=100, title=title, file_path=outdir)
        else:
            filename = f"{title}_{int(time.time())}.{ext}"
            out_path = os.path.join(outdir, filename)
            download_file(info["url"], out_path, title=title, headers=hdrs)

    except Exception as e:
        print(f"Download Error: {e}", file=sys.stderr)
        update_status("error", error=str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
