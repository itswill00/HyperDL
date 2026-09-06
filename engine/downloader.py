#!/usr/bin/env python3
"""
HyperDL Downloader Engine
Minimalist media downloader for TikTok, Instagram, X, and YouTube.
"""

import os
import sys
import re
import json
import time
import argparse
import urllib.request
import urllib.parse
import urllib.error

STATUS_FILE = "/data/local/tmp/hyperdl_status.json"
DEFAULT_OUTDIR = "/storage/emulated/0/Download/HyperDL"

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

def download_file(url, out_path, title="Media"):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
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
            send_android_notification("Download Complete", f"{title} saved to Downloads/HyperDL")
            return out_path
    except Exception as e:
        update_status("error", error=str(e), title=title)
        raise

def resolve_tiktok(url, fmt="video"):
    update_status("resolving", title="Connecting to TikTok...")
    req = urllib.request.Request(
        "https://www.tikwm.com/api/",
        data=urllib.parse.urlencode({"url": url}).encode("utf-8"),
        headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    
    if res.get("code") != 0 or not res.get("data"):
        raise RuntimeError(res.get("msg") or "Unable to retrieve TikTok video")
    
    data = res["data"]
    title = data.get("title") or "TikTok Video"
    
    if fmt == "audio":
        audio_url = data.get("music") or (data.get("music_info") or {}).get("play")
        return {"url": audio_url, "title": title, "ext": "mp3", "kind": "audio"}
    elif fmt == "album" and data.get("images"):
        return {"images": data.get("images"), "title": title, "ext": "jpg", "kind": "album"}
    else:
        video_url = data.get("play") or data.get("hdplay") or data.get("wmplay")
        return {"url": video_url, "title": title, "ext": "mp4", "kind": "video"}

def resolve_twitter(url):
    update_status("resolving", title="Connecting to X...")
    status_id_match = re.search(r'status/(\d+)', url)
    if not status_id_match:
        raise RuntimeError("Invalid link format")
    status_id = status_id_match.group(1)
    
    req = urllib.request.Request(f"https://api.vxtwitter.com/Twitter/status/{status_id}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    
    title = data.get("text") or f"Post {status_id}"
    video_url = data.get("video_url")
    if video_url:
        return {"url": video_url, "title": title, "ext": "mp4", "kind": "video"}
    elif data.get("mediaURLs"):
        return {"images": data.get("mediaURLs"), "title": title, "ext": "jpg", "kind": "album"}
    else:
        raise RuntimeError("No media found in this post")

def resolve_instagram(url):
    update_status("resolving", title="Connecting to Instagram...")
    shortcode_match = re.search(r'/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)', url)
    if not shortcode_match:
        raise RuntimeError("Invalid Instagram link")
    shortcode = shortcode_match.group(1)
    
    req = urllib.request.Request(
        "https://co.wuk.sh/api/json",
        data=json.dumps({"url": url, "vQuality": "max"}).encode("utf-8"),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    
    stream_url = res.get("url")
    if not stream_url:
        raise RuntimeError("Unable to load Instagram media")
    return {"url": stream_url, "title": f"Instagram_{shortcode}", "ext": "mp4", "kind": "video"}

def resolve_youtube(url, fmt="video"):
    update_status("resolving", title="Connecting to YouTube...")
    req = urllib.request.Request(
        "https://co.wuk.sh/api/json",
        data=json.dumps({"url": url, "isAudioOnly": (fmt == "audio")}).encode("utf-8"),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    
    stream_url = res.get("url")
    if not stream_url:
        raise RuntimeError(res.get("text") or "Unable to load YouTube media")
    
    ext = "mp3" if fmt == "audio" else "mp4"
    return {"url": stream_url, "title": "YouTube Video", "ext": ext, "kind": fmt}

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
            try:
                info = resolve_tiktok(url, fmt)
            except Exception:
                info = resolve_youtube(url, fmt)

        title = sanitize_filename(info.get("title", "Media"))
        ext = info.get("ext", "mp4")
        
        if info.get("kind") == "album" and info.get("images"):
            images = info["images"]
            total = len(images)
            for idx, img_url in enumerate(images):
                img_path = os.path.join(outdir, f"{title}_{idx+1}.{ext}")
                update_status("downloading", percent=int((idx+1)/total*100), title=f"{title} ({idx+1}/{total})")
                download_file(img_url, img_path, title=f"{title}_{idx+1}")
            update_status("completed", percent=100, title=title, file_path=outdir)
        else:
            filename = f"{title}_{int(time.time())}.{ext}"
            out_path = os.path.join(outdir, filename)
            download_file(info["url"], out_path, title=title)

    except Exception as e:
        update_status("error", error=str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
