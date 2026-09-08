#!/system/bin/sh
SKIPUNZIP=1

if [ "$ARCH" != "arm64" ]; then
    ui_print "! Unsupported architecture: $ARCH"
    ui_print "! HyperDL standalone runtime requires 64-bit ARM (arm64)."
    abort "! Installation aborted."
fi

ui_print "- Installing HyperDL..."

# Stop any running daemons or downloads from previous version before extracting
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

ui_print "- Extracting files..."
unzip -o "$ZIPFILE" -x 'META-INF/*' -d "$MODPATH" >/dev/null 2>&1

ui_print "- Preparing directories..."
mkdir -p /storage/emulated/0/Download/HyperDL 2>/dev/null || true
chmod 0777 /storage/emulated/0/Download/HyperDL 2>/dev/null || true
mkdir -p /data/adb/hyperdl 2>/dev/null || true
chmod 0777 /data/adb/hyperdl 2>/dev/null || true
mkdir -p /data/local/tmp 2>/dev/null || true
chmod 0777 /data/local/tmp 2>/dev/null || true

# Synchronize clip.jar to persistent config directory
if [ -f "$MODPATH/system/bin/clip.jar" ]; then
    cp -f "$MODPATH/system/bin/clip.jar" /data/adb/hyperdl/clip.jar 2>/dev/null || true
    chmod 644 /data/adb/hyperdl/clip.jar 2>/dev/null || true
fi

# Ensure .nomedia in .vault if vault directory exists
if [ -d /storage/emulated/0/Download/HyperDL/.vault ]; then
    touch /storage/emulated/0/Download/HyperDL/.vault/.nomedia 2>/dev/null || true
    chmod 0666 /storage/emulated/0/Download/HyperDL/.vault/.nomedia 2>/dev/null || true
fi

ui_print "- Setting file permissions and SELinux contexts..."
set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm_recursive "$MODPATH/system/bin" 0 0 0755 0755
set_perm_recursive "$MODPATH/runtime/bin" 0 0 0755 0755
set_perm_recursive "$MODPATH/runtime/lib" 0 0 0755 0755
chmod 755 "$MODPATH/system/bin/libhyperdl.so" 2>/dev/null
chmod 755 "$MODPATH/system/bin/hyperdl.bundle" 2>/dev/null
chmod 755 "$MODPATH/system/bin/hyperdl_daemon" 2>/dev/null
chmod 755 "$MODPATH/system/bin/yt-dlp" 2>/dev/null
chmod 644 "$MODPATH/system/bin/clip.jar" 2>/dev/null
chmod 755 "$MODPATH/runtime/bin/python3" 2>/dev/null
chmod 755 "$MODPATH/runtime/bin/ffmpeg" "$MODPATH/runtime/bin/ffmpeg.bin" 2>/dev/null || true
chmod 755 "$MODPATH/runtime/bin/ffprobe" "$MODPATH/runtime/bin/ffprobe.bin" 2>/dev/null || true
chmod 755 "$MODPATH/service.sh" 2>/dev/null
chmod 755 "$MODPATH/uninstall.sh" 2>/dev/null
chmod 644 "$MODPATH/module.prop" 2>/dev/null
chmod 644 "$MODPATH/webroot/index.html" 2>/dev/null

# Enforce system SELinux contexts for Android 10-15+ compatibility
chcon -R u:object_r:system_file:s0 "$MODPATH" 2>/dev/null || true

if [ -f "$MODPATH/webroot/index.html" ]; then
    ui_print "- WebUI configured."
fi

ui_print "- Installation complete."
ui_print "- Please reboot your device to activate HyperDL."
