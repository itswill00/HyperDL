#!/system/bin/sh

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

kill_hyperdl_pid /data/local/tmp/hyperdl_clip.pid
kill_hyperdl_pid /data/local/tmp/hyperdl.pid
pkill -9 -f hyperdl_daemon 2>/dev/null || true
pkill -9 -f hyperdl.bundle 2>/dev/null || true
pkill -9 -f "yt-dlp.*HyperDL" 2>/dev/null || true

rm -f /data/local/tmp/hyperdl* 2>/dev/null || true

# Downloaded media is the user's data and stays untouched. Everything else,
# including the resolution cache, goes.
rm -rf /data/adb/hyperdl 2>/dev/null || true

exit 0
