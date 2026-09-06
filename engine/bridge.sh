#!/bin/sh
# HyperDL WebUI Bridge Shell Interface

MODDIR="$(cd "$(dirname "$0")/.." && pwd)"
ENGINE_PY="$MODDIR/engine/downloader.py"
OUTDIR="/storage/emulated/0/Download/HyperDL"
CONF_DIR="/data/adb/hyperdl"
COOKIES_FILE="$CONF_DIR/cookies.txt"
STATUS_FILE="/data/local/tmp/hyperdl_status.json"
PID_FILE="/data/local/tmp/hyperdl.pid"
CLIP_PID_FILE="/data/local/tmp/hyperdl_clip.pid"
LOG_FILE="/data/local/tmp/hyperdl_engine.log"

mkdir -p "$OUTDIR" "$CONF_DIR" /data/local/tmp 2>/dev/null

# Multi-path Python 3 discovery
find_python() {
  if [ -x "/data/data/com.termux/files/usr/bin/python3" ]; then
    echo "/data/data/com.termux/files/usr/bin/python3"
  elif command -v python3 >/dev/null 2>&1; then
    command -v python3
  elif [ -x "/system/bin/python3" ]; then
    echo "/system/bin/python3"
  elif [ -x "/data/adb/modules/python/bin/python3" ]; then
    echo "/data/adb/modules/python/bin/python3"
  elif [ -x "/data/adb/ap/bin/python3" ]; then
    echo "/data/adb/ap/bin/python3"
  elif [ -x "/data/adb/ksu/bin/python3" ]; then
    echo "/data/adb/ksu/bin/python3"
  else
    echo ""
  fi
}

PYTHON_BIN="$(find_python)"

# Setup runtime environment if using Termux Python
if echo "$PYTHON_BIN" | grep -q "com.termux"; then
  export PATH="/data/data/com.termux/files/usr/bin:/system/bin:$PATH"
  export LD_LIBRARY_PATH="/data/data/com.termux/files/usr/lib:$LD_LIBRARY_PATH"
  export HOME="/data/data/com.termux/files/home"
  export PREFIX="/data/data/com.termux/files/usr"
fi

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

    if [ -z "$PYTHON_BIN" ]; then
      echo '{"status":"error","error":"Python 3 not found. Install via Termux (pkg install python) or flash a Python module."}' > "$STATUS_FILE"
      echo '{"error":"python_not_found"}'
      exit 1
    fi

    echo '{"status":"resolving","percent":0,"title":"Connecting to platform..."}' > "$STATUS_FILE"
    echo "--- New Download: $URL ($FMT) ---" >> "$LOG_FILE"

    "$PYTHON_BIN" "$ENGINE_PY" "$URL" --format "$FMT" --outdir "$OUTDIR" >> "$LOG_FILE" 2>&1 &
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

  get_cookies)
    if [ -f "$COOKIES_FILE" ]; then
      CONTENT_B64="$(base64 "$COOKIES_FILE" | tr -d '\n')"
      LINES="$(wc -l < "$COOKIES_FILE" | tr -d ' ')"
      echo '{"exists":true,"lines":'"$LINES"',"content_b64":"'"$CONTENT_B64"'"}'
    else
      echo '{"exists":false,"lines":0,"content_b64":""}'
    fi
    ;;

  save_cookies)
    DATA_B64="$1"
    if [ -n "$DATA_B64" ]; then
      echo "$DATA_B64" | base64 -d > "$COOKIES_FILE"
      chmod 600 "$COOKIES_FILE"
      LINES="$(wc -l < "$COOKIES_FILE" | tr -d ' ')"
      echo '{"success":true,"lines":'"$LINES"'}'
    else
      rm -f "$COOKIES_FILE"
      echo '{"success":true,"lines":0}'
    fi
    ;;

  clear_cookies)
    rm -f "$COOKIES_FILE"
    echo '{"success":true}'
    ;;

  get_logs)
    if [ -f "$LOG_FILE" ]; then
      tail -n 60 "$LOG_FILE"
    else
      echo "No log entries recorded yet."
    fi
    ;;

  toggle_autodl)
    STATE="$1"
    if [ "$STATE" = "1" ] || [ "$STATE" = "on" ]; then
      touch "$CONF_DIR/autodl.enabled" 2>/dev/null
      sh "$MODDIR/engine/clipboard_daemon.sh" start
      echo '{"autodl":true}'
    else
      rm -f "$CONF_DIR/autodl.enabled" 2>/dev/null
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
    HAS_COOKIES="false"
    [ -f "$COOKIES_FILE" ] && HAS_COOKIES="true"
    echo '{"storage_free":"'"$STORAGE_FREE"'","outdir":"'"$OUTDIR"'","python":"'"$PYTHON_BIN"'","has_cookies":'"$HAS_COOKIES"'}'
    ;;

  *)
    echo '{"error":"unknown action"}'
    ;;
esac
