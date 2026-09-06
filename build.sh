#!/system/bin/sh

PROJECT_DIR="/data/data/com.termux/files/home/HyperDL_Module"
OUTPUT_DIR="/storage/emulated/0/Download"

set -e

cd "$PROJECT_DIR"

if [ ! -f "module.prop" ]; then
    echo "error: module.prop not found"
    exit 1
fi

VERSION=$(grep '^version=' module.prop | cut -d= -f2)
VERSION_CODE=$(grep '^versionCode=' module.prop | cut -d= -f2)
ZIP_OUT="HyperDL-${VERSION}.zip"

echo "building hyperdl ${VERSION} (${VERSION_CODE})"

for tool in zip node; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "error: $tool is not installed"
        exit 1
    fi
done

if [ -d "webui" ]; then
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

mkdir -p "$OUTPUT_DIR"
rm -f "$OUTPUT_DIR/$ZIP_OUT"

echo "packaging module zip..."
zip -qr9 "$OUTPUT_DIR/$ZIP_OUT" \
    module.prop \
    customize.sh \
    service.sh \
    uninstall.sh \
    engine \
    webroot \
    -x "*.git*" "webui/*" "webroot/*.map"

echo "build complete: $OUTPUT_DIR/$ZIP_OUT"

if [ "$1" = "--deploy" ]; then
    echo "deploying to live device modules..."
    if su -c "
        MOD_TARGET=\"/data/adb/modules/hyperdl\"
        mkdir -p \"\$MOD_TARGET/engine\"
        mkdir -p \"\$MOD_TARGET/webroot\"
        mkdir -p /storage/emulated/0/Download/HyperDL

        cp -f module.prop \"\$MOD_TARGET/module.prop\"
        cp -f customize.sh \"\$MOD_TARGET/customize.sh\"
        cp -f service.sh \"\$MOD_TARGET/service.sh\"
        cp -f uninstall.sh \"\$MOD_TARGET/uninstall.sh\"
        cp -f engine/downloader.py \"\$MOD_TARGET/engine/downloader.py\"
        cp -f engine/bridge.sh \"\$MOD_TARGET/engine/bridge.sh\"
        cp -f engine/clipboard_daemon.sh \"\$MOD_TARGET/engine/clipboard_daemon.sh\"
        cp -f webroot/index.html \"\$MOD_TARGET/webroot/index.html\"

        chmod 755 \"\$MOD_TARGET/service.sh\" \"\$MOD_TARGET/uninstall.sh\"
        chmod 755 \"\$MOD_TARGET/engine/\"*
        chmod 644 \"\$MOD_TARGET/module.prop\" \"\$MOD_TARGET/webroot/index.html\"
    "; then
        echo "deploy complete"
    else
        echo "error: deploy failed"
        exit 1
    fi
fi
