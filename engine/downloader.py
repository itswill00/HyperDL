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
import subprocess
import shutil
import socket
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
import html as pyhtml
import urllib.request
import urllib.parse
import urllib.error

# Protect all operations from hanging sockets
socket.setdefaulttimeout(15)

STATUS_FILE = "/data/local/tmp/hyperdl_status.json"
DEFAULT_OUTDIR = "/storage/emulated/0/Download/HyperDL"
CONF_DIR = "/data/adb/hyperdl"
COOKIES_PATH = "/data/adb/hyperdl/cookies.txt"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"

def expand_shortlink_fast(url, timeout=3.5):
    """
    Ultra-fast shortlink expansion using HTTP HEAD/Range 0-0.
    Avoids downloading megabytes of landing page HTML just to get target URL.
    """
    low = url.lower()
    if not any(k in low for k in [
        "vt.tiktok.com", "vm.tiktok.com", "v.douyin.com",
        "fb.watch", "/share/", "t.co", "pin.it", "pin.",
        "/s/", "redd.it", "bit.ly", "tinyurl.com", "is.gd"
    ]):
        return url

    class FastRedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            m = req.get_method()
            if code in (301, 302, 303, 307, 308):
                return urllib.request.Request(newurl, headers=req.headers, method=m)
            return None

    opener = urllib.request.build_opener(FastRedirectHandler)
    req = urllib.request.Request(url, method="HEAD", headers={
        "User-Agent": USER_AGENT,
        "Accept": "*/*"
    })
    res = url
    try:
        with opener.open(req, timeout=timeout) as r:
            res = r.geturl()
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location") or e.headers.get("location")
        if loc:
            if not loc.startswith("http"):
                loc = urllib.parse.urljoin(url, loc)
            res = loc
    except Exception:
        try:
            req_get = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"})
            with urllib.request.urlopen(req_get, timeout=timeout) as r:
                res = r.geturl()
        except Exception:
            res = url

    # Guard: if expansion stripped the video path (e.g. redirected to homepage with ?_r=1 or /)
    if "tiktok.com" in res.lower() and "/video/" not in res.lower() and "/photo/" not in res.lower():
        return url
    if "instagram.com" in res.lower() and "/p/" not in res.lower() and "/reel/" not in res.lower() and "/tv/" not in res.lower():
        return url
    return res

def humanize_error(e):
    if not e:
        return ""
    msg = str(e)
    low = msg.lower()
    if any(k in low for k in [
        "temporary failure in name resolution",
        "no address associated with hostname",
        "network is unreachable",
        "connection refused",
        "connection timed out",
        "timed out",
        "gaierror",
        "getaddrinfo failed",
        "connection reset",
        "remotedisconnected",
        "networkerror",
        "urlopen error"
    ]):
        return "No internet connection or network is unreachable. Please check your connection."
    if "certificate_verify_failed" in low or ("ssl" in low and "verify" in low):
        return "Network security error: SSL certificate verification failed. Check device date/time."
    if "http error 403" in low or "forbidden" in low:
        return "Access denied by platform (HTTP 403). Session cookies may be required."
    if "http error 404" in low or "not found" in low:
        return "Media not found (HTTP 404). Link may be expired or deleted."
    if "private video" in low or "login required" in low:
        return "Content is private or requires authentication. Please configure cookies."
    return msg

def update_status(status, percent=0, speed="", downloaded="", total="", title="", file_path="", error=""):
    data = {
        "status": status,
        "percent": percent,
        "speed": speed,
        "downloaded": downloaded,
        "total": total,
        "title": title,
        "file_path": file_path,
        "error": humanize_error(error) if error else "",
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

def download_file(url, out_path, title="Media", headers=None, emit_error=True, emit_complete=True):
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
            with open(out_path, "wb", buffering=1024 * 1024) as f:
                while True:
                    chunk = resp.read(512 * 1024)
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

            if emit_complete:
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

def download_media_candidates(item, out_path, title, emit_complete=True):
    if item.get("direct_ytdlp"):
        outdir = os.path.dirname(out_path) or "."
        return download_with_ytdlp_direct(item["url"], outdir, fmt=item.get("fmt", "video"), is_yt=item.get("is_yt", False))

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
            return download_file(url, out_path, title=title, headers=hdrs, emit_error=False, emit_complete=emit_complete)
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
                if fb_item.get("direct_ytdlp"):
                    outdir = os.path.dirname(out_path) or "."
                    return download_with_ytdlp_direct(fb_item["url"], outdir, fmt=fb_item.get("fmt", "video"), is_yt=fb_item.get("is_yt", False))
                return download_media_candidates(fb_item, out_path, title, emit_complete=emit_complete)
        except Exception as fe:
            last_err = fe
            print(f"Mirror resolver failed: {fe}", file=sys.stderr)

    raise RuntimeError(f"Unable to download stream: {last_err}")

def fetch_tikwm(clean_url, fmt="video"):
    endpoints = [
        "https://www.tikwm.com/api/"
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
            with urllib.request.urlopen(req, timeout=5) as resp:
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
                            "candidates": [{"url": music_url, "headers": {"User-Agent": USER_AGENT, "Referer": "https://www.tiktok.com/"}, "label": "TikWM Audio"}]
                        }
                elif d.get("images"):
                    img_list = []
                    for im in d.get("images", []):
                        if im.startswith("/"):
                            im = "https://www.tikwm.com" + im
                        img_list.append(im)
                    return {
                        "title": title,
                        "ext": "jpg",
                        "kind": "album",
                        "images": img_list,
                        "headers": {"User-Agent": USER_AGENT, "Referer": "https://www.tiktok.com/"}
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
    clean_url = expand_shortlink_fast(url, timeout=3.5)
    cookie_hdr = get_cookie_header("tiktok.com")

    if not cookie_hdr:
        try:
            return fetch_tikwm(clean_url, fmt)
        except Exception as e:
            print(f"Fast TikWM path note: {e}, attempting direct scrape...", file=sys.stderr)

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

    try:
        return fetch_tikwm(clean_url, fmt)
    except Exception as te:
        print(f"TikWM mirror fallback note: {te}", file=sys.stderr)
        return {
            "direct_ytdlp": True,
            "url": clean_url if clean_url != url else url,
            "fmt": fmt,
            "is_yt": False,
            "title": "TikTok Media"
        }

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
            with urllib.request.urlopen(req, timeout=4) as resp:
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

    # Fast OpenGraph / Crawler metadata probe (WhatsApp / Facebook bot UA)
    try:
        crawler_hdrs = {
            "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }
        req = urllib.request.Request(f"https://www.instagram.com/reel/{shortcode}/", headers=crawler_hdrs)
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        
        og_vid = re.search(r'property=["\']og:video(?::secure_url)?["\']\s+content=["\']([^"\']+)["\']', html)
        if og_vid:
            vurl = pyhtml.unescape(og_vid.group(1)).replace("&amp;", "&")
            return {"url": vurl, "title": f"Instagram_{shortcode}", "ext": "mp4", "kind": "video"}
            
        if "/reel/" not in url.lower() and "/reels/" not in url.lower():
            og_img = re.search(r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html)
            if og_img:
                iurl = pyhtml.unescape(og_img.group(1)).replace("&amp;", "&")
                if not iurl.endswith("instagram.com/"):
                    return {"url": iurl, "title": f"Instagram_{shortcode}", "ext": "jpg", "kind": "image"}
    except Exception as e:
        print(f"Instagram crawler probe note: {e}", file=sys.stderr)

    # Route directly to single-pass yt-dlp to avoid double invocation delay
    return {
        "direct_ytdlp": True,
        "url": url,
        "fmt": "video",
        "is_yt": False,
        "title": f"Instagram_{shortcode}"
    }

def resolve_facebook(url, fmt="video"):
    update_status("resolving", title="Resolving Facebook media...")
    clean_url = expand_shortlink_fast(url, timeout=3.5)
    clean_url = clean_url.replace("m.facebook.com", "www.facebook.com").replace("mbasic.facebook.com", "www.facebook.com")
    
    cookie_hdr = get_cookie_header("facebook.com")
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.facebook.com/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }
    if cookie_hdr:
        hdrs["Cookie"] = cookie_hdr

    try:
        req = urllib.request.Request(clean_url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=6) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        hd_m = re.search(r'"progressive_url"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"\s*,\s*"failure_reason"\s*:\s*[^,]+\s*,\s*"metadata"\s*:\s*\{\s*"quality"\s*:\s*"HD"\s*\}', html, re.S)
        sd_m = re.search(r'"progressive_url"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"\s*,\s*"failure_reason"\s*:\s*[^,]+\s*,\s*"metadata"\s*:\s*\{\s*"quality"\s*:\s*"SD"\s*\}', html, re.S)
        native_hd_m = re.search(r'"browser_native_hd_url"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', html, re.S)
        native_sd_m = re.search(r'"browser_native_sd_url"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', html, re.S)
        playable_hd_m = re.search(r'"playable_url_quality_hd"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', html, re.S)
        playable_sd_m = re.search(r'"playable_url"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', html, re.S)

        def unescape_fb(val):
            val = val.replace(r"\/", "/").replace(r"\u0026", "&")
            return re.sub(r'\\u([0-9a-fA-F]{4})', lambda x: chr(int(x.group(1), 16)), val)

        fb_media_hdrs = {"User-Agent": USER_AGENT, "Referer": "https://www.facebook.com/"}
        candidates = []
        if hd_m:
            candidates.append({"url": unescape_fb(hd_m.group(1)), "headers": fb_media_hdrs, "label": "Facebook HD"})
        if native_hd_m and not hd_m:
            candidates.append({"url": unescape_fb(native_hd_m.group(1)), "headers": fb_media_hdrs, "label": "Facebook HD"})
        if playable_hd_m and not hd_m and not native_hd_m:
            candidates.append({"url": unescape_fb(playable_hd_m.group(1)), "headers": fb_media_hdrs, "label": "Facebook HD"})
        if sd_m:
            candidates.append({"url": unescape_fb(sd_m.group(1)), "headers": fb_media_hdrs, "label": "Facebook SD"})
        if native_sd_m and not sd_m:
            candidates.append({"url": unescape_fb(native_sd_m.group(1)), "headers": fb_media_hdrs, "label": "Facebook SD"})
        if playable_sd_m and not sd_m and not native_sd_m:
            candidates.append({"url": unescape_fb(playable_sd_m.group(1)), "headers": fb_media_hdrs, "label": "Facebook SD"})

        title_m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html) or \
                  re.search(r'<title[^>]*>(.*?)</title>', html, re.S)
        title = "Facebook Video"
        if title_m:
            t = re.sub(r'\s*\|\s*Facebook.*$', '', title_m.group(1), flags=re.I).strip()
            t = pyhtml.unescape(t)
            if t and t.lower() not in ("facebook", "watch", "reel"):
                title = t

        if candidates:
            return {
                "title": title,
                "ext": "mp4",
                "kind": "video",
                "candidates": candidates,
                "fallback": lambda: {"direct_ytdlp": True, "url": clean_url, "fmt": fmt, "is_yt": False, "title": title}
            }
    except Exception as e:
        print(f"Facebook direct scrape note: {e}", file=sys.stderr)

    return {
        "direct_ytdlp": True,
        "url": clean_url,
        "fmt": fmt,
        "is_yt": False,
        "title": "Facebook Video"
    }

def resolve_pinterest(url, fmt="video"):
    update_status("resolving", title="Resolving Pinterest media...")
    clean_url = expand_shortlink_fast(url, timeout=3.5)

    m = re.search(r'pin/(?:[\w-]+--)?(\d+)', clean_url)
    if m:
        pin_id = m.group(1)
        try:
            headers = {
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Referer": "https://www.pinterest.com/",
                "X-Pinterest-Pws-Handler": "www/[username].js",
            }
            cookie_hdr = get_cookie_header("pinterest.com")
            if cookie_hdr:
                headers["Cookie"] = cookie_hdr

            payload = {"options": {"field_set_key": "unauth_react_main_pin", "id": pin_id}}
            api_url = "https://www.pinterest.com/resource/PinResource/get/?" + urllib.parse.urlencode({"data": json.dumps(payload, separators=(',', ':'))})
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                d = json.loads(resp.read().decode("utf-8"))
            pin = d.get("resource_response", {}).get("data", {})
            title = pin.get("title") or pin.get("grid_title") or pin.get("description") or f"Pinterest_{pin_id}"

            videos = pin.get("videos", {}).get("video_list", {})
            if isinstance(videos, dict) and videos:
                mp4s = [v.get("url") for k, v in videos.items() if v.get("url") and not str(v.get("url")).endswith(".m3u8")]
                if mp4s:
                    return {"url": mp4s[0], "title": title, "ext": "mp4", "kind": "video"}
                all_vids = [v.get("url") for k, v in videos.items() if v.get("url")]
                if all_vids:
                    return {"url": all_vids[0], "title": title, "ext": "mp4", "kind": "video"}

            story = pin.get("story_pin_data", {})
            if isinstance(story, dict):
                for page in story.get("pages", []):
                    for block in page.get("blocks", []):
                        if int(block.get("block_type") or 0) == 3 and isinstance(block.get("video"), dict):
                            vlist = block.get("video", {}).get("video_list", {})
                            for k, v in vlist.items():
                                if v.get("url") and not str(v.get("url")).endswith(".m3u8"):
                                    return {"url": v["url"], "title": title, "ext": "mp4", "kind": "video"}

            images = pin.get("images", {})
            orig = images.get("orig", {}) if isinstance(images, dict) else {}
            if orig.get("url"):
                return {"url": orig["url"], "title": title, "ext": "jpg", "kind": "image"}
        except Exception as e:
            print(f"Pinterest API note: {e}", file=sys.stderr)

    return {
        "direct_ytdlp": True,
        "url": clean_url,
        "fmt": fmt,
        "is_yt": False,
        "title": "Pinterest Media"
    }

def resolve_reddit(url, fmt="video"):
    update_status("resolving", title="Resolving Reddit media...")
    clean_url = expand_shortlink_fast(url, timeout=3.5)

    p = urllib.parse.urlparse(clean_url)
    clean_path = p.path.rstrip("/")
    if not clean_path.endswith(".json"):
        clean_path += "/.json"

    cookie_hdr = get_cookie_header("reddit.com")
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Accept": "application/json,text/html,*/*",
        "Referer": "https://www.reddit.com/"
    }
    if cookie_hdr:
        hdrs["Cookie"] = cookie_hdr

    # Try RapidSave mirror first as Reddit actively blocks .json endpoints without OAuth
    try:
        rs_url = f"https://rapidsave.com/info?url={urllib.parse.quote(clean_url)}"
        rs_req = urllib.request.Request(rs_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(rs_req, timeout=4) as r:
            rs_html = r.read().decode("utf-8", errors="ignore")
        rs_match = re.search(r'<a[^>]+class=["\'][^"\']*downloadbutton[^"\']*["\'][^>]+href=["\']([^"\']+)["\']', rs_html) or \
                   re.search(r'<a[^>]+href=["\'](https?://(?:sd|d)\.rapidsave\.com/download\.php\?[^"\']+)["\']', rs_html)
        if rs_match:
            dl_url = rs_match.group(1).replace("&amp;", "&")
            title_m = re.search(r'<title>(.*?)</title>', rs_html)
            t = title_m.group(1) if title_m else "Reddit Video"
            t = re.sub(r'\s*-\s*Reddit Video Downloader.*$', '', t, flags=re.I).strip()
            return {"url": dl_url, "title": t or "Reddit Video", "ext": "mp4", "kind": "video"}
    except Exception as re_err:
        print(f"Reddit rapidsave mirror note: {re_err}", file=sys.stderr)

    candidates_urls = [
        f"https://old.reddit.com{clean_path}",
        f"https://www.reddit.com{clean_path}"
    ]

    def fetch_reddit_candidate(c_url):
        req = urllib.request.Request(c_url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            raw_text = resp.read().decode("utf-8", errors="ignore")
            if raw_text.strip().startswith(("[", "{")):
                return json.loads(raw_text)
        return None

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(fetch_reddit_candidate, cu) for cu in candidates_urls]
            for f in futures:
                try:
                    data = f.result()
                    if isinstance(data, list) and data:
                        post = data[0].get("data", {}).get("children", [{}])[0].get("data", {})
                        title = post.get("title") or "Reddit Media"

                        gallery = post.get("media_metadata", {})
                        if isinstance(gallery, dict) and gallery:
                            images = []
                            for k, meta in gallery.items():
                                src = meta.get("s", {}).get("u") or meta.get("s", {}).get("mp4")
                                if src:
                                    images.append(pyhtml.unescape(src).replace("&amp;", "&"))
                            if images:
                                return {"images": images, "title": title, "ext": "jpg", "kind": "album"}

                        post_url = pyhtml.unescape(post.get("url") or "")
                        if any(post_url.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
                            return {"url": post_url, "title": title, "ext": "jpg", "kind": "image"}

                        media = post.get("media") or post.get("secure_media") or post.get("preview", {}).get("reddit_video_preview")
                        rv = (media.get("reddit_video") if isinstance(media, dict) and media.get("reddit_video") else media) or {}
                        fallback = rv.get("fallback_url")
                        if fallback:
                            return {
                                "url": fallback,
                                "title": title,
                                "ext": "mp4",
                                "kind": "video"
                            }
                except Exception:
                    continue
    except Exception as e:
        print(f"Reddit JSON candidates note: {e}", file=sys.stderr)

    return {
        "direct_ytdlp": True,
        "url": clean_url,
        "fmt": fmt,
        "is_yt": False,
        "title": "Reddit Media"
    }

def resolve_twitter(url, fmt="video"):
    update_status("resolving", title="Resolving X/Twitter post...")
    clean_url = expand_shortlink_fast(url, timeout=3.5)

    m = re.search(r'status/(\d+)', clean_url)
    if not m:
        return {
            "direct_ytdlp": True,
            "url": clean_url,
            "fmt": fmt,
            "is_yt": False,
            "title": "X Media"
        }
    status_id = m.group(1)

    cookie_hdr = get_cookie_header("x.com") or get_cookie_header("twitter.com")
    cookies_map = load_cookies("x.com")
    if not cookies_map:
        cookies_map = load_cookies("twitter.com")

    csrf = cookies_map.get("ct0")
    auth = cookies_map.get("auth_token")

    if csrf and auth and cookie_hdr:
        try:
            bearer = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
            api_endpoint = "https://x.com/i/api/graphql/2ICDjqPd81tulZcYrtpTuQ/TweetResultByRestId"
            variables = {"tweetId": status_id, "withCommunity": False, "includePromotedContent": False, "withVoice": False}
            features = {
                "creator_subscriptions_tweet_preview_api_enabled": True,
                "tweetypie_unmention_optimization_enabled": True,
                "responsive_web_edit_tweet_api_enabled": True,
                "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
                "view_counts_everywhere_api_enabled": True,
                "longform_notetweets_consumption_enabled": True,
                "responsive_web_graphql_exclude_directive_enabled": True,
                "verified_phone_label_enabled": False,
                "responsive_web_graphql_timeline_navigation_enabled": True,
            }
            query = urllib.parse.urlencode({
                "variables": json.dumps(variables, separators=(",", ":")),
                "features": json.dumps(features, separators=(",", ":"))
            })
            req_url = f"{api_endpoint}?{query}"
            gql_hdrs = {
                "authorization": f"Bearer {bearer}",
                "x-twitter-auth-type": "OAuth2Session",
                "x-twitter-client-language": "en",
                "x-twitter-active-user": "yes",
                "x-csrf-token": csrf,
                "cookie": cookie_hdr,
                "user-agent": USER_AGENT,
                "accept": "*/*",
                "referer": "https://x.com/"
            }
            req = urllib.request.Request(req_url, headers=gql_hdrs)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            result = ((data.get("data") or {}).get("tweetResult") or {}).get("result") or {}
            legacy = (result.get("tweet", {}).get("legacy") if isinstance(result.get("tweet"), dict) else result.get("legacy")) or {}
            media_list = legacy.get("extended_entities", {}).get("media") or legacy.get("entities", {}).get("media") or []
            if media_list:
                title = legacy.get("full_text") or f"Tweet_{status_id}"
                images = []
                for media in media_list:
                    mtype = str(media.get("type") or "").lower()
                    if mtype in ("video", "animated_gif"):
                        variants = media.get("video_info", {}).get("variants", [])
                        mp4s = [v for v in variants if v.get("content_type") == "video/mp4" and v.get("url")]
                        if mp4s:
                            mp4s.sort(key=lambda x: int(x.get("bitrate") or 0), reverse=True)
                            return {"url": mp4s[0]["url"], "title": title, "ext": "mp4", "kind": "video"}
                    elif mtype == "photo":
                        p_url = media.get("media_url_https")
                        if p_url:
                            images.append(p_url)
                if images:
                    if len(images) == 1:
                        return {"url": images[0], "title": title, "ext": "jpg", "kind": "image"}
                    return {"images": images, "title": title, "ext": "jpg", "kind": "album"}
        except Exception as e:
            print(f"Twitter GraphQL API note: {e}", file=sys.stderr)

    guest_endpoints = [
        f"https://api.fxtwitter.com/i/status/{status_id}",
        f"https://api.vxtwitter.com/Twitter/status/{status_id}",
        f"https://cdn.syndication.twimg.com/tweet-result?id={status_id}&token=4"
    ]

    def query_guest_ep(ep):
        req = urllib.request.Request(ep, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            return ep, json.loads(resp.read().decode("utf-8"))

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(query_guest_ep, ep): ep for ep in guest_endpoints}
        for f in as_completed(futures):
            try:
                ep, data = f.result()
                if not data:
                    continue
                title = data.get("text") or data.get("tweet", {}).get("text") or f"Tweet_{status_id}"

                v_url = data.get("video_url")
                if not v_url and data.get("tweet", {}).get("media", {}).get("videos"):
                    v_url = data["tweet"]["media"]["videos"][0].get("url")
                if v_url:
                    return {"url": v_url, "title": title, "ext": "mp4", "kind": "video"}

                photos = data.get("mediaURLs")
                if not photos and data.get("tweet", {}).get("media", {}).get("photos"):
                    photos = [p.get("url") for p in data["tweet"]["media"]["photos"] if p.get("url")]
                if photos:
                    if len(photos) == 1:
                        return {"url": photos[0], "title": title, "ext": "jpg", "kind": "image"}
                    return {"images": photos, "title": title, "ext": "jpg", "kind": "album"}
            except Exception:
                continue

    return {
        "direct_ytdlp": True,
        "url": clean_url,
        "fmt": fmt,
        "is_yt": False,
        "title": f"Tweet_{status_id}"
    }

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

    update_status("resolving", title="Downloading utility components...")
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

def get_python_binary():
    py_candidates = [
        "/data/data/com.termux/files/usr/bin/python3",
        "/data/adb/modules/hyperdl/runtime/bin/python3",
        "/data/data/com.termux/files/home/HyperDL_Module/runtime/bin/python3",
        sys.executable,
        "python3"
    ]
    for p in py_candidates:
        if p and os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return "python3"

def get_runtime_env():
    env = dict(os.environ)
    runtime_dir = "/data/adb/modules/hyperdl/runtime"
    if not os.path.isdir(runtime_dir):
        candidate_dev = "/data/data/com.termux/files/home/HyperDL_Module/runtime"
        if os.path.isdir(candidate_dev):
            runtime_dir = candidate_dev
    if os.path.isdir(runtime_dir):
        env["PATH"] = f"{runtime_dir}/bin:" + env.get("PATH", "/system/bin")
        env["LD_LIBRARY_PATH"] = f"{runtime_dir}/lib"
        env["PYTHONHOME"] = runtime_dir
        env["PYTHONPATH"] = f"{runtime_dir}/lib/python314.zip:{runtime_dir}/lib/python3.14/lib-dynload"
        env["SSL_CERT_FILE"] = f"{runtime_dir}/lib/cacert.pem"
    return env

def get_ffmpeg_binary():
    import shutil
    candidates = [
        "/data/adb/modules/hyperdl/runtime/bin/ffmpeg",
        "/data/data/com.termux/files/home/HyperDL_Module/runtime/bin/ffmpeg",
        "/data/adb/modules/hyperdl/system/bin/ffmpeg",
        "/data/data/com.termux/files/home/HyperDL_Module/system/bin/ffmpeg",
        "/data/data/com.termux/files/usr/bin/ffmpeg",
        "/system/bin/ffmpeg",
        "/system/xbin/ffmpeg",
    ]
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return shutil.which("ffmpeg")

def resolve_ytdlp(url, fmt="video", is_yt=False):
    return {
        "direct_ytdlp": True,
        "url": url,
        "fmt": fmt,
        "is_yt": is_yt,
        "title": "Media"
    }

def resolve_youtube(url, fmt="video"):
    return {
        "direct_ytdlp": True,
        "url": url,
        "fmt": fmt,
        "is_yt": True,
        "title": "YouTube Media"
    }

def download_with_ytdlp_direct(url, outdir, fmt="video", format_id=None, height=None):
    ytdlp_bin = get_or_download_ytdlp()
    py_bin = get_python_binary()

    cookie_arg = ["--cookies", COOKIES_PATH] if os.path.exists(COOKIES_PATH) else []
    ffmpeg_bin = get_ffmpeg_binary()
    ffmpeg_arg = ["--ffmpeg-location", ffmpeg_bin] if ffmpeg_bin else []

    node_bin = None
    for nc in ["/data/data/com.termux/files/usr/bin/node", "/system/bin/node", "/system/xbin/node"]:
        if os.path.isfile(nc) and os.access(nc, os.X_OK):
            node_bin = nc
            break
    if not node_bin:
        node_bin = shutil.which("node")
    js_arg = ["--js-runtimes", f"node:{node_bin}"] if node_bin else []

    if fmt == "audio":
        format_arg = ["-f", "ba/bestaudio/best", "-x", "--audio-format", "flac", "--audio-quality", "0"]
    elif format_id and not height:
        format_arg = ["-f", format_id]
    elif height:
        h = int(height)
        if ffmpeg_bin:
            format_arg = ["-f", f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={h}]+bestaudio/best[height<={h}]/best", "--merge-output-format", "mp4"]
        else:
            format_arg = ["-f", f"best[height<={h}][ext=mp4]/best[height<={h}]/best"]
    else:
        if ffmpeg_bin:
            format_arg = ["-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[ext=mp4]/best", "--merge-output-format", "mp4"]
        else:
            format_arg = ["-f", "best[ext=mp4]/best"]

    os.makedirs(outdir, exist_ok=True)
    out_tpl = os.path.join(outdir, "%(title).60s_%(id)s.%(ext)s")

    cmd = [
        py_bin,
        ytdlp_bin,
        "--no-warnings",
        "--no-check-certificates",
        "--no-playlist",
        "--concurrent-fragments", "4",
        "--no-mtime",
        "--buffer-size", "256k",
        "--http-chunk-size", "10M",
        "--extractor-retries", "2",
        "--socket-timeout", "12",
        "--newline",
        "--progress-template", "%(progress._percent_str)s|%(progress._downloaded_bytes_str)s|%(progress._total_bytes_str)s|%(progress._speed_str)s",
        "-o", out_tpl,
    ] + js_arg + ffmpeg_arg + format_arg + cookie_arg + [url]

    env = get_runtime_env()
    update_status("downloading", percent=0, title="Downloading...")
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    title = "Media"
    downloaded_file = None
    for line in proc.stdout:
        line = line.strip()
        if "|" in line:
            parts = line.split("|")
            pct_str = parts[0].replace("%", "").strip()
            try:
                pct = int(float(pct_str))
            except Exception:
                pct = 50
            dl_str = parts[1].strip() if len(parts) > 1 else ""
            tot_str = parts[2].strip() if len(parts) > 2 else ""
            spd_str = parts[3].strip() if len(parts) > 3 else ""
            update_status("downloading", percent=pct, downloaded=dl_str, total=tot_str, speed=spd_str, title=title)
        elif "[download] Destination:" in line:
            downloaded_file = line.replace("[download] Destination:", "").strip()
            title = os.path.splitext(os.path.basename(downloaded_file))[0]
        elif "[Merger] Merging formats into" in line:
            downloaded_file = line.replace("[Merger] Merging formats into", "").strip().strip('"')
            title = os.path.splitext(os.path.basename(downloaded_file))[0]
        elif "[ExtractAudio] Destination:" in line:
            downloaded_file = line.replace("[ExtractAudio] Destination:", "").strip().strip('"')
            title = os.path.splitext(os.path.basename(downloaded_file))[0]

    proc.wait()
    if proc.returncode != 0:
        err = proc.stderr.read().strip()
        raise RuntimeError(f"yt-dlp failed: {err[-200:]}")

    if not downloaded_file or not os.path.exists(downloaded_file):
        files = [os.path.join(outdir, f) for f in os.listdir(outdir)]
        if files:
            files.sort(key=os.path.getmtime, reverse=True)
            downloaded_file = files[0]
            title = os.path.splitext(os.path.basename(downloaded_file))[0]

    if downloaded_file and os.path.exists(downloaded_file):
        scan_media_file(downloaded_file)
        update_status("completed", percent=100, title=title, file_path=downloaded_file)
        send_android_notification("Download complete", f"{title} saved to Download/HyperDL")
        return downloaded_file

    raise RuntimeError("Media file not found after download completed")

def probe_resolutions(url):
    import subprocess
    m_url = re.search(r'https?://[^\s<>"]+', url)
    if m_url:
        url = m_url.group(0)
    ytdlp_bin = get_or_download_ytdlp()
    py_bin = get_python_binary()
    cookie_arg = ["--cookies", COOKIES_PATH] if os.path.exists(COOKIES_PATH) else []
    ffmpeg_bin = get_ffmpeg_binary()
    ffmpeg_arg = ["--ffmpeg-location", ffmpeg_bin] if ffmpeg_bin else []

    node_bin = None
    for nc in ["/data/data/com.termux/files/usr/bin/node", "/system/bin/node", "/system/xbin/node"]:
        if os.path.isfile(nc) and os.access(nc, os.X_OK):
            node_bin = nc
            break
    if not node_bin:
        import shutil
        node_bin = shutil.which("node")
    js_arg = ["--js-runtimes", f"node:{node_bin}"] if node_bin else []

    cmd = [
        py_bin, ytdlp_bin,
        "-J", "--no-warnings", "--no-check-certificates",
        "--no-playlist", "--no-check-formats", "--socket-timeout", "10",
        "--extractor-retries", "1",
    ] + js_arg + ffmpeg_arg + cookie_arg + [url]

    env = get_runtime_env()
    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
    if res.returncode != 0 or not res.stdout.strip():
        return []

    try:
        data = json.loads(res.stdout)
    except Exception:
        return []

    duration = data.get("duration") or 0
    formats = data.get("formats") or []

    best_audio_size = 0
    for f in formats:
        if f.get("vcodec", "none") == "none" and f.get("acodec", "none") != "none":
            asize = f.get("filesize") or f.get("filesize_approx") or 0
            if asize == 0 and duration > 0:
                abr = f.get("abr") or f.get("tbr") or 128
                asize = int((abr * 1024 / 8) * duration)
            if asize > best_audio_size:
                best_audio_size = asize

    by_height = {}
    for f in formats:
        h = f.get("height")
        if not h or h < 144:
            continue
        vcodec = f.get("vcodec", "none")
        if vcodec == "none":
            continue
        note = str(f.get("format_note", "")).lower()
        if "premium" in note:
            continue

        vsize = f.get("filesize") or f.get("filesize_approx") or 0
        tbr = f.get("tbr") or 0
        vbr = f.get("vbr") or 0
        fps = f.get("fps") or 30
        if vsize == 0 and duration > 0:
            br = vbr or tbr
            if br:
                vsize = int((br * 1024 / 8) * duration)

        if h not in by_height or vsize > by_height[h]["vsize"]:
            by_height[h] = {"height": h, "vsize": vsize, "fps": fps}

    if not by_height:
        return []

    labels = {
        4320: "8K Ultra HD",
        2160: "4K Ultra HD",
        1440: "2K QHD",
        1080: "1080p Full HD",
        720: "720p HD",
        480: "480p SD",
        360: "360p",
        240: "240p",
        144: "144p"
    }

    results = []
    for h in sorted(by_height.keys(), reverse=True):
        entry = by_height[h]
        tot = entry["vsize"] + best_audio_size
        lbl = labels.get(h, f"{h}p")
        results.append({
            "height": h,
            "format_id": str(h),
            "label": lbl,
            "ext": "mp4",
            "filesize": tot,
            "fps": entry["fps"]
        })

    return results

def main():
    parser = argparse.ArgumentParser(description="HyperDL Downloader")
    subparsers = parser.add_subparsers(dest="action")

    dl_parser = subparsers.add_parser("download")
    dl_parser.add_argument("url", help="Media link")
    dl_parser.add_argument("--format", default="video", choices=["video", "audio", "album"])
    dl_parser.add_argument("--outdir", default=DEFAULT_OUTDIR)
    dl_parser.add_argument("--height", default=None, help="Max height for video")
    dl_parser.add_argument("--format-id", default=None, dest="format_id", help="Specific yt-dlp format ID")

    probe_parser = subparsers.add_parser("probe")
    probe_parser.add_argument("url", help="Media link")

    args, _ = parser.parse_known_args()

    if args.action == "probe":
        try:
            resolutions = probe_resolutions(args.url.strip())
            print(json.dumps({"resolutions": resolutions}), flush=True)
        except Exception as e:
            print(json.dumps({"error": humanize_error(e)}), flush=True)
            sys.exit(1)
        return

    if args.action != "download" and args.action is not None:
        print(json.dumps({"error": "unknown_action"}), flush=True)
        sys.exit(1)

    if not hasattr(args, 'url') or not args.url:
        parser.print_help()
        sys.exit(1)

    url = args.url.strip()
    m_url = re.search(r'https?://[^\s<>"]+', url)
    if m_url:
        url = m_url.group(0)
    fmt = args.format
    outdir = args.outdir
    height = args.height if hasattr(args, 'height') else None
    format_id = args.format_id if hasattr(args, 'format_id') else None

    try:
        update_status("resolving", title="Connecting to platform...")
        low_url = url.lower()

        if format_id or height:
            download_with_ytdlp_direct(url, outdir, fmt=fmt, format_id=format_id, height=height)
            return

        if "tiktok.com" in low_url or "douyin.com" in low_url:
            info = resolve_tiktok(url, fmt)
        elif "twitter.com" in low_url or "x.com" in low_url:
            info = resolve_twitter(url, fmt)
        elif "instagram.com" in low_url or "instagr.am" in low_url:
            info = resolve_instagram(url)
        elif "facebook.com" in low_url or "fb.watch" in low_url or "fb.com" in low_url:
            info = resolve_facebook(url, fmt)
        elif "pinterest.com" in low_url or "pin.it" in low_url:
            info = resolve_pinterest(url, fmt)
        elif "reddit.com" in low_url or "redd.it" in low_url:
            info = resolve_reddit(url, fmt)
        elif "youtube.com" in low_url or "youtu.be" in low_url:
            info = resolve_youtube(url, fmt)
        else:
            info = resolve_ytdlp(url, fmt, is_yt=False)

        if info.get("direct_ytdlp"):
            download_with_ytdlp_direct(info["url"], outdir, fmt=info.get("fmt", fmt))
            return

        title = sanitize_filename(info.get("title", "Media"))
        ext = info.get("ext", "mp4")

        if info.get("kind") == "album" and info.get("images"):
            images = info["images"]
            total = len(images)
            for idx, img_url in enumerate(images):
                img_path = os.path.join(outdir, f"{title}_{idx+1}.{ext}")
                update_status("downloading", percent=int((idx+1)/total*100), title=f"{title} ({idx+1}/{total})")
                hdrs = dict(info.get("headers") or {})
                if "tikwm.com" in img_url:
                    hdrs["Referer"] = "https://www.tikwm.com/"
                download_file(img_url, img_path, title=f"{title}_{idx+1}", headers=hdrs, emit_error=True, emit_complete=False)
            update_status("completed", percent=100, title=title, file_path=outdir)
            send_android_notification("Download complete", f"{title} saved ({total} items)")
        else:
            if fmt == "audio":
                ffmpeg_bin = get_ffmpeg_binary()
                if ffmpeg_bin:
                    tmp_raw = os.path.join(outdir, f".tmp_{int(time.time())}_{title}.raw")
                    download_media_candidates(info, tmp_raw, title=title, emit_complete=False)
                    out_path = os.path.join(outdir, f"{title}_{int(time.time())}.flac")
                    update_status("downloading", percent=95, title="Encoding audio to FLAC HD...")
                    res = subprocess.run([ffmpeg_bin, "-y", "-i", tmp_raw, "-c:a", "flac", out_path], capture_output=True)
                    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
                        fallback_ext = ext if ext in ["mp3", "m4a", "wav", "aac"] else "mp3"
                        out_path = os.path.join(outdir, f"{title}_{int(time.time())}.{fallback_ext}")
                        if os.path.exists(tmp_raw):
                            os.replace(tmp_raw, out_path)
                    else:
                        if os.path.exists(tmp_raw):
                            try:
                                os.remove(tmp_raw)
                            except Exception:
                                pass
                    try:
                        os.chmod(out_path, 0o666)
                    except Exception:
                        pass
                    scan_media_file(out_path)
                    update_status("completed", percent=100, title=title, file_path=out_path)
                    send_android_notification("Download complete", f"{title} saved as FLAC HD")
                    return
            filename = f"{title}_{int(time.time())}.{ext}"
            out_path = os.path.join(outdir, filename)
            download_media_candidates(info, out_path, title=title)

    except Exception as e:
        print(f"Download Error: {e}", file=sys.stderr)
        update_status("error", error=str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
