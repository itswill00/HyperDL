#!/system/bin/sh
SKIPUNZIP=1

kill_hyperdl_pid() {
    _pf="$1"
    [ -f "$_pf" ] || return 0
    _pid="$(cat "$_pf" 2>/dev/null)"
    case "$_pid" in ''|*[!0-9]*) _pid="" ;; esac
    if [ -n "$_pid" ] && {
        { [ -r "/proc/$_pid/cmdline" ] && \
          tr '\0' ' ' < "/proc/$_pid/cmdline" | grep -q hyperdl; } || \
        { [ -r "/proc/$_pid/environ" ] && \
          tr '\0' '\n' < "/proc/$_pid/environ" | grep -q '^HYPERDL_BRIDGE=1$'; }
    }; then
        kill -9 "$_pid" 2>/dev/null || true
    fi
    rm -f "$_pf"
}

ARCH_ABI=$(getprop ro.product.cpu.abi 2>/dev/null)
if [ "$ARCH" != "arm64" ] && [ "$ARCH_ABI" != "arm64-v8a" ]; then
    ui_print "! Unsupported architecture: $ARCH ($ARCH_ABI)"
    ui_print "! HyperDL standalone runtime requires 64-bit ARM (arm64)."
    abort "! Installation aborted."
fi

ui_print "- Installing HyperDL..."

kill_hyperdl_pid /data/local/tmp/hyperdl_clip.pid
kill_hyperdl_pid /data/local/tmp/hyperdl.pid
pkill -9 -f hyperdl_daemon 2>/dev/null || true
pkill -9 -f hyperdl.bundle 2>/dev/null || true

rm -rf "$MODPATH/system" 2>/dev/null || true

ui_print "- Extracting files..."
unzip -o "$ZIPFILE" -x 'META-INF/*' -d "$MODPATH" >/dev/null 2>&1

ui_print "- Preparing directories..."
# Work profiles and secondary users do not own /storage/emulated/0. Fall back to
# /data/media/0 so downloads still work outside the primary user.
if ! mkdir -p /storage/emulated/0/Download/HyperDL 2>/dev/null || [ ! -w /storage/emulated/0/Download/HyperDL ]; then
    ui_print "! /storage/emulated/0 is not writable, using /data/media/0 instead."
    mkdir -p /data/media/0/Download/HyperDL 2>/dev/null || true
    chmod 0777 /data/media/0/Download/HyperDL 2>/dev/null || true
else
    chmod 0777 /storage/emulated/0/Download/HyperDL 2>/dev/null || true
fi

# CONF_DIR holds the cookie session, so it stays owner-only. The bridge always
# runs as root, so nothing legitimate loses access.
mkdir -p /data/adb/hyperdl 2>/dev/null || true
chmod 0700 /data/adb/hyperdl 2>/dev/null || true
[ -f /data/adb/hyperdl/cookies.txt ] && chmod 0600 /data/adb/hyperdl/cookies.txt 2>/dev/null || true
mkdir -p /data/local/tmp 2>/dev/null || true

if [ -f "$MODPATH/bin/clip.jar" ]; then
    cp -f "$MODPATH/bin/clip.jar" /data/adb/hyperdl/clip.jar 2>/dev/null || true
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
        # $MODPATH points at modules_update during install and disappears after
        # the reboot, so link to the stable installed path instead.
        ln -sf /data/adb/modules/hyperdl/bin/libhyperdl.so "$mgr_bin/hyperdl" 2>/dev/null || true
    fi
done

chcon -R u:object_r:system_file:s0 "$MODPATH" 2>/dev/null || true

if [ -f "$MODPATH/webroot/index.html" ]; then
    ui_print "- WebUI configured."
fi

ui_print "- Installation complete."
ui_print "- Please reboot your device to activate HyperDL."
