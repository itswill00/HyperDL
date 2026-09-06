#!/system/bin/sh
MODDIR="${0%/*}"

# Wait until boot completed
while [ "$(getprop sys.boot_completed)" != "1" ]; do
    sleep 3
done

sleep 2

mkdir -p /storage/emulated/0/Download/HyperDL 2>/dev/null || true
mkdir -p /data/adb/hyperdl 2>/dev/null || true
rm -f /data/local/tmp/hyperdl_status.json /data/local/tmp/hyperdl.pid 2>/dev/null || true

# Auto-start clipboard daemon if enabled in config
if [ -f /data/adb/hyperdl/autodl.enabled ]; then
    sh "$MODDIR/engine/clipboard_daemon.sh" start >/dev/null 2>&1 &
fi
