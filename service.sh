#!/system/bin/sh
MODDIR="${0%/*}"

pid_is_hyperdl() {
    [ -n "$1" ] || return 1
    kill -0 "$1" 2>/dev/null || return 1
    if [ -r "/proc/$1/cmdline" ] && \
       tr '\0' ' ' < "/proc/$1/cmdline" 2>/dev/null | grep -q hyperdl; then
        return 0
    fi
    if [ -r "/proc/$1/environ" ] && \
       tr '\0' '\n' < "/proc/$1/environ" 2>/dev/null | grep -q '^HYPERDL_BRIDGE=1$'; then
        return 0
    fi
    return 1
}

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
[ -f /data/local/tmp/hyperdl_last_clip.txt ] && chmod 0600 /data/local/tmp/hyperdl_last_clip.txt 2>/dev/null || true
[ -f /data/local/tmp/hyperdl_engine.log ] && chmod 0640 /data/local/tmp/hyperdl_engine.log 2>/dev/null || true

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
        chmod 0755 "$od/.vault" 2>/dev/null || true
        touch "$od/.vault/.nomedia" 2>/dev/null || true
        chmod 0644 "$od/.vault/.nomedia" 2>/dev/null || true
    fi
done

# Never rewrite a live task to "paused" just because this script ran. At boot
# the PID file points at a process from the previous boot and is stale, so the
# check simply lets the normal reset below run.
ACTIVE_DOWNLOAD=0
if [ -f /data/local/tmp/hyperdl.pid ]; then
    _active_pid="$(cat /data/local/tmp/hyperdl.pid 2>/dev/null)"
    case "$_active_pid" in
        ''|*[!0-9]*) ;;
        *)
            if pid_is_hyperdl "$_active_pid"; then
                ACTIVE_DOWNLOAD=1
            fi
            ;;
    esac
fi

if [ "$ACTIVE_DOWNLOAD" -eq 0 ]; then
    rm -f /data/local/tmp/hyperdl.pid /data/local/tmp/hyperdl_clip.pid 2>/dev/null || true

    for status_file in /data/local/tmp/hyperdl_status.json /data/adb/hyperdl/active_task.json; do
        if [ -f "$status_file" ]; then
            sed -i 's/"status": *"downloading"/"status": "paused"/g' "$status_file" 2>/dev/null || true
            sed -i 's/"status": *"resolving"/"status": "paused"/g' "$status_file" 2>/dev/null || true
            chmod 600 "$status_file" 2>/dev/null || true
        fi
    done
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

