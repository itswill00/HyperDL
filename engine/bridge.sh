#!/bin/sh
# HyperDL WebUI Bridge Shell Interface

MODDIR="$(cd "$(dirname "$0")/.." && pwd)"
ENGINE_PY="$MODDIR/engine/downloader.py"
OUTDIR="/storage/emulated/0/Download/HyperDL"
STATUS_FILE="/data/local/tmp/hyperdl_status.json"
PID_FILE="/data/local/tmp/hyperdl.pid"
CLIP_PID_FILE="/data/local/tmp/hyperdl_clip.pid"

mkdir -p "$OUTDIR"

ACTION="$1"
shift

case "$ACTION" in
  status)
    if [ -f "$STATUS_FILE" ]; then
      cat "$STATUS_FILE"
    else
      echo '{"status":"idle","percent":0}'
    fi
    ;;

  download)
    URL="$1"
    FMT="${2:-video}"
    
    if [ -f "$PID_FILE" ]; then
      kill -9 $(cat "$PID_FILE") 2>/dev/null
    fi

    echo '{"status":"resolving","percent":0,"title":"Connecting to platform..."}' > "$STATUS_FILE"

    python3 "$ENGINE_PY" "$URL" --format "$FMT" --outdir "$OUTDIR" >/dev/null 2>&1 &
    echo $! > "$PID_FILE"
    echo '{"status":"started","pid":'$!'}'
    ;;

  list)
    echo "["
    FIRST=1
    for f in "$OUTDIR"/*; do
      if [ -f "$f" ]; then
        NAME="$(basename "$f")"
        SIZE="$(ls -lh "$f" 2>/dev/null | awk '{print $5}')"
        EXT="${NAME##*.}"
        
        if [ $FIRST -eq 0 ]; then
          echo ","
        fi
        FIRST=0
        
        printf '{"name":"%s","size":"%s","ext":"%s","path":"%s"}' "$NAME" "$SIZE" "$EXT" "$f"
      fi
    done
    echo "]"
    ;;

  delete)
    FILE_PATH="$1"
    if [ -f "$FILE_PATH" ]; then
      rm -f "$FILE_PATH"
      echo '{"success":true}'
    else
      echo '{"success":false,"error":"file not found"}'
    fi
    ;;

  toggle_autodl)
    STATE="$1"
    mkdir -p /data/adb/hyperdl 2>/dev/null
    if [ "$STATE" = "1" ] || [ "$STATE" = "on" ]; then
      touch /data/adb/hyperdl/autodl.enabled 2>/dev/null
      sh "$MODDIR/engine/clipboard_daemon.sh" start
      echo '{"autodl":true}'
    else
      rm -f /data/adb/hyperdl/autodl.enabled 2>/dev/null
      sh "$MODDIR/engine/clipboard_daemon.sh" stop
      echo '{"autodl":false}'
    fi
    ;;

  get_autodl)
    if [ -f "$CLIP_PID_FILE" ] && kill -0 $(cat "$CLIP_PID_FILE") 2>/dev/null; then
      echo '{"autodl":true}'
    else
      echo '{"autodl":false}'
    fi
    ;;

  info)
    STORAGE_FREE="$(df -h /data 2>/dev/null | tail -1 | awk '{print $4}')"
    echo '{"storage_free":"'"$STORAGE_FREE"'","outdir":"'"$OUTDIR"'"}'
    ;;

  *)
    echo '{"error":"unknown action"}'
    ;;
esac
