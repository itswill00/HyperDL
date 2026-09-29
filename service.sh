#!/system/bin/sh
MODDIR="${0%/*}"

while [ "$(getprop sys.boot_completed)" != "1" ]; do
    sleep 3
done

MAX_WAIT=30
while [ $MAX_WAIT -gt 0 ]; do
    if [ -d /storage/emulated/0/Download ] || [ "$(getprop sys.user_0_ce_available)" = "true" ]; then
        break
    fi
    sleep 2
    MAX_WAIT=$((MAX_WAIT - 1))
done

# Work profiles and secondary users do not own /storage/emulated/0, so probe
# for a writable location before giving up.
if ! mkdir -p /storage/emulated/0/Download/HyperDL 2>/dev/null || [ ! -w /storage/emulated/0/Download/HyperDL ]; then
    mkdir -p /data/media/0/Download/HyperDL 2>/dev/null || true
    chmod 0777 /data/media/0/Download/HyperDL 2>/dev/null || true
else
    chmod 0777 /storage/emulated/0/Download/HyperDL 2>/dev/null || true
fi

# CONF_DIR holds the cookie session, so it stays owner-only.
mkdir -p /data/adb/hyperdl 2>/dev/null || true
chmod 0700 /data/adb/hyperdl 2>/dev/null || true
[ -f /data/adb/hyperdl/cookies.txt ] && chmod 0600 /data/adb/hyperdl/cookies.txt 2>/dev/null || true

CLIP_JAR=""
for j in "$MODDIR/bin/clip.jar" "$MODDIR/system/bin/clip.jar"; do
    if [ -f "$j" ]; then
        CLIP_JAR="$j"
        break
    fi
done
if [ -n "$CLIP_JAR" ] && [ ! -f /data/adb/hyperdl/clip.jar ]; then
    cp -f "$CLIP_JAR" /data/adb/hyperdl/clip.jar 2>/dev/null || true
    chmod 644 /data/adb/hyperdl/clip.jar 2>/dev/null || true
fi

# Keep the gallery-hidden marker in place on whichever storage we resolved.
for od in /storage/emulated/0/Download/HyperDL /data/media/0/Download/HyperDL; do
    if [ -d "$od/.vault" ]; then
        touch "$od/.vault/.nomedia" 2>/dev/null || true
        chmod 0666 "$od/.vault/.nomedia" 2>/dev/null || true
    fi
done

rm -f /data/local/tmp/hyperdl.pid /data/local/tmp/hyperdl_clip.pid 2>/dev/null || true

if [ -f /data/local/tmp/hyperdl_status.json ]; then
    sed -i 's/"status": *"downloading"/"status": "paused"/g' /data/local/tmp/hyperdl_status.json 2>/dev/null || true
    sed -i 's/"status": *"resolving"/"status": "paused"/g' /data/local/tmp/hyperdl_status.json 2>/dev/null || true
fi

if [ -f /data/adb/hyperdl/autodl.enabled ]; then
    DAEMON_BIN=""
    for d in "$MODDIR/bin/hyperdl_daemon" /data/adb/modules/hyperdl/bin/hyperdl_daemon "$MODDIR/system/bin/hyperdl_daemon" /data/adb/modules/hyperdl/system/bin/hyperdl_daemon; do
        if [ -x "$d" ]; then
            DAEMON_BIN="$d"
            break
        fi
    done
    if [ -n "$DAEMON_BIN" ]; then
        sh "$DAEMON_BIN" start >/dev/null 2>&1 &
    fi
fi

