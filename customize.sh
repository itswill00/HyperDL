#!/system/bin/sh
SKIPUNZIP=1

if [ "$ARCH" != "arm64" ]; then
    ui_print "! Unsupported architecture: $ARCH"
    ui_print "! HyperDL standalone runtime requires 64-bit ARM (arm64)."
    abort "! Installation aborted."
fi

ui_print "- Installing HyperDL..."
ui_print "- Extracting files..."
unzip -o "$ZIPFILE" -x 'META-INF/*' -d "$MODPATH" >/dev/null 2>&1

ui_print "- Preparing directories..."
mkdir -p /storage/emulated/0/Download/HyperDL 2>/dev/null
chmod 0777 /storage/emulated/0/Download/HyperDL 2>/dev/null
mkdir -p /data/adb/hyperdl 2>/dev/null
chmod 0777 /data/adb/hyperdl 2>/dev/null
mkdir -p /data/local/tmp 2>/dev/null
chmod 0777 /data/local/tmp 2>/dev/null

ui_print "- Setting file permissions..."
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
chmod 755 "$MODPATH/runtime/bin/ffmpeg" 2>/dev/null
chmod 755 "$MODPATH/runtime/bin/ffprobe" 2>/dev/null
chmod 755 "$MODPATH/service.sh" 2>/dev/null
chmod 755 "$MODPATH/uninstall.sh" 2>/dev/null

if [ -f "$MODPATH/webroot/index.html" ]; then
    ui_print "- WebUI configured."
fi

ui_print "- Installation complete."
ui_print "- Please reboot your device to activate HyperDL."
