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
import threading
import socket
import ssl
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed
import html as pyhtml
import urllib.request
import urllib.parse
import urllib.error

socket.setdefaulttimeout(15)

STATUS_FILE = "/data/local/tmp/hyperdl_status.json"
PID_FILE = "/data/local/tmp/hyperdl.pid"
PROBE_FILE = "/data/local/tmp/hyperdl_probe.json"
PROBE_PID = "/data/local/tmp/hyperdl_probe.pid"
CONF_DIR = "/data/adb/hyperdl"
ACTIVE_TASK_FILE = "/data/adb/hyperdl/active_task.json"
DEFAULT_OUTDIR = "/storage/emulated/0/Download/HyperDL"
COOKIES_PATH = "/data/adb/hyperdl/cookies.txt"
UPDATE_METADATA_URL = "https://raw.githubusercontent.com/itswill00/HyperDL-Release/main/update.json"

CURRENT_URL = ""
CURRENT_FMT = "video"
CURRENT_FORMAT_ID = ""
CURRENT_HEIGHT = ""

_last_status = {
    "percent": 0,
    "downloaded": "",
    "total": "",
    "title": ""
}

def handle_sigterm(signum, frame):
    try:
        update_status("paused", title=_last_status.get("title") or "Download paused")
    except Exception:
        pass
    sys.exit(0)

try:
    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)
except Exception:
    pass

def get_effective_outdir(preferred=DEFAULT_OUTDIR):
    candidates = [
        preferred,
        "/storage/emulated/0/Download/HyperDL",
        "/data/media/0/Download/HyperDL",
        "/sdcard/Download/HyperDL"
    ]
    for c in candidates:
        if not c:
            continue
        try:
            os.makedirs(c, exist_ok=True)
            test_f = os.path.join(c, f".perm_test_{os.getpid()}")
            with open(test_f, "w") as f:
                f.write("ok")
            os.remove(test_f)
            return c
        except Exception:
            continue
    return preferred

def clean_media_url(raw_url):
    if not raw_url:
        return ""
    m = re.search(r'https?://[^\s<>"]+', raw_url)
    clean = m.group(0) if m else raw_url.strip()
    try:
        parsed = urllib.parse.urlparse(clean)
        if not parsed.query:
            return clean
        qs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        netloc = parsed.netloc.lower()
        is_yt = "youtube.com" in netloc or "youtu.be" in netloc
        is_ig = "instagram.com" in netloc
        is_tt = "tiktok.com" in netloc or "douyin.com" in netloc
        is_x = "x.com" in netloc or "twitter.com" in netloc

        new_qs = []
        for k, v in qs:
            kl = k.lower()
            if kl.startswith("utm_") or kl in ("ref", "ref_src"):
                continue
            if kl in ("si", "feature") and is_yt:
                continue
            if kl == "igsh" and is_ig:
                continue
            if kl in ("_t", "_r") and is_tt:
                continue
            if is_x and (kl == "s" or (kl == "t" and not is_yt)):
                continue
            new_qs.append((k, v))

        new_query = urllib.parse.urlencode(new_qs)
        return urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))
    except Exception:
        return clean

def check_storage_space(outdir, required_bytes=100 * 1024 * 1024):
    try:
        st = os.statvfs(outdir)
        free_bytes = st.f_bavail * st.f_frsize
        if free_bytes < required_bytes:
            free_mb = free_bytes // (1024 * 1024)
            return False, f"Low storage space: only {free_mb} MB available (< 100 MB free)"
        return True, ""
    except Exception:
        return True, ""


def get_target_directory(base_outdir, info, url=""):
    vault_flag = "/data/adb/hyperdl/vault.enabled"
    vault_conf = "/data/adb/hyperdl/vault_domains.conf"
    if os.path.exists(vault_flag) and os.path.exists(vault_conf):
        try:
            with open(vault_conf, "r") as vf:
                v_domains = [l.strip().lower() for l in vf if l.strip()]
                low_u = (url or "").lower()
                if any(vd in low_u for vd in v_domains):
                    vault_root = os.path.join(base_outdir, ".vault")
                    target = os.path.join(vault_root, "Stream")
                    os.makedirs(target, exist_ok=True)
                    nm = os.path.join(vault_root, ".nomedia")
                    if not os.path.exists(nm):
                        with open(nm, "w") as f:
                            pass
                        os.chmod(nm, 0o666)
                    return target
        except Exception:
            pass

    platform = info.get("platform")
    if not platform:
        low = (url or "").lower()
        if "instagram.com" in low or "instagr.am" in low:
            platform = "Instagram"
        elif "tiktok.com" in low or "douyin.com" in low:
            platform = "TikTok"
        elif "youtube.com" in low or "youtu.be" in low:
            platform = "YouTube"
        elif "twitter.com" in low or "x.com" in low or "t.co" in low:
            platform = "Twitter"
        elif "facebook.com" in low or "fb.watch" in low or "fb.com" in low:
            platform = "Facebook"
        elif "pinterest.com" in low or "pin.it" in low:
            platform = "Pinterest"
        elif "reddit.com" in low or "redd.it" in low:
            platform = "Reddit"
        elif "threads.net" in low or "threads.com" in low:
            platform = "Threads"
        elif "bilibili.com" in low or "b23.tv" in low:
            platform = "Bilibili"
        elif "streamable.com" in low:
            platform = "Streamable"
        elif "bsky.app" in low:
            platform = "Bluesky"
        else:
            ext_key = str(info.get("extractor_key") or info.get("extractor") or "").strip()
            platform = ext_key if ext_key else "Media"

    author = info.get("channel") or info.get("uploader") or info.get("uploader_id") or info.get("author") or info.get("creator")
    if not author:
        m_ig = re.search(r'instagram\.com/([^/?#]+)/(?:p|reel|reels)/', url or "")
        if m_ig and m_ig.group(1) not in ("p", "reel", "reels", "tv", "explore"):
            author = m_ig.group(1)
        m_tt = re.search(r'tiktok\.com/@([^/?#]+)', url or "")
        if m_tt:
            author = m_tt.group(1)
        m_x = re.search(r'(?:twitter|x)\.com/([^/?#]+)/status', url or "")
        if m_x:
            author = m_x.group(1)
        m_bsky = re.search(r'bsky\.app/profile/([^/?#]+)', url or "")
        if m_bsky:
            author = m_bsky.group(1)

    clean_author = sanitize_filename(str(author).strip().lstrip("@")) if author else ""
    if clean_author.lower() in ("unknown", "null", "none", ""):
        clean_author = ""

    if platform and clean_author:
        target = os.path.join(base_outdir, platform, clean_author)
    elif platform:
        target = os.path.join(base_outdir, platform)
    else:
        target = base_outdir

    try:
        os.makedirs(target, exist_ok=True)
        os.chmod(target, 0o777)
    except Exception:
        pass
    return target

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"

def expand_shortlink_fast(url, timeout=3.5):
    """
    Ultra-fast shortlink expansion using HTTP HEAD/Range 0-0.
    Avoids downloading megabytes of landing page HTML just to get target URL.
    """
    low = url.lower()
    if not any(k in low for k in [
        "vt.tiktok.com", "vm.tiktok.com", "v.douyin.com",
        "fb.watch", "/share/", "t.co", "pin.it",
        "/s/", "redd.it", "bit.ly", "tinyurl.com", "is.gd"
    ]):
        return url

    class FastRedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            if code in (301, 302, 303, 307, 308):
                return urllib.request.Request(newurl, headers=req.headers, method="GET")
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

    if "tiktok.com" in res.lower() and "/video/" not in res.lower() and "/photo/" not in res.lower():
        return url
    if "instagram.com" in res.lower() and "/p/" not in res.lower() and "/reel/" not in res.lower() and "/tv/" not in res.lower():
        return url
    if "pinterest.com" in res.lower() and "/pin/" not in res.lower():
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
    if "ffmpeg" in low and ("not found" in low or "not installed" in low):
        return "FFmpeg postprocessing failed. Please verify module installation."
    if "http error 404" in low or "404 not found" in low or "404: not found" in low:
        return "Media not found (HTTP 404). Link may be expired or deleted."
    if "private video" in low or "login required" in low:
        return "Content is private or requires authentication. Please configure cookies."
    return msg

_last_notif_time = 0.0
_last_notif_pct = -1

def post_android_notification(status, percent=0, speed="", downloaded="", total="", title="", file_path="", error="", eta=""):
    """
    Post real-time download status to the Android system notification bar using /system/bin/cmd notification.
    Runs as UID 2000 (com.android.shell) so Android NotificationManager enqueues it cleanly.
    Single-line title and single-line body ensures zero literal escape sequences ('\n') on any Android OEM.
    """
    global _last_notif_time, _last_notif_pct

    if os.path.exists("/data/adb/hyperdl/disable_notifications"):
        return

    now = time.time()
    clean_title = (title or "Media").strip()
    clean_title = clean_title.replace("\r", " ").replace("\n", " ").strip()
    clean_title = re.sub(r'\s+', ' ', clean_title)
    if len(clean_title) > 65:
        clean_title = clean_title[:62] + "..."

    notif_title = "HyperDL"
    notif_text = ""

    if status == "resolving":
        notif_title = "HyperDL"
        notif_text = f"Connecting to source • {clean_title}" if clean_title != "Media" else "Connecting to media source..."
    elif status == "downloading":
        if (now - _last_notif_time < 2.0) and (abs(percent - _last_notif_pct) < 10):
            return
        if (now - _last_notif_time < 1.0):
            return

        notif_title = clean_title if clean_title != "Media" else "HyperDL • Downloading"
        
        details = []
        if percent > 0:
            details.append(f"{percent}%")
        if downloaded and downloaded not in ("N/A", "NA", "None", ""):
            if total and total not in ("N/A", "NA", "None", "?", ""):
                details.append(f"{downloaded} / {total}")
            else:
                details.append(downloaded)
        if speed and speed not in ("N/A", "NA", "None", ""):
            details.append(speed)
        if eta and eta not in ("N/A", "NA", "None", "null", "Unknown", ""):
            details.append(f"ETA {eta}")

        notif_text = " • ".join(details) if details else "Downloading media..."
        _last_notif_pct = percent
    elif status == "completed":
        fname = os.path.basename(file_path) if file_path else clean_title
        fname = fname.replace("\r", " ").replace("\n", " ").strip()
        fname = re.sub(r'\s+', ' ', fname)
        if len(fname) > 65:
            fname = fname[:62] + "..."
        notif_title = fname
        notif_text = "Download complete • Saved to /Download/HyperDL"
    elif status == "error":
        notif_title = "HyperDL • Download failed"
        err_msg = humanize_error(error) if error else "An unexpected error occurred"
        err_msg = err_msg.replace("\r", " ").replace("\n", " ").strip()
        err_msg = re.sub(r'\s+', ' ', err_msg)
        notif_text = err_msg
    elif status == "paused":
        notif_title = "HyperDL • Download paused"
        notif_text = f"{clean_title} ({percent}% ready)" if clean_title != "Media" else f"Download paused ({percent}% ready)"
    else:
        return

    _last_notif_time = now

    def _send():
        cmd = [
            "/system/bin/cmd", "notification", "post",
            "-t", notif_title,
            "hyperdl_task",
            notif_text
        ]
        try:
            if os.getuid() == 0:
                subprocess.run(
                    cmd,
                    preexec_fn=lambda: (os.setresgid(2000, 2000, 2000), os.setresuid(2000, 2000, 2000)),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2
                )
            else:
                subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2
                )
        except Exception:
            try:
                fallback_cmd = [
                    "/system/bin/cmd", "notification", "post",
                    "-t", notif_title,
                    "hyperdl_task",
                    notif_text
                ]
                if os.getuid() == 0:
                    subprocess.run(
                        fallback_cmd,
                        preexec_fn=lambda: (os.setresgid(2000, 2000, 2000), os.setresuid(2000, 2000, 2000)),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=2
                    )
                else:
                    subprocess.run(
                        fallback_cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=2
                    )
            except Exception:
                pass

    try:
        t = threading.Thread(target=_send, daemon=True)
        t.start()
        if status in ("completed", "error"):
            t.join(timeout=2.0)
    except Exception:
        pass

def update_status(status, percent=0, speed="", downloaded="", total="", title="", file_path="", error="", eta=""):
    global _last_status
    if percent > 0:
        _last_status["percent"] = percent
    elif percent == 0 and status in ("error", "paused") and _last_status.get("percent", 0) > 0:
        percent = _last_status["percent"]

    if downloaded:
        _last_status["downloaded"] = downloaded
    elif not downloaded and status in ("error", "paused") and _last_status.get("downloaded"):
        downloaded = _last_status["downloaded"]

    if total:
        _last_status["total"] = total
    elif not total and status in ("error", "paused") and _last_status.get("total"):
        total = _last_status["total"]

    if eta:
        _last_status["eta"] = eta
    elif not eta and status in ("error", "paused") and _last_status.get("eta"):
        eta = _last_status["eta"]

    if title:
        _last_status["title"] = title
    elif not title and _last_status.get("title"):
        title = _last_status["title"]

    data = {
        "status": status,
        "percent": percent,
        "speed": speed,
        "downloaded": downloaded,
        "total": total,
        "eta": eta if status == "downloading" else "",
        "title": title,
        "file_path": file_path,
        "error": humanize_error(error) if error else "",
        "timestamp": int(time.time()),
        "url": CURRENT_URL,
        "fmt": CURRENT_FMT,
        "format_id": CURRENT_FORMAT_ID,
        "height": CURRENT_HEIGHT
    }
    try:
        os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
        tmp_status = f"{STATUS_FILE}.tmp.{os.getpid()}"
        with open(tmp_status, "w") as f:
            json.dump(data, f)
        os.replace(tmp_status, STATUS_FILE)
        try:
            os.chmod(STATUS_FILE, 0o666)
        except Exception:
            pass
    except Exception:
        pass

    try:
        os.makedirs(CONF_DIR, exist_ok=True)
        tmp_active = f"{ACTIVE_TASK_FILE}.tmp.{os.getpid()}"
        with open(tmp_active, "w") as f:
            json.dump(data, f)
        os.replace(tmp_active, ACTIVE_TASK_FILE)
        try:
            os.chmod(ACTIVE_TASK_FILE, 0o666)
        except Exception:
            pass
    except Exception:
        pass

    print(json.dumps(data), flush=True)

    try:
        post_android_notification(
            status=status,
            percent=percent,
            speed=speed,
            downloaded=downloaded,
            total=total,
            title=title,
            file_path=file_path,
            error=error,
            eta=eta
        )
    except Exception:
        pass

def sanitize_filename(name):
    if not name:
        return "Media"
    clean = name.replace('#', ' ')
    clean = re.sub(r'[/\\:*?"<>|\n\r\t%&+=`$\'{}\[\]@;]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip(' ._-')
    return clean[:60] if clean else "Media"

def save_source_sidecar(file_path, url=""):
    if not file_path or not url:
        return
    url = (url or "").strip()
    if not url:
        return
    try:
        side = file_path + ".url.txt"
        if os.path.exists(side):
            return
        with open(side, "w") as f:
            f.write(url + "\n")
        try:
            os.chmod(side, 0o666)
        except Exception:
            pass
    except Exception:
        pass

def scan_media_file(file_path):
    if not file_path or not os.path.exists(file_path):
        return
    try:
        os.chmod(file_path, 0o666)
    except Exception:
        pass
    try:
        quoted = urllib.parse.quote(file_path)
        cmd = (
            f'(am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file://{quoted}" >/dev/null 2>&1; '
            f'content insert --uri content://media/external/file --bind _data:s:"{file_path}" >/dev/null 2>&1) &'
        )
        os.system(cmd)
    except Exception:
        pass

def send_android_notification(title, text):
    try:
        post_android_notification(status="completed", title=title, file_path=text)
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
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        save_source_sidecar(out_path, CURRENT_URL or url)
        if emit_complete:
            update_status("completed", percent=100, title=title, file_path=out_path)
        return out_path

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    part_path = out_path + ".part"

    hdrs = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Connection": "keep-alive"
    }
    if headers:
        hdrs.update(headers)

    existing_bytes = 0
    if os.path.exists(part_path):
        try:
            existing_bytes = os.path.getsize(part_path)
        except Exception:
            existing_bytes = 0
        if existing_bytes > 0:
            hdrs["Range"] = f"bytes={existing_bytes}-"

    req = urllib.request.Request(url, headers=hdrs)
    try:
        try:
            resp = urllib.request.urlopen(req, timeout=40)
        except urllib.error.HTTPError as e:
            if e.code == 416 and existing_bytes > 0:
                os.replace(part_path, out_path)
                try:
                    os.chmod(out_path, 0o666)
                except Exception:
                    pass
                scan_media_file(out_path)
                if emit_complete:
                    update_status("completed", percent=100, title=title, file_path=out_path)
                return out_path
            if "Range" in hdrs:
                del hdrs["Range"]
                if os.path.exists(part_path):
                    try:
                        os.remove(part_path)
                    except Exception:
                        pass
                existing_bytes = 0
                req = urllib.request.Request(url, headers=hdrs)
                resp = urllib.request.urlopen(req, timeout=40)
            else:
                raise

        with resp:
            is_resume = (resp.status == 206)
            if is_resume:
                open_mode = "ab"
                downloaded = existing_bytes
                total_bytes = 0
                cr = resp.headers.get('content-range')
                if cr and '/' in cr:
                    tot_str = cr.split('/')[-1].strip()
                    if tot_str.isdigit():
                        total_bytes = int(tot_str)
                if not total_bytes:
                    cl = int(resp.headers.get('content-length', 0) or 0)
                    total_bytes = downloaded + cl if cl > 0 else 0
            else:
                open_mode = "wb"
                downloaded = 0
                total_bytes = int(resp.headers.get('content-length', 0) or 0)

            start_time = time.time()
            last_update = 0
            bytes_this_session = 0

            with open(part_path, open_mode, buffering=1024 * 1024) as f:
                while True:
                    read_size = 512 * 1024
                    if total_bytes > 0:
                        remaining = total_bytes - downloaded
                        if remaining <= 0:
                            break
                        if remaining < read_size:
                            read_size = remaining

                    chunk = resp.read(read_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    bytes_this_session += len(chunk)

                    now = time.time()
                    if now - last_update >= 0.25:
                        last_update = now
                        elapsed = max(now - start_time, 0.001)
                        speed_bps = bytes_this_session / elapsed
                        speed_str = f"{speed_bps / (1024*1024):.1f} MB/s" if speed_bps >= 1024*1024 else f"{speed_bps / 1024:.0f} KB/s"
                        
                        pct = int((downloaded / total_bytes * 100)) if total_bytes > 0 else 50
                        dl_str = f"{downloaded / (1024*1024):.1f} MB"
                        tot_str = f"{total_bytes / (1024*1024):.1f} MB" if total_bytes > 0 else ""
                        
                        rem = max(total_bytes - downloaded, 0) if total_bytes > 0 else 0
                        eta_str = ""
                        if rem > 0 and speed_bps > 0:
                            s = int(rem / speed_bps)
                            eta_str = f"{s // 60:02d}:{s % 60:02d}" if s < 3600 else f"{s // 3600}h {s % 3600 // 60}m"

                        update_status("downloading", percent=pct, speed=speed_str, downloaded=dl_str, total=tot_str, title=title, eta=eta_str)

                    if total_bytes > 0 and downloaded >= total_bytes:
                        break

            if not os.path.exists(part_path) or os.path.getsize(part_path) == 0:
                raise RuntimeError("Downloaded file is empty")
            if total_bytes > 0 and downloaded < total_bytes:
                raise RuntimeError(f"Downloaded file is incomplete ({downloaded}/{total_bytes} bytes)")

            os.replace(part_path, out_path)

            try:
                os.chmod(out_path, 0o666)
            except Exception:
                pass

            scan_media_file(out_path)
            save_source_sidecar(out_path, CURRENT_URL)

            if emit_complete:
                update_status("completed", percent=100, title=title, file_path=out_path)
            return out_path
    except Exception as e:
        if emit_error:
            update_status("error", error=str(e), title=title)
        raise

def download_hls(m3u8_url, out_path, title="Media", headers=None, emit_complete=True):
    ffmpeg_bin = get_ffmpeg_binary()
    env = get_ffmpeg_env()
    if ffmpeg_bin:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        part_path = out_path + ".tmp.mp4"
        if os.path.exists(part_path):
            try:
                os.remove(part_path)
            except Exception:
                pass
        
        hdr_args = []
        user_agent = (headers or {}).get("User-Agent") or USER_AGENT
        hdr_str = f"User-Agent: {user_agent}\r\n"
        if headers:
            for k, v in headers.items():
                if k.lower() != "user-agent":
                    hdr_str += f"{k}: {v}\r\n"
        hdr_args = ["-headers", hdr_str]

        cmd = [
            ffmpeg_bin,
            "-y",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
        ] + hdr_args + [
            "-i", m3u8_url,
            "-c", "copy",
            "-movflags", "+faststart",
            "-f", "mp4",
            part_path
        ]
        update_status("downloading", percent=35, title=f"Downloading: {title}")
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if res.returncode == 0 and os.path.exists(part_path) and os.path.getsize(part_path) > 1024:
            os.replace(part_path, out_path)
            try:
                os.chmod(out_path, 0o666)
            except Exception:
                pass
            scan_media_file(out_path)
            save_source_sidecar(out_path, CURRENT_URL if m3u8_url == CURRENT_URL else m3u8_url)
            if emit_complete:
                update_status("completed", percent=100, title=title, file_path=out_path)
            return out_path

    outdir = os.path.dirname(out_path) or "."
    return download_with_ytdlp_direct(m3u8_url, outdir, fmt="video")

def download_media_candidates(item, out_path, title, emit_complete=True):
    if item.get("direct_ytdlp"):
        outdir = os.path.dirname(out_path) or "."
        return download_with_ytdlp_direct(item["url"], outdir, fmt=item.get("fmt", "video"), is_yt=item.get("is_yt", False), is_playlist=item.get("is_playlist", False))

    if item.get("is_m3u8") or str(item.get("url", "")).endswith(".m3u8"):
        return download_hls(item["url"], out_path, title=title, headers=item.get("headers"), emit_complete=emit_complete)

    if item.get("audio_url"):
        ffmpeg_bin = get_ffmpeg_binary()
        if ffmpeg_bin:
            tmp_v = out_path + ".tmp_v.mp4"
            tmp_a = out_path + ".tmp_a.m4a"
            hdrs = item.get("headers") or {}
            download_file(item["url"], tmp_v, title=f"{title} [Video]", headers=hdrs, emit_error=True, emit_complete=False)
            download_file(item["audio_url"], tmp_a, title=f"{title} [Audio]", headers=hdrs, emit_error=True, emit_complete=False)
            update_status("downloading", percent=98, title=f"{title} (Muxing audio & video...)")
            res = subprocess.run([ffmpeg_bin, "-y", "-i", tmp_v, "-i", tmp_a, "-c", "copy", out_path], env=get_ffmpeg_env(), capture_output=True)
            for tmp_f in (tmp_v, tmp_a):
                if os.path.exists(tmp_f):
                    try:
                        os.remove(tmp_f)
                    except Exception:
                        pass
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                try:
                    os.chmod(out_path, 0o666)
                except Exception:
                    pass
                scan_media_file(out_path)
                save_source_sidecar(out_path, CURRENT_URL)
                if emit_complete:
                    update_status("completed", percent=100, title=title, file_path=out_path)
                return out_path
        return download_file(item["url"], out_path, title=title, headers=item.get("headers"), emit_error=True, emit_complete=emit_complete)

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
                    return download_with_ytdlp_direct(fb_item["url"], outdir, fmt=fb_item.get("fmt", "video"), is_yt=fb_item.get("is_yt", False), is_playlist=fb_item.get("is_playlist", False))
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
                media_id = str(d.get("id") or "")
                author = (d.get("author") or {}).get("unique_id") or (d.get("author") or {}).get("nickname") or ""
                
                if fmt == "audio":
                    music_url = d.get("music") or (d.get("music_info") or {}).get("play")
                    if music_url:
                        return {
                            "title": title,
                            "ext": "mp3",
                            "kind": "audio",
                            "id": media_id,
                            "channel": author,
                            "platform": "TikTok",
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
                        "id": media_id,
                        "channel": author,
                        "platform": "TikTok",
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
                            "id": media_id,
                            "channel": author,
                            "platform": "TikTok",
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
                media_id = str(item.get("id") or item.get("aweme_id") or "")
                author = (item.get("author") or {}).get("unique_id") or (item.get("author") or {}).get("nickname") or ""
                
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
                            "id": media_id,
                            "channel": author,
                            "platform": "TikTok",
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
                            "id": media_id,
                            "channel": author,
                            "platform": "TikTok",
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
                        "id": media_id,
                        "channel": author,
                        "platform": "TikTok",
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

def is_progressive_instagram_format(f):
    if not f or not f.get("url"):
        return False
    fid = str(f.get("format_id", "")).lower()
    if fid.startswith("dash-") or fid.endswith("a") or fid.endswith("v"):
        return False
    vcodec = str(f.get("vcodec", "")).lower()
    acodec = str(f.get("acodec", "")).lower()
    if vcodec == "none" or acodec == "none":
        return False
    ext = str(f.get("ext", "")).lower()
    vext = str(f.get("video_ext", "")).lower()
    return ext == "mp4" or vext == "mp4"

def resolve_instagram(url, fmt="video"):
    update_status("resolving", title="Resolving Instagram media...")
    clean_url = expand_shortlink_fast(url, timeout=3.5)
    shortcode_match = re.search(r'/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)', clean_url)
    if not shortcode_match:
        return {
            "direct_ytdlp": True,
            "url": clean_url,
            "fmt": fmt,
            "is_yt": False,
            "title": "Instagram Media"
        }
    shortcode = shortcode_match.group(1)

    if fmt == "video":
        try:
            crawler_hdrs = {
                "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9"
            }
            probe_path = "reel" if ("/reel/" in clean_url or "/reels/" in clean_url) else "p"
            req = urllib.request.Request(f"https://www.instagram.com/{probe_path}/{shortcode}/", headers=crawler_hdrs)
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            
            og_vid = re.search(r'property=["\']og:video(?::secure_url)?["\']\s+content=["\']([^"\']+)["\']', html)
            if og_vid:
                vurl = pyhtml.unescape(og_vid.group(1)).replace("&amp;", "&")
                og_title = re.search(r'property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html)
                author = None
                raw_title = f"Instagram_{shortcode}"
                if og_title:
                    t_str = pyhtml.unescape(og_title.group(1))
                    m_auth = re.search(r'\(@([A-Za-z0-9_.]+)\)', t_str)
                    if m_auth:
                        author = m_auth.group(1)
                    raw_title = t_str.split("on Instagram:")[0].strip() if "on Instagram:" in t_str else t_str
                return {
                    "url": vurl,
                    "title": raw_title,
                    "ext": "mp4",
                    "kind": "video",
                    "id": shortcode,
                    "channel": author,
                    "platform": "Instagram"
                }
        except Exception:
            pass

    try:
        ytdlp_bin = get_or_download_ytdlp()
        if ytdlp_bin and ytdlp_bin not in sys.path:
            sys.path.insert(0, ytdlp_bin)
        from yt_dlp import YoutubeDL

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }
        if os.path.exists(COOKIES_PATH):
            ydl_opts["cookiefile"] = COOKIES_PATH

        with YoutubeDL(ydl_opts) as ydl:
            ie = ydl.get_info_extractor("Instagram")
            info = ie.extract(clean_url)

        raw_title = info.get("title") or f"Instagram_{shortcode}"
        title = sanitize_filename(re.sub(r'[\r\n\t]+', ' ', raw_title).strip()) or f"Instagram_{shortcode}"

        if info.get("_type") == "playlist":
            entries = list(info.get("entries") or [])
            items = []
            for e in entries:
                if not e:
                    continue
                vurl = None
                aurl = None
                e_formats = e.get("formats") or []
                prog = [f for f in e_formats if is_progressive_instagram_format(f)]
                if prog:
                    best_prog = max(prog, key=lambda f: (f.get("width") or 0) * (f.get("height") or 0) or (f.get("tbr") or 0))
                    vurl = best_prog.get("url")
                elif e_formats:
                    v_fmts = [f for f in e_formats if (f.get("vcodec") and f.get("vcodec") != "none") or str(f.get("format_id", "")).endswith("v") or ".mp4" in str(f.get("url", "")).lower()]
                    a_fmts = [f for f in e_formats if (f.get("acodec") and f.get("acodec") != "none") or str(f.get("format_id", "")).endswith("a") or f.get("ext") in ("m4a", "aac")]
                    if v_fmts:
                        best_v = max(v_fmts, key=lambda f: (f.get("height") or 0) * (f.get("width") or 0) or (f.get("tbr") or 0))
                        vurl = best_v.get("url")
                        if a_fmts:
                            best_a = max(a_fmts, key=lambda f: (f.get("abr") or 0) or (f.get("tbr") or 0))
                            aurl = best_a.get("url")
                elif e.get("url") and (".mp4" in str(e.get("url")).lower() or e.get("ext") == "mp4"):
                    vurl = e.get("url")

                if vurl:
                    items.append({"url": vurl, "audio_url": aurl, "ext": "mp4", "kind": "video"})
                else:
                    thumbs = e.get("thumbnails") or []
                    img_url = None
                    if thumbs:
                        if any((t.get("width") or 0) > 0 for t in thumbs):
                            best_t = max(thumbs, key=lambda t: (t.get("width") or 0) * (t.get("height") or 0))
                            img_url = best_t.get("url")
                        else:
                            img_url = thumbs[-1].get("url")
                    if not img_url and e.get("url"):
                        img_url = e.get("url")
                    if img_url:
                        items.append({"url": img_url, "ext": "jpg", "kind": "image"})

            if items:
                author_channel = info.get("channel") or info.get("uploader") or info.get("uploader_id")
                if fmt in ("photo", "image"):
                    photo_items = [it for it in items if it.get("kind") == "image"]
                    if photo_items:
                        return {
                            "items": photo_items, "title": title, "ext": "jpg", "kind": "album",
                            "id": shortcode, "platform": "Instagram", "channel": author_channel, "uploader": info.get("uploader")
                        }
                if fmt == "audio":
                    aud_item = next((it for it in items if it.get("audio_url") or it.get("kind") == "video"), None)
                    if aud_item:
                        return {
                            **aud_item, "title": title,
                            "id": shortcode, "platform": "Instagram", "channel": author_channel, "uploader": info.get("uploader")
                        }

                return {
                    "items": items,
                    "title": title,
                    "ext": "mp4" if any(it.get("kind") == "video" for it in items) else "jpg",
                    "kind": "album",
                    "id": shortcode,
                    "platform": "Instagram",
                    "channel": author_channel,
                    "uploader": info.get("uploader")
                }
        else:
            author_channel = info.get("channel") or info.get("uploader") or info.get("uploader_id")
            formats = info.get("formats") or []
            prog_formats = [f for f in formats if is_progressive_instagram_format(f)]
            v_fmts = [f for f in formats if (f.get("vcodec") and f.get("vcodec") != "none") or str(f.get("format_id", "")).endswith("v") or ".mp4" in str(f.get("url", "")).lower()]

            if prog_formats and fmt not in ("photo", "image"):
                best_prog = max(prog_formats, key=lambda f: (f.get("width") or 0) * (f.get("height") or 0) or (f.get("tbr") or 0))
                return {
                    "url": best_prog.get("url"), "title": title, "ext": "mp4", "kind": "video",
                    "id": shortcode, "platform": "Instagram", "channel": author_channel, "uploader": info.get("uploader"),
                    "fallback": lambda: {"direct_ytdlp": True, "url": clean_url, "fmt": fmt, "is_yt": False, "title": title, "platform": "Instagram", "channel": author_channel, "id": shortcode}
                }

            if v_fmts and fmt not in ("photo", "image"):
                return {
                    "direct_ytdlp": True,
                    "url": clean_url,
                    "fmt": fmt,
                    "is_yt": False,
                    "title": title,
                    "id": shortcode,
                    "platform": "Instagram",
                    "channel": author_channel,
                    "uploader": info.get("uploader")
                }

            info_url = info.get("url") or ""
            is_info_video = (
                (info.get("vcodec") and info.get("vcodec") != "none") or
                info.get("ext") == "mp4" or
                ".mp4" in info_url.lower() or
                ".m3u8" in info_url.lower()
            )
            if info_url and is_info_video and fmt not in ("photo", "image"):
                return {
                    "url": info_url, "title": title, "ext": "mp4", "kind": "video",
                    "id": shortcode, "platform": "Instagram", "channel": author_channel, "uploader": info.get("uploader")
                }

            if fmt != "audio":
                img_url = None
                if info_url and not is_info_video:
                    img_url = info_url
                if not img_url:
                    thumbs = info.get("thumbnails") or []
                    if thumbs:
                        if any((t.get("width") or 0) > 0 for t in thumbs):
                            best = max(thumbs, key=lambda t: (t.get("width") or 0) * (t.get("height") or 0))
                        else:
                            best = thumbs[-1]
                        img_url = best.get("url")
                if img_url:
                    img_ext = "jpg"
                    if ".png" in img_url.lower():
                        img_ext = "png"
                    elif ".webp" in img_url.lower():
                        img_ext = "webp"
                    return {
                        "url": img_url, "title": title, "ext": img_ext, "kind": "image",
                        "id": shortcode, "platform": "Instagram", "channel": author_channel, "uploader": info.get("uploader")
                    }
    except Exception as e:
        print(f"Instagram yt_dlp extractor note: {e}", file=sys.stderr)

    return {
        "direct_ytdlp": True,
        "url": clean_url,
        "fmt": fmt,
        "is_yt": False,
        "title": f"Instagram_{shortcode}",
        "platform": "Instagram"
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

        if fmt not in ("audio", "video"):
            og_img = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html) or \
                     re.search(r'content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html)
            if og_img:
                img_u = pyhtml.unescape(og_img.group(1)).replace("&amp;", "&")
                if img_u and not any(bad in img_u.lower() for bad in ("facebook_logo", "rsrc.php", "fb_logo")):
                    return {"url": img_u, "title": title, "ext": "jpg", "kind": "image", "platform": "Facebook"}
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

    if "pin.it" in clean_url.lower():
        try:
            req = urllib.request.Request(clean_url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            })
            with urllib.request.urlopen(req, timeout=5) as resp:
                final_u = resp.geturl()
                if "/pin/" in final_u:
                    clean_url = final_u
        except urllib.error.HTTPError as e:
            loc = e.headers.get("Location") or e.headers.get("location")
            if loc and "/pin/" in loc:
                clean_url = loc
        except Exception:
            pass

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
            pin = d.get("resource_response", {}).get("data") or {}
            raw_title = pin.get("title") or pin.get("grid_title") or pin.get("description") or f"Pinterest_{pin_id}"
            title = re.sub(r'[\r\n\t]+', ' ', raw_title).strip() or f"Pinterest_{pin_id}"

            videos = (pin.get("videos") or {}).get("video_list") or {}
            if isinstance(videos, dict) and videos:
                mp4s = [v.get("url") for k, v in videos.items() if v.get("url") and not str(v.get("url")).endswith(".m3u8")]
                if mp4s:
                    return {"url": mp4s[0], "title": title, "ext": "mp4", "kind": "video"}
                m3u8s = [v.get("url") for k, v in videos.items() if v.get("url")]
                if m3u8s:
                    return {"url": m3u8s[0], "title": title, "ext": "mp4", "kind": "video", "is_m3u8": True}

            story = pin.get("story_pin_data") or {}
            if isinstance(story, dict):
                for page in story.get("pages", []):
                    for block in page.get("blocks", []):
                        if int(block.get("block_type") or 0) == 3 and isinstance(block.get("video"), dict):
                            vlist = (block.get("video") or {}).get("video_list") or {}
                            mp4s = [v.get("url") for k, v in vlist.items() if v.get("url") and not str(v.get("url")).endswith(".m3u8")]
                            if mp4s:
                                return {"url": mp4s[0], "title": title, "ext": "mp4", "kind": "video"}
                            m3u8s = [v.get("url") for k, v in vlist.items() if v.get("url")]
                            if m3u8s:
                                return {"url": m3u8s[0], "title": title, "ext": "mp4", "kind": "video", "is_m3u8": True}

            if isinstance(story, dict) and fmt != "audio":
                story_imgs = []
                for page in story.get("pages", []):
                    for block in page.get("blocks", []):
                        img_obj = block.get("image") or {}
                        if isinstance(img_obj, dict):
                            i_url = (img_obj.get("images", {}).get("orig", {}) or {}).get("url")
                            if i_url:
                                story_imgs.append(i_url)
                if story_imgs:
                    if len(story_imgs) == 1:
                        return {"url": story_imgs[0], "title": title, "ext": "jpg", "kind": "image", "platform": "Pinterest", "id": pin_id}
                    return {"images": story_imgs, "title": title, "ext": "jpg", "kind": "album", "platform": "Pinterest", "id": pin_id}

            if fmt != "audio":
                images = pin.get("images") or {}
                orig = images.get("orig") or {} if isinstance(images, dict) else {}
                if orig.get("url"):
                    ext = "png" if ".png" in str(orig["url"]).lower() else "jpg"
                    return {"url": orig["url"], "title": title, "ext": ext, "kind": "image", "platform": "Pinterest", "id": pin_id}
        except Exception as e:
            print(f"Pinterest API note: {e}", file=sys.stderr)

        if fmt not in ("audio", "video"):
            try:
                req_html = urllib.request.Request(clean_url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req_html, timeout=4) as resp:
                    p_html = resp.read().decode("utf-8", errors="ignore")
                og_img = re.search(r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', p_html)
                if og_img:
                    img_u = pyhtml.unescape(og_img.group(1)).replace("&amp;", "&")
                    if img_u:
                        ext = "png" if ".png" in img_u.lower() else "jpg"
                        return {"url": img_u, "title": f"Pinterest_{pin_id}", "ext": ext, "kind": "image", "platform": "Pinterest", "id": pin_id}
            except Exception:
                pass

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
            for f in as_completed(futures):
                try:
                    data = f.result()
                    if isinstance(data, list) and data:
                        post_root = ((data[0] or {}).get("data") or {})
                        children = post_root.get("children") or [{}]
                        post = ((children[0] or {}).get("data")) or {}
                        title = post.get("title") or "Reddit Media"

                        gallery = (post.get("media_metadata") or {})
                        if isinstance(gallery, dict) and gallery:
                            images = []
                            for k, meta in gallery.items():
                                meta = (meta or {})
                                s_obj = (meta.get("s") or {})
                                src = s_obj.get("u") or s_obj.get("mp4")
                                if src:
                                    images.append(pyhtml.unescape(src).replace("&amp;", "&"))
                            if images:
                                return {"images": images, "title": title, "ext": "jpg", "kind": "album"}

                        post_url = pyhtml.unescape(post.get("url") or "")
                        if any(ext in post_url.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")):
                            ext = "png" if ".png" in post_url.lower() else "jpg"
                            return {"url": post_url, "title": title, "ext": ext, "kind": "image", "platform": "Reddit"}

                        media = post.get("media") or post.get("secure_media") or ((post.get("preview") or {}).get("reddit_video_preview"))
                        media = (media or {})
                        rv = (media.get("reddit_video") if isinstance(media.get("reddit_video"), dict) else media) or {}
                        fallback = rv.get("fallback_url")
                        if fallback:
                            return {
                                "url": fallback,
                                "title": title,
                                "ext": "mp4",
                                "kind": "video"
                            }

                        if fmt in ("photo", "image", "album"):
                            preview_imgs = ((post.get("preview") or {}).get("images")) or []
                            if preview_imgs:
                                src_u = (((preview_imgs[0] or {}).get("source")) or {}).get("url")
                                if src_u:
                                    clean_src = pyhtml.unescape(src_u).replace("&amp;", "&")
                                    ext = "png" if ".png" in clean_src.lower() else "jpg"
                                    return {"url": clean_src, "title": title, "ext": ext, "kind": "image", "platform": "Reddit"}
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
    m_auth = re.search(r'(?:twitter|x)\.com/([^/?#]+)/status', clean_url)
    author = m_auth.group(1) if m_auth and m_auth.group(1) not in ("i", "intent", "search") else ""

    cookie_hdr = get_cookie_header("x.com") or get_cookie_header("twitter.com")
    cookies_map = load_cookies("x.com")
    if not cookies_map:
        cookies_map = load_cookies("twitter.com")

    csrf = cookies_map.get("ct0")
    auth_token = cookies_map.get("auth_token")

    if csrf and auth_token and cookie_hdr:
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
                fb_lambda = lambda: {"direct_ytdlp": True, "url": clean_url, "fmt": fmt, "is_yt": False, "title": title, "channel": author, "id": status_id, "platform": "Twitter"}
                has_video_in_media = False
                images = []
                for media in media_list:
                    mtype = str(media.get("type") or "").lower()
                    if mtype in ("video", "animated_gif"):
                        has_video_in_media = True
                        variants = media.get("video_info", {}).get("variants", [])
                        mp4s = [v for v in variants if v.get("content_type") == "video/mp4" and v.get("url")]
                        if mp4s:
                            mp4s.sort(key=lambda x: int(x.get("bitrate") or 0), reverse=True)
                            if fmt == "audio":
                                return {"url": mp4s[-1]["url"], "title": title, "ext": "mp4", "kind": "video", "id": status_id, "channel": author, "platform": "Twitter", "fallback": fb_lambda}
                            return {"url": mp4s[0]["url"], "title": title, "ext": "mp4", "kind": "video", "id": status_id, "channel": author, "platform": "Twitter", "fallback": fb_lambda}
                    elif mtype == "photo":
                        p_url = media.get("media_url_https")
                        if p_url:
                            images.append(p_url)
                if has_video_in_media:
                    return fb_lambda()
                if images and fmt != "audio":
                    fb_album = lambda: {"direct_ytdlp": True, "url": clean_url, "fmt": "album", "is_yt": False, "title": title, "channel": author, "id": status_id, "platform": "Twitter"}
                    if len(images) == 1:
                        return {"url": images[0], "title": title, "ext": "jpg", "kind": "image", "id": status_id, "channel": author, "platform": "Twitter", "fallback": fb_album}
                    return {"images": images, "title": title, "ext": "jpg", "kind": "album", "id": status_id, "channel": author, "platform": "Twitter", "fallback": fb_album}
        except Exception as e:
            print(f"Twitter GraphQL API note: {e}", file=sys.stderr)

    guest_endpoints = [
        f"https://api.fxtwitter.com/status/{status_id}",
        f"https://cdn.syndication.twimg.com/tweet-result?id={status_id}&token=4"
    ]

    def query_guest_ep(ep):
        req = urllib.request.Request(ep, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            return ep, json.loads(resp.read().decode("utf-8"))

    results = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(query_guest_ep, ep): ep for ep in guest_endpoints}
        for f in as_completed(futures):
            try:
                ep, data = f.result()
                if data and isinstance(data, dict):
                    results.append((ep, data))
            except Exception:
                continue

    has_video_indicator = False
    for ep, data in results:
        data = (data or {})
        tweet_fallback = (data.get("tweet") or {})
        title = data.get("text") or tweet_fallback.get("text") or f"Tweet_{status_id}"
        g_auth = ((data.get("author") or {}).get("screen_name")) or data.get("user_screen_name") or author
        fb_lambda = lambda: {"direct_ytdlp": True, "url": clean_url, "fmt": fmt, "is_yt": False, "title": title, "channel": g_auth, "id": status_id, "platform": "Twitter"}

        v_url = None
        if "fxtwitter" in ep or "vxtwitter" in ep:
            v_url = data.get("video_url") or None
            for m in (data.get("media_extended") or []):
                if str((m or {}).get("type", "")).lower() in ("video", "animated_gif", "gif"):
                    has_video_indicator = True
                    if (m or {}).get("url") and not v_url:
                        v_url = (m or {}).get("url")
            if data.get("video_url"):
                has_video_indicator = True
            tweet_obj = (data.get("tweet") or {})
            media_obj = (tweet_obj.get("media") or {})
            vids = media_obj.get("videos") or []
            if vids:
                has_video_indicator = True
                if (vids[0] or {}).get("url") and not v_url:
                    v_url = (vids[0] or {}).get("url")
        elif "syndication" in ep:
            for md in (data.get("mediaDetails") or []):
                md = (md or {})
                if str(md.get("type", "")).lower() in ("video", "animated_gif"):
                    has_video_indicator = True
                    variants = ((md.get("video_info") or {}).get("variants")) or []
                    mp4s = [v for v in variants if (v or {}).get("content_type") == "video/mp4" and (v or {}).get("url")]
                    if mp4s and not v_url:
                        mp4s.sort(key=lambda x: int((x or {}).get("bitrate") or 0), reverse=True)
                        v_url = (mp4s[0] or {}).get("url")
            if ((data.get("video") or {}).get("variants")):
                has_video_indicator = True
                if not v_url:
                    variants = ((data.get("video") or {}).get("variants")) or []
                    mp4s = [v for v in variants if (v or {}).get("content_type") == "video/mp4" and (v or {}).get("url")]
                    if mp4s:
                        mp4s.sort(key=lambda x: int((x or {}).get("bitrate") or 0), reverse=True)
                        v_url = (mp4s[0] or {}).get("url")

        if not v_url and data.get("video_url"):
            has_video_indicator = True
            v_url = data.get("video_url")

        if v_url:
            return {"url": v_url, "title": title, "ext": "mp4", "kind": "video", "id": status_id, "channel": g_auth, "platform": "Twitter", "fallback": fb_lambda}

    if has_video_indicator:
        return {
            "direct_ytdlp": True,
            "url": clean_url,
            "fmt": fmt,
            "is_yt": False,
            "title": f"Tweet_{status_id}",
            "id": status_id,
            "channel": author,
            "platform": "Twitter"
        }

    if fmt != "audio":
        for ep, data in results:
            data = (data or {})
            tweet_fallback_p = (data.get("tweet") or {})
            title = data.get("text") or tweet_fallback_p.get("text") or f"Tweet_{status_id}"
            g_auth = ((data.get("author") or {}).get("screen_name")) or data.get("user_screen_name") or author
            fb_lambda = lambda: {"direct_ytdlp": True, "url": clean_url, "fmt": fmt, "is_yt": False, "title": title, "channel": g_auth, "id": status_id, "platform": "Twitter"}

            photos = []
            if "fxtwitter" in ep or "vxtwitter" in ep:
                tweet_obj_p = (data.get("tweet") or {})
                media_obj_p = (tweet_obj_p.get("media") or {})
                photos = [p.get("url") for p in (media_obj_p.get("photos") or []) if (p or {}).get("url")]
                if not photos:
                    m_ext = data.get("media_extended") or []
                    if m_ext:
                        photos = [m.get("url") for m in m_ext if str((m or {}).get("type", "")).lower() == "image" and (m or {}).get("url")]
                    elif data.get("mediaURLs"):
                        photos = [u for u in (data.get("mediaURLs") or []) if u]
            elif "syndication" in ep:
                photos = [(p or {}).get("url") for p in (data.get("photos") or []) if (p or {}).get("url")]

            if photos:
                fb_album = lambda: {"direct_ytdlp": True, "url": clean_url, "fmt": "album", "is_yt": False, "title": title, "channel": g_auth, "id": status_id, "platform": "Twitter"}
                if len(photos) == 1:
                    return {"url": photos[0], "title": title, "ext": "jpg", "kind": "image", "id": status_id, "channel": g_auth, "platform": "Twitter", "fallback": fb_album}
                return {"images": photos, "title": title, "ext": "jpg", "kind": "album", "id": status_id, "channel": g_auth, "platform": "Twitter", "fallback": fb_album}

    return {
        "direct_ytdlp": True,
        "url": clean_url,
        "fmt": fmt,
        "is_yt": False,
        "title": f"Tweet_{status_id}",
        "id": status_id,
        "channel": author,
        "platform": "Twitter"
    }

YTDLP_DOWNLOAD_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"

def _repack_pyc(src_zip, dst_zip):
    import tempfile, compileall, zipfile
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(src_zip, "r") as z:
            z.extractall(tmpdir)
        compileall.compile_dir(tmpdir, force=True, quiet=1, legacy=True)
        for root, dirs, files in os.walk(tmpdir):
            for f in files:
                if f.endswith(".py"):
                    os.remove(os.path.join(root, f))
        with open(dst_zip, "wb") as of:
            of.write(b"#!/usr/bin/env python3\n")
            with zipfile.ZipFile(of, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                for root, dirs, files in os.walk(tmpdir):
                    for f in files:
                        full = os.path.join(root, f)
                        z.write(full, os.path.relpath(full, tmpdir))

def get_or_download_ytdlp():
    candidates = [
        "/data/adb/modules/hyperdl/bin/yt-dlp",
        "/data/adb/modules/hyperdl/system/bin/yt-dlp",
        "/data/adb/modules_update/hyperdl/bin/yt-dlp",
        "/data/adb/modules_update/hyperdl/system/bin/yt-dlp",
        os.path.join(CONF_DIR, "bin", "yt-dlp"),
        os.path.join(CONF_DIR, "yt-dlp"),
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
        opt_path = tmp_path + ".opt"
        _repack_pyc(tmp_path, opt_path)
        os.replace(opt_path, tmp_path)
    except Exception as opt_err:
        print(f"Bytecode optimizer note: {opt_err}", file=sys.stderr)

    os.chmod(tmp_path, 0o755)
    os.replace(tmp_path, target_path)
    return target_path

def get_ytdlp_local_version():
    ytdlp_bin = get_or_download_ytdlp()
    py_bin = get_python_binary()
    try:
        res = subprocess.run([py_bin, ytdlp_bin, "--version"], capture_output=True, text=True, timeout=5, env=get_runtime_env())
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "Unknown"

def check_ytdlp_version_api():
    cur_ver = get_ytdlp_local_version()
    latest_ver = cur_ver
    try:
        req = urllib.request.Request("https://github.com/yt-dlp/yt-dlp/releases/latest", method="HEAD", headers={"User-Agent": USER_AGENT})
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
        with opener.open(req, timeout=6) as r:
            latest_ver = r.geturl().split("/")[-1].strip()
    except Exception as e:
        print(f"Check ytdlp release note: {e}", file=sys.stderr)

    has_update = bool(cur_ver and latest_ver and cur_ver != "Unknown" and cur_ver != latest_ver)
    return {
        "current": cur_ver,
        "latest": latest_ver,
        "has_update": has_update
    }

def perform_ytdlp_update():
    target_paths = [
        "/data/adb/modules/hyperdl/bin/yt-dlp",
        "/data/adb/modules/hyperdl/system/bin/yt-dlp",
        "/data/adb/modules_update/hyperdl/bin/yt-dlp",
        "/data/adb/modules_update/hyperdl/system/bin/yt-dlp",
        os.path.join(CONF_DIR, "bin", "yt-dlp"),
    ]

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dl = os.path.join(tmpdir, "raw_ytdlp")
        req = urllib.request.Request(YTDLP_DOWNLOAD_URL, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as resp, open(raw_dl, "wb") as f:
            f.write(resp.read())

        opt_path = os.path.join(tmpdir, "opt_ytdlp")
        _repack_pyc(raw_dl, opt_path)

        py_bin = get_python_binary()
        ver_res = subprocess.run([py_bin, opt_path, "--version"], capture_output=True, text=True, timeout=5, env=get_runtime_env())
        if ver_res.returncode != 0 or not ver_res.stdout.strip():
            return {"success": False, "error": "Verification failed after optimization"}

        new_ver = ver_res.stdout.strip()

        updated_any = False
        for tp in target_paths:
            if os.path.exists(os.path.dirname(tp)):
                try:
                    shutil.copyfile(opt_path, tp)
                    os.chmod(tp, 0o755)
                    updated_any = True
                except Exception:
                    pass

        if not updated_any:
            cb = os.path.join(CONF_DIR, "bin")
            os.makedirs(cb, exist_ok=True)
            tp = os.path.join(cb, "yt-dlp")
            shutil.copyfile(opt_path, tp)
            os.chmod(tp, 0o755)

        return {"success": True, "version": new_ver}

def get_module_local_prop():
    candidates = [
        "/data/adb/modules/hyperdl/module.prop",
        "/data/adb/modules_update/hyperdl/module.prop",
    ]
    props = {"version": "v1.3.19", "versionCode": "13190"}
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if "=" in line and not line.startswith("#"):
                            k, v = line.split("=", 1)
                            props[k.strip()] = v.strip()
                break
            except Exception:
                pass
    return props

def check_module_update():
    local_props = get_module_local_prop()
    cur_ver = local_props.get("version", "v1.3.19")
    try:
        cur_code = int(local_props.get("versionCode", "13190"))
    except ValueError:
        cur_code = 13190

    res = {
        "current_version": cur_ver,
        "current_code": cur_code,
        "latest_version": cur_ver,
        "latest_code": cur_code,
        "has_update": False,
        "zip_url": "",
        "changelog": "",
        "notes": ""
    }

    try:
        req = urllib.request.Request(UPDATE_METADATA_URL, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            latest_ver = data.get("version", cur_ver)
            try:
                latest_code = int(data.get("versionCode", cur_code))
            except (ValueError, TypeError):
                latest_code = cur_code
            res["latest_version"] = latest_ver
            res["latest_code"] = latest_code
            res["zip_url"] = data.get("zipUrl", "")
            res["changelog"] = data.get("changelog", "")
            res["notes"] = data.get("notes", "")

            if latest_code > cur_code or (latest_code == cur_code and latest_ver != cur_ver):
                res["has_update"] = True
    except Exception as e:
        print(f"Check module update error: {e}", file=sys.stderr)
        res["error"] = str(e)

    return res

def get_python_binary():
    py_candidates = [
        "/data/adb/modules/hyperdl/runtime/bin/python3",
        "/data/adb/modules_update/hyperdl/runtime/bin/python3",
        sys.executable,
        "/system/bin/python3",
        "/system/xbin/python3",
        "/data/adb/modules/python/bin/python3",
        "/data/adb/ap/bin/python3",
        "/data/adb/ksu/bin/python3",
        "python3"
    ]
    for p in py_candidates:
        if p and os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return "python3"

def _resolve_runtime_dir():
    for d in (
        "/data/adb/modules/hyperdl/runtime",
        "/data/adb/modules_update/hyperdl/runtime"
    ):
        if os.path.isdir(d):
            return d
    return None

def get_runtime_env():
    env = dict(os.environ)
    rd = _resolve_runtime_dir()
    if rd:
        env["PATH"] = f"{rd}/bin:/data/adb/modules/hyperdl/bin:/data/adb/modules/hyperdl/system/bin:" + env.get("PATH", "/system/bin")
        env["LD_LIBRARY_PATH"] = f"{rd}/lib"
        env["PYTHONHOME"] = rd
        env["PYTHONPATH"] = f"{rd}/lib/python314.zip:{rd}/lib/python3.14/lib-dynload:{rd}/lib/python3.14"
        env["SSL_CERT_FILE"] = f"{rd}/lib/cacert.pem"
    return env

def get_ffmpeg_env():
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = "/system/lib64:/system/lib"
    rd = _resolve_runtime_dir()
    if not rd:
        rd = "/data/adb/modules/hyperdl/runtime"
    env["PATH"] = f"{rd}/bin:/data/adb/modules/hyperdl/bin:/data/adb/modules/hyperdl/system/bin:/system/bin:/system/xbin:" + env.get("PATH", "")
    return env

def get_ffmpeg_binary():
    candidates = [
        "/data/adb/modules/hyperdl/runtime/bin/ffmpeg",
        "/data/adb/modules_update/hyperdl/runtime/bin/ffmpeg",
        "/data/adb/modules/hyperdl/bin/ffmpeg",
        "/data/adb/modules/hyperdl/system/bin/ffmpeg",
        "/system/bin/ffmpeg",
        "/system/xbin/ffmpeg",
    ]
    env = get_ffmpeg_env()
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            try:
                r = subprocess.run([c, "-version"], capture_output=True, timeout=2, env=env)
                if r.returncode == 0:
                    return c
            except Exception:
                pass
    w = shutil.which("ffmpeg")
    if w:
        try:
            r = subprocess.run([w, "-version"], capture_output=True, timeout=2, env=env)
            if r.returncode == 0:
                return w
        except Exception:
            pass
    return None

def resolve_bluesky(url, fmt="video"):
    update_status("resolving", title="Resolving Bluesky media...")
    m = re.search(r'bsky\.app/profile/([^/?#]+)/post/([^/?#]+)', url)
    if not m:
        return {"direct_ytdlp": True, "url": url, "fmt": fmt, "platform": "Bluesky"}
    actor, rkey = m.group(1), m.group(2)
    api_url = f"https://public.api.bsky.app/xrpc/app.bsky.feed.getPostThread?uri=at://{actor}/app.bsky.feed.post/{rkey}&depth=0"
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        post = (data.get("thread") or {}).get("post") or {}
        author_info = post.get("author") or {}
        author = author_info.get("handle") or actor
        raw_text = ((post.get("record") or {}).get("text") or "").strip()
        clean_text = re.sub(r'[\r\n\t]+', ' ', raw_text).strip()
        title = clean_text[:60].strip() if clean_text else f"Bluesky post by {author}"
        title = title or f"Bluesky_{rkey}"

        embed = post.get("embed") or {}
        if embed.get("$type") == "app.bsky.embed.recordWithMedia#view":
            embed = embed.get("media") or {}

        embed_type = embed.get("$type", "")

        if "video" in embed_type or "playlist" in embed:
            playlist_url = embed.get("playlist")
            if playlist_url:
                return {
                    "url": playlist_url,
                    "title": title,
                    "id": rkey,
                    "ext": "mp4",
                    "is_m3u8": True,
                    "platform": "Bluesky",
                    "author": author,
                    "channel": author
                }

        images = embed.get("images") or []
        if images and fmt != "audio":
            if len(images) == 1:
                img0 = (images[0] or {})
                img_url = img0.get("fullsize") or img0.get("thumb")
                if img_url:
                    return {
                        "url": img_url,
                        "title": title,
                        "id": rkey,
                        "ext": "jpg",
                        "kind": "image",
                        "platform": "Bluesky",
                        "author": author,
                        "channel": author
                    }
            items = []
            for img in images:
                img = (img or {})
                i_url = img.get("fullsize") or img.get("thumb")
                if i_url:
                    items.append({"url": i_url, "ext": "jpg", "kind": "image"})
            return {
                "kind": "album",
                "items": items,
                "title": title,
                "id": rkey,
                "ext": "jpg",
                "platform": "Bluesky",
                "author": author,
                "channel": author
            }

    except Exception as e:
        print(f"Bluesky API note: {e}", file=sys.stderr)

    return {"direct_ytdlp": True, "url": url, "fmt": fmt, "is_yt": False, "title": f"Bluesky_{rkey}", "platform": "Bluesky"}

def resolve_threads(url, fmt="video"):
    update_status("resolving", title="Resolving Threads media...")
    m = re.search(r'threads\.(?:net|com)/(?:@[^/]+/post|t)/([A-Za-z0-9_-]+)', url)
    post_id = m.group(1) if m else hashlib.md5(url.encode()).hexdigest()[:8]
    try:
        hdrs = {
            "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }
        cookie_hdr = get_cookie_header("threads.net") or get_cookie_header("threads.com")
        if cookie_hdr:
            hdrs["Cookie"] = cookie_hdr
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=6) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        og_vid = re.search(r'property=["\']og:video(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']', html) or \
                 re.search(r'content=["\']([^"\']+)["\'][^>]+property=["\']og:video(?::secure_url)?["\']', html)
        if og_vid:
            vurl = pyhtml.unescape(og_vid.group(1)).replace("&amp;", "&")
            og_title = re.search(r'property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html)
            title = pyhtml.unescape(og_title.group(1)).strip() if og_title else f"Threads_{post_id}"
            m_auth = re.search(r'threads\.(?:net|com)/@([^/]+)', url)
            author = m_auth.group(1) if m_auth else None
            return {"url": vurl, "title": title, "ext": "mp4", "kind": "video", "id": post_id, "channel": author, "platform": "Threads"}
        if fmt not in ("audio", "video"):
            images = re.findall(r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html)
            if not images:
                images = re.findall(r'content=["\']([^"\']+)["\']\s+property=["\']og:image["\']', html)
            if images:
                images = [pyhtml.unescape(u).replace("&amp;", "&") for u in images]
                og_title = re.search(r'property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html)
                title = pyhtml.unescape(og_title.group(1)).strip() if og_title else f"Threads_{post_id}"
                m_auth = re.search(r'threads\.(?:net|com)/@([^/]+)', url)
                author = m_auth.group(1) if m_auth else None
                if len(images) == 1:
                    return {"url": images[0], "title": title, "ext": "jpg", "kind": "image", "id": post_id, "channel": author, "platform": "Threads"}
                return {"images": images, "title": title, "ext": "jpg", "kind": "album", "id": post_id, "channel": author, "platform": "Threads"}
    except Exception as e:
        print(f"Threads OG scrape note: {e}", file=sys.stderr)
    return {"direct_ytdlp": True, "url": url, "fmt": fmt, "is_yt": False, "title": f"Threads_{post_id}", "platform": "Threads"}

def resolve_streamable(url, fmt="video"):
    update_status("resolving", title="Resolving Streamable media...")
    m = re.search(r'streamable\.com/(?:e/)?([A-Za-z0-9]+)', url)
    if not m:
        return {"direct_ytdlp": True, "url": url, "fmt": fmt, "is_yt": False, "title": "Streamable Video"}
    vid_id = m.group(1)
    try:
        req = urllib.request.Request(f"https://api.streamable.com/videos/{vid_id}", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as resp:
            d = json.loads(resp.read().decode("utf-8"))
        title = d.get("title") or f"Streamable_{vid_id}"
        files = d.get("files") or {}
        for key in ("mp4", "mp4-mobile"):
            f = files.get(key) or {}
            if f.get("url"):
                mp4_url = f["url"]
                if not mp4_url.startswith("http"):
                    mp4_url = "https:" + mp4_url
                return {"url": mp4_url, "title": title, "ext": "mp4", "kind": "video", "id": vid_id, "platform": "Streamable"}
    except Exception as e:
        print(f"Streamable API note: {e}", file=sys.stderr)
    return {"direct_ytdlp": True, "url": url, "fmt": fmt, "is_yt": False, "title": f"Streamable_{vid_id}", "platform": "Streamable"}

def resolve_bilibili(url, fmt="video"):
    update_status("resolving", title="Resolving Bilibili media...")
    clean_url = url
    if "b23.tv" in url.lower():
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
            opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
            with opener.open(req, timeout=4) as r:
                clean_url = r.geturl()
        except urllib.error.HTTPError as e:
            loc = e.headers.get("Location") or e.headers.get("location")
            if loc:
                clean_url = loc if loc.startswith("http") else urllib.parse.urljoin(url, loc)
        except Exception:
            pass

    m_bv = re.search(r'/(BV[A-Za-z0-9]+)', clean_url)
    m_av = re.search(r'/av(\d+)', clean_url)
    if not m_bv and not m_av:
        return {"direct_ytdlp": True, "url": clean_url, "fmt": fmt, "is_yt": False, "title": "Bilibili Video", "platform": "Bilibili"}

    bvid = m_bv.group(1) if m_bv else None
    aid = m_av.group(1) if m_av else None
    title = f"Bilibili_{bvid or aid}"
    hdrs = {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.bilibili.com/",
        "Origin": "https://www.bilibili.com",
        "Accept": "application/json, text/plain, */*",
    }
    cookie_hdr = get_cookie_header("bilibili.com")
    if cookie_hdr:
        hdrs["Cookie"] = cookie_hdr

    try:
        params = f"bvid={bvid}" if bvid else f"aid={aid}"
        req = urllib.request.Request(f"https://api.bilibili.com/x/web-interface/view?{params}", headers=hdrs)
        with urllib.request.urlopen(req, timeout=4) as resp:
            d = json.loads(resp.read().decode("utf-8"))
        info = (d.get("data") or {})
        title = info.get("title") or (f"Bilibili_{bvid or aid}")
        cid = info.get("cid")
        vid_bvid = info.get("bvid") or bvid
        vid_aid = info.get("aid") or aid
        channel = (info.get("owner") or {}).get("name") or ""

        if cid and (vid_bvid or vid_aid):
            q_param = "qn=80&fnval=0&fnver=0&fourk=1"
            if vid_bvid:
                play_params = f"bvid={vid_bvid}&cid={cid}&{q_param}"
            else:
                play_params = f"avid={vid_aid}&cid={cid}&{q_param}"
            req2 = urllib.request.Request(f"https://api.bilibili.com/x/player/playurl?{play_params}", headers=hdrs)
            with urllib.request.urlopen(req2, timeout=4) as resp2:
                pd = json.loads(resp2.read().decode("utf-8"))
            durl = ((pd.get("data") or {}).get("durl") or [])
            if durl:
                best = max(durl, key=lambda x: (x or {}).get("size", 0))
                best = (best or {})
                media_url = best.get("url") or ((best.get("backup_url") or [None])[0])
                if media_url:
                    return {
                        "url": media_url,
                        "title": title,
                        "ext": "mp4",
                        "kind": "video",
                        "id": vid_bvid or str(vid_aid),
                        "channel": channel,
                        "platform": "Bilibili",
                        "headers": hdrs
                    }
    except Exception as e:
        print(f"Bilibili API note: {e}", file=sys.stderr)

    return {"direct_ytdlp": True, "url": clean_url, "fmt": fmt, "is_yt": False, "title": title, "platform": "Bilibili"}

def resolve_ytdlp(url, fmt="video", is_yt=False):
    return {
        "direct_ytdlp": True,
        "url": url,
        "fmt": fmt,
        "is_yt": is_yt,
        "title": "Media"
    }

def resolve_youtube_post(url):
    m = re.search(r'youtube\.com/post/([A-Za-z0-9_-]+)', url)
    post_id = m.group(1) if m else hashlib.md5(url.encode()).hexdigest()[:8]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        m_data = re.search(r'var ytInitialData = ({.*?});</script>', html)
        if not m_data:
            return None
        data = json.loads(m_data.group(1))
        s = json.dumps(data)

        raw_thumbs = re.findall(r'\"backstageImageRenderer\":\s*\{\"image\":\s*\{\"thumbnails\":\s*(\[.*?\])', s)
        images = []
        for rt in raw_thumbs:
            try:
                th_list = json.loads(rt)
                if th_list:
                    images.append(th_list[-1]["url"])
            except Exception:
                pass

        title = "YouTube Post"
        content_m = re.search(r'\"contentText\":\s*\{\"runs\":\s*(\[.*?\])\}', s)
        if content_m:
            try:
                runs = json.loads(content_m.group(1))
                t = "".join(r.get("text", "") for r in runs).strip()
                if t:
                    title = t
            except Exception:
                pass

        author = "YouTube"
        author_m = re.search(r'\"authorText\":\s*\{.*?\"runs\":\s*\[\{\"text\":\s*\"(.*?)\"', s) or re.search(r'\"authorText\":\s*\{\"simpleText\":\s*\"(.*?)\"', s)
        if author_m:
            author = author_m.group(1)

        if images:
            if len(images) == 1:
                return {"url": images[0], "title": title, "ext": "jpg", "kind": "image", "id": post_id, "platform": "YouTube", "channel": author}
            return {"images": images, "title": title, "ext": "jpg", "kind": "album", "id": post_id, "platform": "YouTube", "channel": author}
    except Exception as e:
        print(f"YouTube community post note: {e}", file=sys.stderr)
    return None

def resolve_youtube(url, fmt="video"):
    if "/post/" in url.lower():
        post_res = resolve_youtube_post(url)
        if post_res:
            return post_res
    return {
        "direct_ytdlp": True,
        "url": url,
        "fmt": fmt,
        "is_yt": True,
        "title": "YouTube Media"
    }

def download_with_ytdlp_direct(url, outdir, fmt="video", format_id=None, height=None, is_playlist=False, audio_format=None):
    ok, err_msg = check_storage_space(outdir, 100 * 1024 * 1024)
    if not ok:
        update_status("error", error=err_msg)
        return None

    ytdlp_bin = get_or_download_ytdlp()
    py_bin = get_python_binary()

    cookie_arg = ["--cookies", COOKIES_PATH] if os.path.exists(COOKIES_PATH) else []
    ffmpeg_bin = get_ffmpeg_binary()
    ffmpeg_arg = ["--ffmpeg-location", ffmpeg_bin] if ffmpeg_bin else []

    node_bin = None
    for nc in ["/system/bin/node", "/system/xbin/node"]:
        if os.path.isfile(nc) and os.access(nc, os.X_OK):
            node_bin = nc
            break
    if not node_bin:
        node_bin = shutil.which("node")
    js_arg = ["--js-runtimes", f"node:{node_bin}"] if node_bin else []

    target_audio_fmt = audio_format
    if not target_audio_fmt:
        audio_conf = "/data/adb/hyperdl/audio_format.conf"
        if os.path.exists(audio_conf):
            try:
                with open(audio_conf, "r") as af:
                    c = af.read().strip().lower()
                    if c in ("mp3", "flac", "m4a", "opus"):
                        target_audio_fmt = c
            except Exception:
                pass
    if not target_audio_fmt:
        target_audio_fmt = "mp3"

    if fmt == "audio":
        if target_audio_fmt == "flac":
            format_arg = ["-f", "ba/bestaudio/best", "-x", "--audio-format", "flac", "--audio-quality", "0"]
        else:
            format_arg = ["-f", "ba/bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "0"]
    elif fmt in ("album", "photo", "image"):
        format_arg = []
    elif format_id and not height:
        format_arg = ["-f", format_id]
    elif height:
        h = int(height)
        if ffmpeg_bin:
            format_arg = [
                "-f",
                f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={h}]+bestaudio/bestvideo[width<={h}]+bestaudio/best[height<={h}]/best[width<={h}]/best",
                "--merge-output-format", "mp4"
            ]
        else:
            format_arg = ["-f", f"best[height<={h}][ext=mp4]/best[height<={h}]/best[width<={h}]/best"]
    else:
        if ffmpeg_bin:
            format_arg = ["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best", "--merge-output-format", "mp4"]
        else:
            format_arg = ["-f", "best[ext=mp4]/best"]

    os.makedirs(outdir, exist_ok=True)
    is_vault = False
    vault_flag = "/data/adb/hyperdl/vault.enabled"
    vault_conf = "/data/adb/hyperdl/vault_domains.conf"
    if os.path.exists(vault_flag) and os.path.exists(vault_conf):
        try:
            with open(vault_conf, "r") as vf:
                v_domains = [l.strip().lower() for l in vf if l.strip()]
                low_u = (url or "").lower()
                if any(vd in low_u for vd in v_domains):
                    is_vault = True
        except Exception:
            pass

    if is_vault:
        vault_root = os.path.join(outdir, ".vault")
        target_dir = os.path.join(vault_root, "Stream")
        os.makedirs(target_dir, exist_ok=True)
        nm = os.path.join(vault_root, ".nomedia")
        if not os.path.exists(nm):
            try:
                with open(nm, "w") as f:
                    pass
                os.chmod(nm, 0o666)
            except Exception:
                pass
        out_tpl = os.path.join(target_dir, "%(title).60s_%(id)s.%(ext)s")
    else:
        out_tpl = os.path.join(
            outdir,
            "%(extractor_key,extractor|Media)s/%(channel,uploader,uploader_id|Media)s/%(playlist_index)s_%(title).60s_%(id)s.%(ext)s"
        ) if is_playlist else os.path.join(
            outdir,
            "%(extractor_key,extractor|Media)s/%(channel,uploader,uploader_id|Media)s/%(title).60s_%(id)s.%(ext)s"
        )

    extra_dl_args = []
    low_u = (url or "").lower()
    if "youtube.com" in low_u or "youtu.be" in low_u:
        extra_dl_args = ["--continue", "--no-part"]
    elif not (".m3u8" in url or "manifest" in url or "/hls/" in url):
        extra_dl_args = ["--continue", "--concurrent-fragments", "4", "--http-chunk-size", "10M"]
    else:
        extra_dl_args = ["--no-part"]

    playlist_arg = ["--yes-playlist"] if is_playlist else ["--no-playlist"]

    is_yt = ("youtube.com" in low_u or "youtu.be" in low_u)
    if is_yt:
        cookie_attempts = [[], cookie_arg] if cookie_arg else [[]]
    else:
        cookie_attempts = [cookie_arg, []] if cookie_arg else [[]]
    for attempt_idx, active_cookies in enumerate(cookie_attempts):
        cmd = [
            py_bin,
            ytdlp_bin,
            "--no-warnings",
            "--no-check-certificates",
        ] + playlist_arg + [
            "--no-mtime",
            "--buffer-size", "256k",
            "--extractor-retries", "3",
            "--socket-timeout", "15",
            "--newline",
            "--progress-template", "download:%(progress._percent_str)s|%(progress._downloaded_bytes_str)s|%(progress._total_bytes_str)s|%(progress._total_bytes_estimate_str)s|%(progress._speed_str)s|%(info.title)s|%(progress._eta_str)s",
            "-o", out_tpl,
        ] + extra_dl_args + js_arg + ffmpeg_arg + format_arg + active_cookies + [url]

        env = get_runtime_env()
        t_proc_start = time.time()
        init_title = "Connecting to YouTube..." if is_yt else "Connecting to media stream..."
        update_status("resolving", percent=0, title=init_title)
        proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        stderr_lines = []
        def _drain_stderr():
            try:
                for eline in proc.stderr:
                    stderr_lines.append(eline)
            except Exception:
                pass

        t_err = threading.Thread(target=_drain_stderr, daemon=True)
        t_err.start()

        title = "Media"
        downloaded_file = None
        for line in proc.stdout:
            line = line.strip()
            if "|" in line:
                clean_l = line[9:] if line.startswith("download:") else line
                parts = clean_l.split("|")
                pct_str = parts[0].replace("%", "").strip()
                try:
                    pct = int(float(pct_str))
                except Exception:
                    pct = 0
                dl_str = parts[1].strip() if len(parts) > 1 else ""
                tot_str = parts[2].strip() if len(parts) > 2 else ""
                est_str = parts[3].strip() if len(parts) > 3 else ""
                spd_str = parts[4].strip() if len(parts) > 4 else ""
                if len(parts) > 5 and parts[5].strip() and title == "Media":
                    title = parts[5].strip()
                eta_str = parts[6].strip() if len(parts) > 6 else ""
                if eta_str in ("N/A", "NA", "none", "None", "null", "Unknown"):
                    eta_str = ""

                if tot_str in ("N/A", "NA", "none", "None", "null", ""):
                    if est_str and est_str not in ("N/A", "NA", "none", "None", "null"):
                        tot_str = est_str if est_str.startswith("~") else f"~{est_str.strip()}"
                    else:
                        tot_str = ""

                if dl_str in ("N/A", "NA", "none", "None", "null"):
                    dl_str = ""
                if spd_str in ("N/A", "NA", "none", "None", "null"):
                    spd_str = ""

                update_status("downloading", percent=pct, downloaded=dl_str, total=tot_str, speed=spd_str, title=title, eta=eta_str)
            elif "[download] Destination:" in line:
                downloaded_file = line.replace("[download] Destination:", "").strip()
                title = os.path.splitext(os.path.basename(downloaded_file))[0]
            elif "[Merger] Merging formats into" in line:
                downloaded_file = line.replace("[Merger] Merging formats into", "").strip().strip('"')
                title = os.path.splitext(os.path.basename(downloaded_file))[0]
                update_status("downloading", percent=99, speed="", title=f"{title} (Merging formats...)")
            elif "[ExtractAudio] Destination:" in line:
                downloaded_file = line.replace("[ExtractAudio] Destination:", "").strip().strip('"')
                title = os.path.splitext(os.path.basename(downloaded_file))[0]
                update_status("downloading", percent=99, speed="", title=f"{title} (Extracting audio...)")
            elif "[download]" in line and "has already been downloaded" in line:
                m_dl = re.search(r'\[download\]\s+(.*?)\s+has already been downloaded', line)
                if m_dl:
                    downloaded_file = m_dl.group(1).strip().strip('"')
                    title = os.path.splitext(os.path.basename(downloaded_file))[0]

        proc.wait()
        t_err.join(timeout=1.5)
        if proc.returncode != 0:
            err = "".join(stderr_lines).strip()
            if active_cookies and attempt_idx == 0:
                print(f"yt-dlp failed with cookies, retrying without cookies: {err[-120:]}", file=sys.stderr)
                update_status("downloading", percent=0, title="Retrying download without cookies...")
                continue
            raise RuntimeError(f"yt-dlp failed: {err[-200:]}")
        break

    if not downloaded_file or not os.path.exists(downloaded_file):
        candidates = []
        for r, _, fnames in os.walk(outdir):
            for fn in fnames:
                if not fn.startswith('.') and not any(fn.endswith(bad) for bad in ('.part', '.ytdl', '.temp', '.tmp', '.raw')):
                    full_p = os.path.join(r, fn)
                    try:
                        if os.path.getmtime(full_p) >= t_proc_start - 10:
                            candidates.append(full_p)
                    except Exception:
                        pass
        if candidates:
            candidates.sort(key=os.path.getmtime, reverse=True)
            downloaded_file = candidates[0]
            title = os.path.splitext(os.path.basename(downloaded_file))[0]

    if downloaded_file and os.path.exists(downloaded_file):
        scan_media_file(downloaded_file)
        save_source_sidecar(downloaded_file, url)
        update_status("completed", percent=100, title=title, file_path=downloaded_file)
        return downloaded_file

    raise RuntimeError("Media file not found after download completed")

def _write_probe_result(data):
    try:
        os.makedirs(os.path.dirname(PROBE_FILE), exist_ok=True)
        tmp_file = f"{PROBE_FILE}.tmp.{os.getpid()}"
        with open(tmp_file, "w") as f:
            json.dump(data, f)
        os.replace(tmp_file, PROBE_FILE)
        try:
            os.chmod(PROBE_FILE, 0o666)
        except Exception:
            pass
    except Exception:
        pass
    finally:
        try:
            if os.path.exists(PROBE_PID):
                os.unlink(PROBE_PID)
        except Exception:
            pass

def probe_resolutions(url):
    try:
        os.nice(19)
    except Exception:
        pass

    try:
        with open(PROBE_PID, "w") as f:
            f.write(str(os.getpid()))
        os.chmod(PROBE_PID, 0o666)
    except Exception:
        pass

    url = clean_media_url(url)

    ytdlp_bin = get_or_download_ytdlp()
    py_bin = get_python_binary()

    node_bin = None
    for nc in ["/system/bin/node", "/system/xbin/node"]:
        if os.path.isfile(nc) and os.access(nc, os.X_OK):
            node_bin = nc
            break
    if not node_bin:
        node_bin = shutil.which("node")
    js_arg = ["--js-runtimes", f"node:{node_bin}"] if node_bin else []

    cmd_base = [
        py_bin, ytdlp_bin,
        "-J", "--no-warnings", "--no-check-certificates",
        "--no-playlist", "--skip-download", "--socket-timeout", "10",
        "--extractor-retries", "1",
    ] + js_arg

    env = get_runtime_env()

    # Fast probe without cookies first to avoid expired Google session blocks
    res = subprocess.run(cmd_base + [url], env=env, capture_output=True, text=True, timeout=20)
    if (res.returncode != 0 or not res.stdout.strip()) and os.path.exists(COOKIES_PATH):
        res = subprocess.run(cmd_base + ["--cookies", COOKIES_PATH, url], env=env, capture_output=True, text=True, timeout=20)

    if res.returncode != 0 or not res.stdout.strip():
        _write_probe_result({"status": "ready", "url": url, "resolutions": []})
        return []

    try:
        data = json.loads(res.stdout)
    except Exception:
        _write_probe_result({"status": "ready", "url": url, "resolutions": []})
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
        w = f.get("width")
        eff_h = min(h, w) if (h and w and w < h) else h
        if not eff_h or eff_h < 144:
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

        if eff_h not in by_height or vsize > by_height[eff_h]["vsize"]:
            by_height[eff_h] = {"height": eff_h, "vsize": vsize, "fps": fps}

    if not by_height:
        _write_probe_result({"status": "ready", "url": url, "resolutions": []})
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
        tot = entry["vsize"] + best_audio_size if entry["vsize"] > 0 else 0
        lbl = labels.get(h, f"{h}p")
        badge = "4K" if h >= 2160 else ("2K" if h >= 1440 else ("FHD" if h >= 1080 else ("HD" if h >= 720 else "SD")))
        results.append({
            "height": h,
            "format_id": str(h),
            "label": lbl,
            "badge": badge,
            "ext": "mp4",
            "filesize": tot,
            "fps": entry["fps"],
            "isRealStream": True
        })

    _write_probe_result({"status": "ready", "url": url, "resolutions": results})
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
    dl_parser.add_argument("--audio-format", default=None, choices=["mp3", "flac", "m4a", "opus"], help="Target audio format")

    probe_parser = subparsers.add_parser("probe")
    probe_parser.add_argument("url", help="Media link to probe")

    subparsers.add_parser("check_ytdlp")
    subparsers.add_parser("update_ytdlp")
    subparsers.add_parser("check_update")

    args, _ = parser.parse_known_args()

    if args.action == "probe":
        try:
            res = probe_resolutions(args.url)
            print(json.dumps({"status": "ready", "url": args.url, "resolutions": res}), flush=True)
        except Exception as e:
            _write_probe_result({"status": "error", "error": humanize_error(e), "resolutions": []})
            print(json.dumps({"status": "error", "error": humanize_error(e), "resolutions": []}), flush=True)
            sys.exit(1)
        return

    if args.action == "check_ytdlp":
        try:
            res = check_ytdlp_version_api()
            print(json.dumps(res), flush=True)
        except Exception as e:
            print(json.dumps({"error": humanize_error(e)}), flush=True)
            sys.exit(1)
        return

    if args.action == "update_ytdlp":
        try:
            res = perform_ytdlp_update()
            print(json.dumps(res), flush=True)
        except Exception as e:
            print(json.dumps({"error": humanize_error(e)}), flush=True)
            sys.exit(1)
        return

    if args.action == "check_update":
        try:
            res = check_module_update()
            print(json.dumps(res), flush=True)
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

    global CURRENT_URL, CURRENT_FMT, CURRENT_FORMAT_ID, CURRENT_HEIGHT
    url = clean_media_url(args.url.strip())
    fmt = args.format
    outdir = get_effective_outdir(args.outdir)
    height = args.height if hasattr(args, 'height') else None
    format_id = args.format_id if hasattr(args, 'format_id') else None

    CURRENT_URL = url
    CURRENT_FMT = fmt
    CURRENT_FORMAT_ID = format_id or ""
    CURRENT_HEIGHT = height or ""

    target_audio_fmt = getattr(args, 'audio_format', None)
    if not target_audio_fmt:
        audio_conf = "/data/adb/hyperdl/audio_format.conf"
        if os.path.exists(audio_conf):
            try:
                with open(audio_conf, "r") as af:
                    c = af.read().strip().lower()
                    if c in ("mp3", "flac", "m4a", "opus"):
                        target_audio_fmt = c
            except Exception:
                pass
    if not target_audio_fmt:
        target_audio_fmt = "mp3"

    try:
        ok, err_msg = check_storage_space(outdir, 100 * 1024 * 1024)
        if not ok:
            update_status("error", error=err_msg)
            return

        update_status("resolving", title="Connecting to platform...")
        low_url = url.lower()

        if format_id or height:
            download_with_ytdlp_direct(url, outdir, fmt=fmt, format_id=format_id, height=height, audio_format=target_audio_fmt)
            return

        if "tiktok.com" in low_url or "douyin.com" in low_url:
            info = resolve_tiktok(url, fmt)
        elif "twitter.com" in low_url or "x.com" in low_url:
            info = resolve_twitter(url, fmt)
        elif "instagram.com" in low_url or "instagr.am" in low_url:
            info = resolve_instagram(url, fmt)
        elif "facebook.com" in low_url or "fb.watch" in low_url or "fb.com" in low_url:
            info = resolve_facebook(url, fmt)
        elif "pinterest.com" in low_url or "pin.it" in low_url:
            info = resolve_pinterest(url, fmt)
        elif "reddit.com" in low_url or "redd.it" in low_url:
            info = resolve_reddit(url, fmt)
        elif "youtube.com" in low_url or "youtu.be" in low_url:
            info = resolve_youtube(url, fmt)
        elif "threads.net" in low_url or "threads.com" in low_url:
            info = resolve_threads(url, fmt)
        elif "streamable.com" in low_url:
            info = resolve_streamable(url, fmt)
        elif "bilibili.com" in low_url or "b23.tv" in low_url:
            info = resolve_bilibili(url, fmt)
        elif "bsky.app" in low_url:
            info = resolve_bluesky(url, fmt)
        else:
            info = resolve_ytdlp(url, fmt, is_yt=False)

        if info.get("direct_ytdlp"):
            download_with_ytdlp_direct(info["url"], outdir, fmt=info.get("fmt", fmt), is_playlist=info.get("is_playlist", False))
            return

        title = sanitize_filename(info.get("title", "Media"))
        ext = info.get("ext") or ("jpg" if info.get("kind") == "image" else "mp4")
        media_id = info.get("id") or hashlib.md5(url.encode()).hexdigest()[:8]
        target_dir = get_target_directory(outdir, info, url)
        base_title = re.sub(rf'[_ -]*{re.escape(media_id)}.*$', '', title).strip() or title

        if info.get("kind") == "album" and (info.get("images") or info.get("items")):
            raw_items = info.get("items") or info.get("images") or []
            total = len(raw_items)
            for idx, it in enumerate(raw_items):
                if isinstance(it, dict):
                    item_url = it.get("url")
                    item_ext = it.get("ext") or ("mp4" if it.get("kind") == "video" else ("jpg" if it.get("kind") == "image" else ext))
                else:
                    item_url = it
                    item_ext = "mp4" if ".mp4" in str(item_url).lower() else ext

                if not item_url:
                    continue

                if item_ext == "mp4" and any(e in str(item_url).lower() for e in (".jpg", ".jpeg", ".png", ".webp")):
                    for e in (".jpg", ".jpeg", ".png", ".webp"):
                        if e in str(item_url).lower():
                            item_ext = e.lstrip(".")
                            break

                item_path = os.path.join(target_dir, f"{base_title}_{media_id}_{idx+1}.{item_ext}")
                update_status("downloading", percent=int((idx+1)/total*100), title=f"{title} ({idx+1}/{total})")
                hdrs = dict(info.get("headers") or {})
                if "tikwm.com" in str(item_url):
                    hdrs["Referer"] = "https://www.tikwm.com/"

                if isinstance(it, dict) and it.get("audio_url"):
                    it_cand = dict(it)
                    if "headers" not in it_cand and hdrs:
                        it_cand["headers"] = hdrs
                    download_media_candidates(it_cand, item_path, title=f"{base_title}_{media_id}_{idx+1}", emit_complete=False)
                else:
                    download_file(item_url, item_path, title=f"{base_title}_{media_id}_{idx+1}", headers=hdrs, emit_error=True, emit_complete=False)

                scan_media_file(item_path)
                save_source_sidecar(item_path, url)
            update_status("completed", percent=100, title=title, file_path=target_dir)
        else:
            if fmt == "audio":
                if info.get("kind") == "image" or ext in ("jpg", "jpeg", "png", "webp"):
                    raise RuntimeError("Cannot extract audio: this post only contains photos/images.")
                ffmpeg_bin = get_ffmpeg_binary()
                if ffmpeg_bin:
                    tmp_raw = os.path.join(target_dir, f".tmp_{base_title}_{media_id}.raw")
                    download_media_candidates(info, tmp_raw, title=title, emit_complete=False)
                    if target_audio_fmt == "flac":
                        out_path = os.path.join(target_dir, f"{base_title}_{media_id}.flac")
                        update_status("downloading", percent=95, title="Encoding audio to FLAC HD...")
                        res = subprocess.run([ffmpeg_bin, "-y", "-i", tmp_raw, "-c:a", "flac", out_path], env=get_ffmpeg_env(), capture_output=True)
                    else:
                        out_path = os.path.join(target_dir, f"{base_title}_{media_id}.mp3")
                        update_status("downloading", percent=95, title="Encoding audio to MP3 (320 kbps)...")
                        res = subprocess.run([ffmpeg_bin, "-y", "-i", tmp_raw, "-c:a", "libmp3lame", "-b:a", "320k", out_path], env=get_ffmpeg_env(), capture_output=True)
                    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
                        fallback_ext = ext if ext in ["mp3", "m4a", "wav", "aac"] else "mp3"
                        out_path = os.path.join(target_dir, f"{base_title}_{media_id}.{fallback_ext}")
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
                    save_source_sidecar(out_path, url)
                    update_status("completed", percent=100, title=title, file_path=out_path)
                    return
            if info.get("kind") == "image" and ext == "mp4":
                ext = "jpg"
            if ext == "mp4" and any(e in str(info.get("url", "")).lower() for e in (".jpg", ".jpeg", ".png", ".webp")):
                for e in (".jpg", ".jpeg", ".png", ".webp"):
                    if e in str(info.get("url", "")).lower():
                        ext = e.lstrip(".")
                        break
            filename = f"{base_title}_{media_id}.{ext}"
            out_path = os.path.join(target_dir, filename)
            download_media_candidates(info, out_path, title=title)

    except Exception as e:
        print(f"Download Error: {e}", file=sys.stderr)
        update_status("error", error=str(e))
        sys.exit(1)
    finally:
        try:
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
        except Exception:
            pass

if __name__ == "__main__":
    main()
