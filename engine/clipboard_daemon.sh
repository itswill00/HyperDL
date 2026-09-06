#!/bin/sh
# HyperDL Background Clipboard Listener Daemon

MODDIR="$(cd "$(dirname "$0")/.." && pwd)"
ENGINE_PY="$MODDIR/engine/downloader.py"
PID_FILE="/data/local/tmp/hyperdl_clip.pid"
LAST_CLIP_FILE="/data/local/tmp/hyperdl_last_clip.txt"

case "$1" in
  start)
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
      exit 0
    fi
    
    (
      while true; do
        CLIP="$(cmd clipboard get 2>/dev/null)"
        
        if [ -n "$CLIP" ]; then
          case "$CLIP" in
            *tiktok.com*|*instagram.com*|*twitter.com*|*x.com*|*youtu.be*|*youtube.com*)
              LAST_CLIP="$(cat "$LAST_CLIP_FILE" 2>/dev/null)"
              if [ "$CLIP" != "$LAST_CLIP" ]; then
                echo "$CLIP" > "$LAST_CLIP_FILE"
                cmd notification post -S bigtext -t "HyperDL Auto" "Media terdeteksi" "Mengunduh dari clipboard..." >/dev/null 2>&1
                python3 "$ENGINE_PY" "$CLIP" --format video >/dev/null 2>&1
              fi
              ;;
          esac
        fi
        sleep 3
      done
    ) &
    echo $! > "$PID_FILE"
    ;;

  stop)
    if [ -f "$PID_FILE" ]; then
      kill -9 $(cat "$PID_FILE") 2>/dev/null
      rm -f "$PID_FILE"
    fi
    ;;
esac
