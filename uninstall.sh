#!/system/bin/sh
if [ -f /data/local/tmp/hyperdl_clip.pid ]; then
    kill -9 $(cat /data/local/tmp/hyperdl_clip.pid) 2>/dev/null || true
fi
if [ -f /data/local/tmp/hyperdl.pid ]; then
    kill -9 $(cat /data/local/tmp/hyperdl.pid) 2>/dev/null || true
fi
rm -rf /data/adb/hyperdl /data/local/tmp/hyperdl* 2>/dev/null || true
