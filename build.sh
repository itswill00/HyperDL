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

for tool in clang zip node python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "error: $tool is not installed"
        exit 1
    fi
done

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

if [ ! -f "runtime/bin/python3" ] && [ -f "scripts/bundle_runtime.py" ]; then
    python3 scripts/bundle_runtime.py
fi

mkdir -p "$OUTPUT_DIR"
rm -f "$OUTPUT_DIR/$ZIP_OUT"

echo "packaging module zip..."
zip -qr9 "$OUTPUT_DIR/$ZIP_OUT" \
    module.prop \
    customize.sh \
    service.sh \
    uninstall.sh \
    system \
    runtime \
    webroot \
    -x "*.git*" "webui/*" "webroot/*.map" "*.py" "*__pycache__*"

echo "build complete: $OUTPUT_DIR/$ZIP_OUT"

if [ "$1" = "--deploy" ]; then
    echo "deploying to live device modules..."
    if su -c "
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
        cp -f webroot/index.html \"\$MOD_TARGET/webroot/index.html\"

        rm -rf \"\$MOD_TARGET/runtime\"
        mkdir -p \"\$MOD_TARGET/runtime\"
        cp -rf runtime/* \"\$MOD_TARGET/runtime/\"

        chmod 755 \"\$MOD_TARGET/system/bin/\"*
        chmod 755 \"\$MOD_TARGET/runtime/bin/\"* 2>/dev/null || true
        chmod 755 \"\$MOD_TARGET/service.sh\" \"\$MOD_TARGET/uninstall.sh\"
        chmod 644 \"\$MOD_TARGET/module.prop\" \"\$MOD_TARGET/webroot/index.html\"
    "; then
        echo "deploy complete"
    else
        echo "error: deploy failed"
        exit 1
    fi
fi
