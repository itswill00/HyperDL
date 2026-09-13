#!/system/bin/sh
# Copyright (C) 2026 @noticesa
# Licensed under the GNU General Public License v3.0

set -e

PROJECT_DIR="/data/data/com.termux/files/home/HyperDL_Module"
cd "$PROJECT_DIR"

DEPLOY=false
CLEAN=false
RELEASE=false
CUSTOM_OUTPUT=""

while [ $# -gt 0 ]; do
    case "$1" in
        -d|--deploy)
            DEPLOY=true
            shift
            ;;
        -r|--release)
            RELEASE=true
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
            echo "  -r, --release      Publish release assets to itswill00/HyperDL-Release"
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
    echo "bundling python extractor..."
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

if [ -f "src/sitecustomize.py" ]; then
    mkdir -p runtime/lib/python3.14
    cp -f src/sitecustomize.py runtime/lib/python3.14/sitecustomize.py
fi

STAGING_DIR="${PROJECT_DIR}/releases"
mkdir -p "$STAGING_DIR"
rm -f "$STAGING_DIR/HyperDL-${VERSION}-b${VERSION_CODE}"*.zip

echo "packaging standalone module zip..."
zip -qr9 "$STAGING_DIR/$ZIP_NAME" \
    module.prop \
    customize.sh \
    service.sh \
    uninstall.sh \
    system \
    runtime \
    webroot \
    -x "*.git*" "webui/*" "webroot/*.map" "*.pyc" "*__pycache__*"

cp -f "$STAGING_DIR/$ZIP_NAME" "$STAGING_DIR/$ZIP_ALIAS"
cp -f "$STAGING_DIR/$ZIP_NAME" "$STAGING_DIR/$ZIP_LATEST"

OTA_NAME="HyperDL-${VERSION}-b${VERSION_CODE}-OTA.zip"
OTA_ALIAS="HyperDL-OTA-${VERSION}.zip"
OTA_LATEST="HyperDL-OTA-latest.zip"

echo "packaging lightweight ota zip..."
zip -qr9 "$STAGING_DIR/$OTA_NAME" \
    module.prop \
    system/bin/hyperdl.bundle \
    system/bin/libhyperdl.so \
    system/bin/hyperdl_daemon \
    system/bin/clip.jar \
    webroot \
    -x "*.git*" "webui/*" "webroot/*.map" "*.pyc" "*__pycache__*"

cp -f "$STAGING_DIR/$OTA_NAME" "$STAGING_DIR/$OTA_ALIAS"
cp -f "$STAGING_DIR/$OTA_NAME" "$STAGING_DIR/$OTA_LATEST"

if [ "$OUTPUT_DIR" != "$STAGING_DIR" ]; then
    if mkdir -p "$OUTPUT_DIR" 2>/dev/null; then
        cp -f "$STAGING_DIR"/* "$OUTPUT_DIR/" 2>/dev/null || true
    else
        su -c "mkdir -p '$OUTPUT_DIR' && cp -f '$STAGING_DIR'/* '$OUTPUT_DIR/' && chmod 666 '$OUTPUT_DIR'/*" 2>/dev/null || true
    fi
fi

if [ -d "/storage/emulated/0/Download" ] && [ "$OUTPUT_DIR" != "/storage/emulated/0/Download" ]; then
    cp -f "$STAGING_DIR/$ZIP_NAME" "/storage/emulated/0/Download/$ZIP_ALIAS" 2>/dev/null || su -c "cp -f '$STAGING_DIR/$ZIP_NAME' '/storage/emulated/0/Download/$ZIP_ALIAS' && chmod 666 '/storage/emulated/0/Download/$ZIP_ALIAS'" 2>/dev/null || true
    cp -f "$STAGING_DIR/$OTA_NAME" "/storage/emulated/0/Download/$OTA_ALIAS" 2>/dev/null || su -c "cp -f '$STAGING_DIR/$OTA_NAME' '/storage/emulated/0/Download/$OTA_ALIAS' && chmod 666 '/storage/emulated/0/Download/$OTA_ALIAS'" 2>/dev/null || true
    am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file:///storage/emulated/0/Download/$ZIP_ALIAS" >/dev/null 2>&1 || true
    am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file:///storage/emulated/0/Download/$OTA_ALIAS" >/dev/null 2>&1 || true
fi

am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file://$OUTPUT_DIR/$ZIP_NAME" >/dev/null 2>&1 || true
am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file://$OUTPUT_DIR/$ZIP_ALIAS" >/dev/null 2>&1 || true
am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file://$OUTPUT_DIR/$OTA_NAME" >/dev/null 2>&1 || true
am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file://$OUTPUT_DIR/$OTA_ALIAS" >/dev/null 2>&1 || true

ZIP_SIZE=$(du -h "$STAGING_DIR/$ZIP_NAME" | cut -f1)
OTA_SIZE=$(du -h "$STAGING_DIR/$OTA_NAME" | cut -f1)
CHECKSUM=$(sha256sum "$STAGING_DIR/$ZIP_NAME" | cut -d' ' -f1)
OTA_CHECKSUM=$(sha256sum "$STAGING_DIR/$OTA_NAME" | cut -d' ' -f1)

echo "=========================================="
echo "  Build successful!"
echo "  Standalone:  ${OUTPUT_DIR}/${ZIP_NAME} (${ZIP_SIZE})"
echo "  OTA Package: ${OUTPUT_DIR}/${OTA_NAME} (${OTA_SIZE})"
echo "  Aliases:     ${OUTPUT_DIR}/${ZIP_ALIAS}"
echo "               ${OUTPUT_DIR}/${OTA_ALIAS}"
echo "  SHA-256 (Full): ${CHECKSUM}"
echo "  SHA-256 (OTA):  ${OTA_CHECKSUM}"
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
        [ -f system/bin/clip.jar ] && cp -f system/bin/clip.jar \"\$MOD_TARGET/system/bin/clip.jar\"
        mkdir -p /data/adb/hyperdl
        [ -f system/bin/clip.jar ] && cp -f system/bin/clip.jar /data/adb/hyperdl/clip.jar
        [ -f system/bin/yt-dlp ] && cp -f system/bin/yt-dlp \"\$MOD_TARGET/system/bin/yt-dlp\"
        cp -f webroot/index.html \"\$MOD_TARGET/webroot/index.html\"

        rm -rf \"\$MOD_TARGET/runtime\"
        mkdir -p \"\$MOD_TARGET/runtime\"
        cp -rf runtime/* \"\$MOD_TARGET/runtime/\"

        chmod 755 \"\$MOD_TARGET/system/bin/\"*
        chmod 644 \"\$MOD_TARGET/system/bin/clip.jar\" 2>/dev/null || true
        chmod 755 \"\$MOD_TARGET/runtime/bin/\"* 2>/dev/null || true
        chmod 755 \"\$MOD_TARGET/service.sh\" \"\$MOD_TARGET/uninstall.sh\"
        chmod 644 \"\$MOD_TARGET/module.prop\" \"\$MOD_TARGET/webroot/index.html\"
        chmod 0777 /storage/emulated/0/Download/HyperDL 2>/dev/null || true
        chmod 0777 /data/adb/hyperdl 2>/dev/null || true
        chcon -R u:object_r:system_file:s0 \"\$MOD_TARGET\" 2>/dev/null || true

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

if [ "$RELEASE" = "true" ]; then
    echo "=========================================="
    echo "  Publishing release to itswill00/HyperDL-Release"
    echo "=========================================="

    if ! command -v gh >/dev/null 2>&1; then
        echo "error: gh (GitHub CLI) is not installed"
        exit 1
    fi

    REL_REPO="itswill00/HyperDL-Release"
    REL_TMP="${PROJECT_DIR}/releases/.tmp_release"
    rm -rf "$REL_TMP"
    mkdir -p "$REL_TMP"

    echo "cloning public release repository..."
    git clone --depth 1 "https://github.com/${REL_REPO}.git" "$REL_TMP"

    echo "updating release metadata..."
    cp -f "${PROJECT_DIR}/update.json" "$REL_TMP/update.json"

    cat <<EOF > "$REL_TMP/README.md"
# HyperDL Releases & OTA Distribution

Official public release channel and Over-The-Air (OTA) hot-patch distribution for **HyperDL**.

## Latest Release: ${VERSION} (b${VERSION_CODE})

- **Standalone Package (Full Module)**: [\`${ZIP_ALIAS}\`](https://github.com/${REL_REPO}/releases/download/${VERSION}/${ZIP_ALIAS}) (~${ZIP_SIZE})
  - Flashable in Magisk, KernelSU, or APatch.
  - Bundles isolated Bionic Python 3.14 runtime and hardware-accelerated FFmpeg.

- **Lightweight OTA Hot-Patch**: [\`${OTA_ALIAS}\`](https://github.com/${REL_REPO}/releases/download/${VERSION}/${OTA_ALIAS}) (~${OTA_SIZE})
  - Fast in-app update via HyperDL WebUI (~250 KB).
  - Updates logic bundle, native bridge, clipboard daemon, and WebUI without rebooting.

## OTA Metadata Endpoint
- JSON: \`https://raw.githubusercontent.com/${REL_REPO}/main/update.json\`
EOF

    (
        cd "$REL_TMP"
        git config user.name "itswill00"
        git config user.email "itswill00@users.noreply.github.com"
        git add update.json README.md
        git commit -m "release: update metadata and links for ${VERSION} (b${VERSION_CODE})" || true
        git push origin main
    )
    rm -rf "$REL_TMP"

    echo "uploading release assets to GitHub (${VERSION})..."
    gh release delete "${VERSION}" --repo "$REL_REPO" -y 2>/dev/null || true
    gh release create "${VERSION}" \
        "$STAGING_DIR/$ZIP_ALIAS" \
        "$STAGING_DIR/$OTA_ALIAS" \
        --repo "$REL_REPO" \
        --title "HyperDL ${VERSION}" \
        --notes "HyperDL ${VERSION} (b${VERSION_CODE}) release with lightweight OTA hot-patch."

    echo "Release published: https://github.com/${REL_REPO}/releases/tag/${VERSION}"
fi
