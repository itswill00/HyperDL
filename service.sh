#!/system/bin/sh
MODDIR="${0%/*}"

# 1. Wait for Android system boot completion
while [ "$(getprop sys.boot_completed)" != "1" ]; do
    sleep 3
done

# 2. Wait for user storage decryption (FBE Direct Boot on Android 10-15)
MAX_WAIT=30
while [ $MAX_WAIT -gt 0 ]; do
    if [ -d /storage/emulated/0/Download ] || [ "$(getprop sys.user_0_ce_available)" = "true" ]; then
        break
    fi
    sleep 2
    MAX_WAIT=$((MAX_WAIT - 1))
done

# 3. Ensure primary directories exist with full read/write permissions
mkdir -p /storage/emulated/0/Download/HyperDL 2>/dev/null || true
chmod 0777 /storage/emulated/0/Download/HyperDL 2>/dev/null || true
mkdir -p /data/adb/hyperdl 2>/dev/null || true
chmod 0777 /data/adb/hyperdl 2>/dev/null || true

# 4. Synchronize clip.jar to persistent config dir if missing
if [ -f "$MODDIR/system/bin/clip.jar" ] && [ ! -f /data/adb/hyperdl/clip.jar ]; then
    cp -f "$MODDIR/system/bin/clip.jar" /data/adb/hyperdl/clip.jar 2>/dev/null || true
    chmod 644 /data/adb/hyperdl/clip.jar 2>/dev/null || true
fi

# 5. Guarantee .nomedia protection in .vault immediately on boot before MediaStore scans
if [ -d /storage/emulated/0/Download/HyperDL/.vault ]; then
    touch /storage/emulated/0/Download/HyperDL/.vault/.nomedia 2>/dev/null || true
    chmod 0666 /storage/emulated/0/Download/HyperDL/.vault/.nomedia 2>/dev/null || true
fi

# 6. Cleanup stale PIDs from previous boot or unexpected reboot
rm -f /data/local/tmp/hyperdl.pid /data/local/tmp/hyperdl_clip.pid 2>/dev/null || true

# 7. Recover stale active tasks in status JSON
if [ -f /data/local/tmp/hyperdl_status.json ]; then
    sed -i 's/"status": *"downloading"/"status": "paused"/g' /data/local/tmp/hyperdl_status.json 2>/dev/null || true
    sed -i 's/"status": *"resolving"/"status": "paused"/g' /data/local/tmp/hyperdl_status.json 2>/dev/null || true
fi

# 8. Start auto clipboard daemon if enabled by user
if [ -f /data/adb/hyperdl/autodl.enabled ]; then
    DAEMON_BIN=""
    for d in "$MODDIR/system/bin/hyperdl_daemon" /data/adb/modules/hyperdl/system/bin/hyperdl_daemon; do
        if [ -x "$d" ]; then
            DAEMON_BIN="$d"
            break
        fi
    done
    if [ -n "$DAEMON_BIN" ]; then
        sh "$DAEMON_BIN" start >/dev/null 2>&1 &
    fi
fi

