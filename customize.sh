#!/system/bin/sh
SKIPUNZIP=1

ui_print "- Installing HyperDL..."
ui_print "- Extracting files..."
unzip -o "$ZIPFILE" -x 'META-INF/*' -d "$MODPATH" >/dev/null 2>&1

ui_print "- Preparing directories..."
mkdir -p /storage/emulated/0/Download/HyperDL 2>/dev/null
mkdir -p /data/adb/hyperdl 2>/dev/null
mkdir -p /data/local/tmp 2>/dev/null

ui_print "- Setting file permissions..."
set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm_recursive "$MODPATH/engine" 0 0 0755 0755
chmod 755 "$MODPATH/service.sh" 2>/dev/null
chmod 755 "$MODPATH/engine/bridge.sh" 2>/dev/null
chmod 755 "$MODPATH/engine/downloader.py" 2>/dev/null
chmod 755 "$MODPATH/engine/clipboard_daemon.sh" 2>/dev/null

if [ -f "$MODPATH/webroot/index.html" ]; then
    ui_print "- WebUI configured."
fi

ui_print "- Done. Open your root manager to access the WebUI."
