#!/system/bin/sh
SKIPUNZIP=1

ARCH_ABI=$(getprop ro.product.cpu.abi 2>/dev/null)
if [ "$ARCH" != "arm64" ] && [ "$ARCH_ABI" != "arm64-v8a" ]; then
    ui_print "! Unsupported architecture: $ARCH ($ARCH_ABI)"
    ui_print "! HyperDL standalone runtime requires 64-bit ARM (arm64)."
    abort "! Installation aborted."
fi

ui_print "- Installing HyperDL..."

if [ -f /data/local/tmp/hyperdl_clip.pid ]; then
    kill -9 $(cat /data/local/tmp/hyperdl_clip.pid 2>/dev/null) 2>/dev/null || true
    rm -f /data/local/tmp/hyperdl_clip.pid
fi
if [ -f /data/local/tmp/hyperdl.pid ]; then
    kill -9 $(cat /data/local/tmp/hyperdl.pid 2>/dev/null) 2>/dev/null || true
    rm -f /data/local/tmp/hyperdl.pid
fi
pkill -9 -f hyperdl_daemon 2>/dev/null || true
pkill -9 -f hyperdl.bundle 2>/dev/null || true

rm -rf "$MODPATH/system" 2>/dev/null || true

ui_print "- Extracting files..."
unzip -o "$ZIPFILE" -x 'META-INF/*' -d "$MODPATH" >/dev/null 2>&1

ui_print "- Preparing directories..."
mkdir -p /storage/emulated/0/Download/HyperDL 2>/dev/null || true
chmod 0777 /storage/emulated/0/Download/HyperDL 2>/dev/null || true
mkdir -p /data/adb/hyperdl 2>/dev/null || true
chmod 0777 /data/adb/hyperdl 2>/dev/null || true
mkdir -p /data/local/tmp 2>/dev/null || true
chmod 0777 /data/local/tmp 2>/dev/null || true

if [ -f "$MODPATH/bin/clip.jar" ]; then
    cp -f "$MODPATH/bin/clip.jar" /data/adb/hyperdl/clip.jar 2>/dev/null || true
    chmod 644 /data/adb/hyperdl/clip.jar 2>/dev/null || true
fi

if [ -d /storage/emulated/0/Download/HyperDL/.vault ]; then
    touch /storage/emulated/0/Download/HyperDL/.vault/.nomedia 2>/dev/null || true
    chmod 0666 /storage/emulated/0/Download/HyperDL/.vault/.nomedia 2>/dev/null || true
fi

ui_print "- Setting file permissions and SELinux contexts..."
set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm_recursive "$MODPATH/bin" 0 0 0755 0755
set_perm_recursive "$MODPATH/runtime/bin" 0 0 0755 0755
set_perm_recursive "$MODPATH/runtime/lib" 0 0 0755 0755
chmod 755 "$MODPATH/bin/libhyperdl.so" 2>/dev/null
chmod 755 "$MODPATH/bin/hyperdl.bundle" 2>/dev/null
chmod 755 "$MODPATH/bin/hyperdl_daemon" 2>/dev/null
chmod 755 "$MODPATH/bin/yt-dlp" 2>/dev/null
chmod 644 "$MODPATH/bin/clip.jar" 2>/dev/null
chmod 755 "$MODPATH/runtime/bin/python3" 2>/dev/null
chmod 755 "$MODPATH/runtime/bin/ffmpeg" "$MODPATH/runtime/bin/ffmpeg.bin" 2>/dev/null || true
chmod 755 "$MODPATH/runtime/bin/ffprobe" "$MODPATH/runtime/bin/ffprobe.bin" 2>/dev/null || true
chmod 755 "$MODPATH/service.sh" 2>/dev/null
chmod 755 "$MODPATH/uninstall.sh" 2>/dev/null
chmod 644 "$MODPATH/module.prop" 2>/dev/null
chmod 644 "$MODPATH/webroot/index.html" 2>/dev/null

for mgr_bin in /data/adb/ap/bin /data/adb/ksu/bin /data/adb/modules/bin; do
    if [ -d "$mgr_bin" ]; then
        ln -sf "$MODPATH/bin/libhyperdl.so" "$mgr_bin/hyperdl" 2>/dev/null || true
    fi
done

chcon -R u:object_r:system_file:s0 "$MODPATH" 2>/dev/null || true

if [ -f "$MODPATH/webroot/index.html" ]; then
    ui_print "- WebUI configured."
fi

ui_print "- Installation complete."
ui_print "- Please reboot your device to activate HyperDL."
