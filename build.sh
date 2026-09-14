#!/system/bin/sh
set -e

PROJECT_DIR="/data/data/com.termux/files/home/HyperDL_Module"
cd "$PROJECT_DIR"

DEPLOY=false
CLEAN=false
RELEASE=false
POST_ONLY=false
BUMP=false
BUMP_ARG=""

while [ $# -gt 0 ]; do
    case "$1" in
        -b|--bump)
            BUMP=true
            shift
            if [ $# -gt 0 ]; then
                case "$1" in
                    patch|minor|major|v*|[0-9]*)
                        BUMP_ARG="$1"
                        shift
                        ;;
                esac
            fi
            ;;
        -d|--deploy)  DEPLOY=true; shift ;;
        -r|--release) RELEASE=true; shift ;;
        -c|--clean)   CLEAN=true; shift ;;
        -p|--post)    POST_ONLY=true; shift ;;
        -h|--help)
            echo "Usage: ./build.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -b, --bump [type]  Precise version bump (patch|minor|major, default: patch) across all 6 files"
            echo "  -d, --deploy       Fast deploy to /data/adb/modules/hyperdl (~0.5s, no zip)"
            echo "  -p, --post         Print and copy Telegram post to clipboard"
            echo "  -c, --clean        Clean build artifacts"
            echo "  -r, --release      Publish release to GitHub"
            exit 0
            ;;
        *)
            echo "error: unrecognized option '$1' (use -h for help)"
            exit 1
            ;;
    esac
done

if [ "$BUMP" = "true" ]; then
    python3 scripts/bump_version.py $BUMP_ARG
fi

if [ ! -f "module.prop" ]; then
    echo "error: module.prop not found in $PROJECT_DIR"
    exit 1
fi

VERSION=$(grep '^version=' module.prop | cut -d= -f2)
VERSION_CODE=$(grep '^versionCode=' module.prop | cut -d= -f2)

print_post() {
    local headline body post_text
    headline=$(git log -1 --pretty=format:"%s")
    body=$(git log -1 --pretty=format:"%b" | sed '/^$/d; s/^/* /')

    post_text=$(cat <<EOF
HyperDL Build
#b${VERSION_CODE}

${headline}
${body:+
$body}

Commit: https://github.com/itswill00/HyperDL/commit/$(git rev-parse --short HEAD)
Release: https://github.com/itswill00/HyperDL-Release/releases/tag/${VERSION}
EOF
)
    echo ""
    echo "================ Telegram Post ================"
    echo "$post_text"
    echo "==============================================="
    echo ""
}

if [ "$POST_ONLY" = "true" ]; then
    print_post
    exit 0
fi

if [ "$CLEAN" = "true" ]; then
    echo "cleaning build artifacts..."
    rm -rf webui/dist webroot/index.html bin/libhyperdl.so bin/hyperdl.bundle releases
    exit 0
fi

# 1. Incremental Component Builds
mkdir -p bin

# Engine bundle
if [ ! -f "bin/hyperdl.bundle" ] || [ "engine/downloader.py" -nt "bin/hyperdl.bundle" ]; then
    echo "-> bundling python extractor..."
    python3 scripts/bundle_engine.py
fi

# C native bridge
if [ ! -f "bin/libhyperdl.so" ] || [ "src/main.c" -nt "bin/libhyperdl.so" ] || [ "src/embedded_engine.h" -nt "bin/libhyperdl.so" ]; then
    echo "-> compiling c native bridge..."
    clang -O3 -Wall -Wextra src/main.c -o bin/libhyperdl.so
    strip --strip-unneeded bin/libhyperdl.so
    chmod 755 bin/libhyperdl.so
fi

# WebUI
if [ ! -f "webroot/index.html" ] || [ -n "$(find webui/src -newer webroot/index.html 2>/dev/null)" ]; then
    echo "-> building webui..."
    (cd webui && [ -d node_modules ] || npm install --no-audit --no-fund)
    (cd webui && node ./node_modules/vite/bin/vite.js build)
    mkdir -p webroot
    cp -f webui/dist/index.html webroot/index.html
fi

# yt-dlp check
if [ ! -f "bin/yt-dlp" ]; then
    echo "-> fetching yt-dlp..."
    curl -sL "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp" -o bin/yt-dlp
    chmod 755 bin/yt-dlp
    [ -f "scripts/optimize_ytdlp.py" ] && python3 scripts/optimize_ytdlp.py bin/yt-dlp
fi

# Sitecustomize
if [ -f "src/sitecustomize.py" ] && [ -d "runtime/lib/python3.14" ]; then
    cp -f src/sitecustomize.py runtime/lib/python3.14/sitecustomize.py
fi

# 2. Fast Deploy Mode
if [ "$DEPLOY" = "true" ]; then
    echo "-> deploying to /data/adb/modules/hyperdl..."
    su -c "
        TARGET=\"/data/adb/modules/hyperdl\"
        [ -f /data/local/tmp/hyperdl_clip.pid ] && kill -9 \$(cat /data/local/tmp/hyperdl_clip.pid 2>/dev/null) 2>/dev/null || true
        [ -f /data/local/tmp/hyperdl.pid ] && kill -9 \$(cat /data/local/tmp/hyperdl.pid 2>/dev/null) 2>/dev/null || true
        rm -f /data/local/tmp/hyperdl*.pid

        mkdir -p \"\$TARGET/bin\" \"\$TARGET/webroot\" /data/adb/hyperdl /storage/emulated/0/Download/HyperDL
        cp -f module.prop customize.sh service.sh uninstall.sh \"\$TARGET/\"
        cp -f bin/* \"\$TARGET/bin/\"
        [ -f bin/clip.jar ] && cp -f bin/clip.jar /data/adb/hyperdl/clip.jar
        cp -f webroot/index.html \"\$TARGET/webroot/index.html\"

        if [ ! -d \"\$TARGET/runtime\" ] || [ ! -f \"\$TARGET/runtime/bin/python3\" ]; then
            echo '   installing runtime...'
            cp -rf runtime \"\$TARGET/\"
        fi

        chmod 755 \"\$TARGET/bin/\"* \"\$TARGET/service.sh\" \"\$TARGET/uninstall.sh\"
        chmod 644 \"\$TARGET/module.prop\" \"\$TARGET/webroot/index.html\"
        chmod 0777 /storage/emulated/0/Download/HyperDL /data/adb/hyperdl 2>/dev/null || true
        chcon -R u:object_r:system_file:s0 \"\$TARGET\" 2>/dev/null || true

        for mgr_bin in /data/adb/ap/bin /data/adb/ksu/bin /data/adb/modules/bin; do
            if [ -d \"\$mgr_bin\" ]; then
                ln -sf \"\$TARGET/bin/libhyperdl.so\" \"\$mgr_bin/hyperdl\" 2>/dev/null || true
            fi
        done

        if [ -f /data/adb/hyperdl/autodl.enabled ]; then
            sh \"\$TARGET/bin/hyperdl_daemon\" start >/dev/null 2>&1 &
        fi
    "
    echo "deploy complete: module updated in <1s"
    exit 0
fi

# 3. Packaging Mode (One Universal Standalone Zip)
OUT_DIR="${PROJECT_DIR}/releases"
mkdir -p "$OUT_DIR"

ZIP_NAME="HyperDL-${VERSION}.zip"
rm -f "$OUT_DIR"/HyperDL-*.zip 2>/dev/null || true

echo "-> packaging module (${ZIP_NAME})..."
zip -qr9 "$OUT_DIR/$ZIP_NAME" \
    module.prop \
    customize.sh \
    service.sh \
    uninstall.sh \
    bin \
    runtime \
    webroot \
    -x "*.git*" "webui/*" "webroot/*.map" "*.pyc" "*__pycache__*"

# Mirror directly to Download folder for easy Telegram file selection
PUB_DIR="/storage/emulated/0/Download/HyperDL_Releases"
su -c "mkdir -p '$PUB_DIR' && rm -f '$PUB_DIR'/HyperDL-*.zip && cp -f '$OUT_DIR'/*.zip '$PUB_DIR/' && chmod 666 '$PUB_DIR'/*" 2>/dev/null || true
am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file://$PUB_DIR/$ZIP_NAME" >/dev/null 2>&1 || true

echo "build finished: package ready in $PUB_DIR/$ZIP_NAME"
print_post

# 4. Release to GitHub
if [ "$RELEASE" = "true" ]; then
    echo "=========================================="
    echo "  publishing to itswill00/HyperDL-Release"
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
# HyperDL Releases & Distribution

Official public release channel for **HyperDL**.

## Latest Release: ${VERSION} (b${VERSION_CODE})

- **Download Module**: [\`${ZIP_NAME}\`](https://github.com/${REL_REPO}/releases/download/${VERSION}/${ZIP_NAME})
EOF

    (
        cd "$REL_TMP"
        git config user.name "itswill00"
        git config user.email "itswill00@users.noreply.github.com"
        git add update.json README.md
        git commit -m "release: ${VERSION} (b${VERSION_CODE})" || true
        git push origin main
    )
    rm -rf "$REL_TMP"

    echo "uploading release asset to GitHub (${VERSION})..."
    gh release delete "${VERSION}" --repo "$REL_REPO" -y 2>/dev/null || true
    gh release create "${VERSION}" \
        "$OUT_DIR/$ZIP_NAME" \
        --repo "$REL_REPO" \
        --title "HyperDL ${VERSION}" \
        --notes "HyperDL ${VERSION} (b${VERSION_CODE}) release"

    echo "Release published: https://github.com/${REL_REPO}/releases/tag/${VERSION}"
fi
