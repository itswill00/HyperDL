#!/system/bin/sh
# Copyright (C) 2026 @itswill00
# Licensed under the GNU General Public License v3.0

set -e

PROJECT_DIR="/data/data/com.termux/files/home/HyperDL_Module"
cd "$PROJECT_DIR"

DEPLOY=false
CLEAN=false
CUSTOM_OUTPUT=""

while [ $# -gt 0 ]; do
    case "$1" in
        -d|--deploy)
            DEPLOY=true
            shift
            ;;
        -o|--output)
            CUSTOM_OUTPUT="$2"
            shift 2
            ;;
        -c|--clean)
            CLEAN=true
            shift
            ;;
        -h|--help)
            echo "Usage: ./build.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -d, --deploy       Deploy module directly to /data/adb/modules/hyperdl"
            echo "  -o, --output DIR   Specify custom output directory for zip releases"
            echo "  -c, --clean        Clean build caches before build"
            echo "  -h, --help         Show this help information"
            exit 0
            ;;
        *)
            echo "error: unrecognized option '$1' (use -h for help)"
            exit 1
            ;;
    esac
done

if [ ! -f "module.prop" ]; then
    echo "error: module.prop not found in $PROJECT_DIR"
    exit 1
fi

VERSION=$(grep '^version=' module.prop | cut -d= -f2)
VERSION_CODE=$(grep '^versionCode=' module.prop | cut -d= -f2)

if [ -n "$CUSTOM_OUTPUT" ]; then
    OUTPUT_DIR="$CUSTOM_OUTPUT"
elif [ -d "/sdcard" ]; then
    OUTPUT_DIR="/sdcard/HyperDL_Releases"
elif [ -d "/storage/emulated/0" ]; then
    OUTPUT_DIR="/storage/emulated/0/Download/HyperDL_Releases"
else
    OUTPUT_DIR="${PROJECT_DIR}/releases"
fi

ZIP_NAME="HyperDL-${VERSION}-b${VERSION_CODE}-Standalone.zip"
ZIP_ALIAS="HyperDL-${VERSION}.zip"
ZIP_LATEST="HyperDL-latest.zip"

echo "=========================================="
echo "  HyperDL Build Pipeline"
echo "  Version: ${VERSION} (b${VERSION_CODE})"
echo "  Target:  ${OUTPUT_DIR}/${ZIP_NAME}"
echo "=========================================="

for tool in clang zip node npm python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "error: required tool '$tool' is not installed"
        exit 1
    fi
done

if [ "$CLEAN" = "true" ]; then
    echo "cleaning build artifacts and caches..."
    rm -rf webui/dist webroot/index.html system/bin/libhyperdl.so system/bin/hyperdl.bundle runtime
fi

if [ -f "scripts/bundle_engine.py" ]; then
    echo "bundling python engine..."
    python3 scripts/bundle_engine.py
fi

if [ -f "src/main.c" ]; then
    echo "compiling c native bridge..."
    mkdir -p system/bin
    clang -O3 -Wall -Wextra src/main.c -o system/bin/libhyperdl.so
    strip --strip-unneeded system/bin/libhyperdl.so
    chmod 755 system/bin/libhyperdl.so
fi

chmod 755 system/bin/* 2>/dev/null || true

if [ -d "webui" ]; then
    if [ ! -d "webui/node_modules" ]; then
        echo "installing webui dependencies..."
        (cd webui && npm install --no-audit --no-fund)
    fi

    echo "compiling webui..."
    if ! (cd webui && node ./node_modules/vite/bin/vite.js build); then
        echo "error: vite build failed"
        exit 1
    fi

    if [ ! -f "webui/dist/index.html" ]; then
        echo "error: webui output not found"
        exit 1
    fi

    mkdir -p webroot
    cp webui/dist/index.html webroot/index.html
fi

if [ ! -f "runtime/bin/python3" ] || [ ! -f "runtime/bin/ffmpeg" ]; then
    if [ -f "scripts/bundle_runtime.py" ]; then
        python3 scripts/bundle_runtime.py
    fi
fi

if [ ! -f "system/bin/yt-dlp" ]; then
    echo "fetching latest standalone yt-dlp..."
    curl -sL "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp" -o system/bin/yt-dlp
    chmod 755 system/bin/yt-dlp
fi

if [ -f "scripts/optimize_ytdlp.py" ] && [ -f "system/bin/yt-dlp" ]; then
    python3 scripts/optimize_ytdlp.py system/bin/yt-dlp
fi

mkdir -p "$OUTPUT_DIR"
rm -f "$OUTPUT_DIR/HyperDL-${VERSION}-b${VERSION_CODE}"*.zip

echo "packaging module zip..."
zip -qr9 "$OUTPUT_DIR/$ZIP_NAME" \
    module.prop \
    customize.sh \
    service.sh \
    uninstall.sh \
    system \
    runtime \
    webroot \
    -x "*.git*" "webui/*" "webroot/*.map" "*.py" "*__pycache__*"

cp -f "$OUTPUT_DIR/$ZIP_NAME" "$OUTPUT_DIR/$ZIP_ALIAS"
cp -f "$OUTPUT_DIR/$ZIP_NAME" "$OUTPUT_DIR/$ZIP_LATEST"

if [ -d "/storage/emulated/0/Download" ] && [ "$OUTPUT_DIR" != "/storage/emulated/0/Download" ]; then
    cp -f "$OUTPUT_DIR/$ZIP_NAME" "/storage/emulated/0/Download/$ZIP_ALIAS"
    am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file:///storage/emulated/0/Download/$ZIP_ALIAS" >/dev/null 2>&1 || true
fi

am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file://$OUTPUT_DIR/$ZIP_NAME" >/dev/null 2>&1 || true
am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file://$OUTPUT_DIR/$ZIP_ALIAS" >/dev/null 2>&1 || true

ZIP_SIZE=$(du -h "$OUTPUT_DIR/$ZIP_NAME" | cut -f1)
CHECKSUM=$(sha256sum "$OUTPUT_DIR/$ZIP_NAME" | cut -d' ' -f1)

echo "=========================================="
echo "  Build successful!"
echo "  Package:  ${OUTPUT_DIR}/${ZIP_NAME} (${ZIP_SIZE})"
echo "  Aliases:  ${OUTPUT_DIR}/${ZIP_ALIAS}"
echo "            ${OUTPUT_DIR}/${ZIP_LATEST}"
echo "  SHA-256:  ${CHECKSUM}"
echo "=========================================="

if [ "$DEPLOY" = "true" ]; then
    echo "deploying to live device modules..."
    if su -c "
        if [ -f /data/local/tmp/hyperdl_clip.pid ]; then
            kill -9 \$(cat /data/local/tmp/hyperdl_clip.pid 2>/dev/null) 2>/dev/null || true
            rm -f /data/local/tmp/hyperdl_clip.pid
        fi
        if [ -f /data/local/tmp/hyperdl.pid ]; then
            kill -9 \$(cat /data/local/tmp/hyperdl.pid 2>/dev/null) 2>/dev/null || true
            rm -f /data/local/tmp/hyperdl.pid
        fi

        MOD_TARGET=\"/data/adb/modules/hyperdl\"
        mkdir -p \"\$MOD_TARGET/system/bin\"
        mkdir -p \"\$MOD_TARGET/webroot\"
        mkdir -p /storage/emulated/0/Download/HyperDL
        rm -rf \"\$MOD_TARGET/engine\"

        cp -f module.prop \"\$MOD_TARGET/module.prop\"
        cp -f customize.sh \"\$MOD_TARGET/customize.sh\"
        cp -f service.sh \"\$MOD_TARGET/service.sh\"
        cp -f uninstall.sh \"\$MOD_TARGET/uninstall.sh\"
        cp -f system/bin/libhyperdl.so \"\$MOD_TARGET/system/bin/libhyperdl.so\"
        cp -f system/bin/hyperdl.bundle \"\$MOD_TARGET/system/bin/hyperdl.bundle\"
        cp -f system/bin/hyperdl_daemon \"\$MOD_TARGET/system/bin/hyperdl_daemon\"
        [ -f system/bin/yt-dlp ] && cp -f system/bin/yt-dlp \"\$MOD_TARGET/system/bin/yt-dlp\"
        cp -f webroot/index.html \"\$MOD_TARGET/webroot/index.html\"

        rm -rf \"\$MOD_TARGET/runtime\"
        mkdir -p \"\$MOD_TARGET/runtime\"
        cp -rf runtime/* \"\$MOD_TARGET/runtime/\"

        chmod 755 \"\$MOD_TARGET/system/bin/\"*
        chmod 755 \"\$MOD_TARGET/runtime/bin/\"* 2>/dev/null || true
        chmod 755 \"\$MOD_TARGET/service.sh\" \"\$MOD_TARGET/uninstall.sh\"
        chmod 644 \"\$MOD_TARGET/module.prop\" \"\$MOD_TARGET/webroot/index.html\"

        if [ -f /data/adb/hyperdl/autodl.enabled ]; then
            sh \"\$MOD_TARGET/system/bin/hyperdl_daemon\" start >/dev/null 2>&1 &
        fi
    "; then
        echo "deploy complete: live module updated successfully"
    else
        echo "error: deploy failed"
        exit 1
    fi
fi
