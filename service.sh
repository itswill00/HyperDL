#!/system/bin/sh
MODDIR="${0%/*}"

while [ "$(getprop sys.boot_completed)" != "1" ]; do
    sleep 3
done

sleep 2

mkdir -p /storage/emulated/0/Download/HyperDL 2>/dev/null || true
chmod 0777 /storage/emulated/0/Download/HyperDL 2>/dev/null || true
mkdir -p /data/adb/hyperdl 2>/dev/null || true
chmod 0777 /data/adb/hyperdl 2>/dev/null || true
rm -f /data/local/tmp/hyperdl.pid 2>/dev/null || true

if [ -f /data/adb/hyperdl/autodl.enabled ]; then
    if [ -x "$MODDIR/system/bin/hyperdl_daemon" ]; then
        sh "$MODDIR/system/bin/hyperdl_daemon" start >/dev/null 2>&1 &
    fi
fi

