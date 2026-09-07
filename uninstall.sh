#!/system/bin/sh
# Terminate background daemons and active processes
if [ -f /data/local/tmp/hyperdl_clip.pid ]; then
    kill -9 $(cat /data/local/tmp/hyperdl_clip.pid 2>/dev/null) 2>/dev/null || true
fi
if [ -f /data/local/tmp/hyperdl.pid ]; then
    kill -9 $(cat /data/local/tmp/hyperdl.pid 2>/dev/null) 2>/dev/null || true
fi
pkill -9 -f hyperdl_daemon 2>/dev/null || true
pkill -9 -f hyperdl.bundle 2>/dev/null || true
pkill -9 -f "yt-dlp.*HyperDL" 2>/dev/null || true

# Cleanup transient runtime caches and PID files
rm -f /data/local/tmp/hyperdl* 2>/dev/null || true

# Remove internal configuration and state
rm -rf /data/adb/hyperdl 2>/dev/null || true

# NOTE: Personal downloaded files in /storage/emulated/0/Download/HyperDL
# are preserved so user never loses their saved media.
exit 0
