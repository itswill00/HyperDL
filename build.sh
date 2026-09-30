#!/system/bin/sh
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

DEPLOY=false
CLEAN=false
RELEASE=false
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
        -h|--help)
            echo "Usage: ./build.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -b, --bump [type]  Bump version (patch|minor|major, default: patch)"
            echo "  -d, --deploy       Deploy to /data/adb/modules/hyperdl"
            echo "  -c, --clean        Clean build artifacts"
            echo "  -r, --release      Tag and publish to the source repo"
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

if [ "$CLEAN" = "true" ]; then
    echo "cleaning build artifacts..."
    rm -rf webui/dist webroot/index.html bin/libhyperdl.so bin/hyperdl.bundle releases
    find engine tests scripts webui/src -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
    find engine tests scripts webui/src -name "*.pyc" -delete 2>/dev/null || true
    exit 0
fi

# 1. Incremental Component Builds
mkdir -p bin

# Python bundle (source of truth: _impl.py)
if [ ! -f "bin/hyperdl.bundle" ] || [ "engine/downloader.py" -nt "bin/hyperdl.bundle" ] || [ "engine/_impl.py" -nt "bin/hyperdl.bundle" ]; then
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
    curl -fsSL "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp" -o bin/yt-dlp
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

        if [ -d runtime ]; then
            echo '   syncing runtime...'
            cp -rf runtime \"\$TARGET/\"
        fi

        chmod 755 \"\$TARGET/bin/\"* \"\$TARGET/service.sh\" \"\$TARGET/uninstall.sh\"
        chmod 644 \"\$TARGET/module.prop\" \"\$TARGET/webroot/index.html\"
        chmod 0777 /storage/emulated/0/Download/HyperDL 2>/dev/null || true
        chmod 700 /data/adb/hyperdl 2>/dev/null || true
        [ -f /data/adb/hyperdl/cookies.txt ] && chmod 600 /data/adb/hyperdl/cookies.txt 2>/dev/null || true
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

# 3. Packaging Mode
OUT_DIR="${PROJECT_DIR}/releases"
mkdir -p "$OUT_DIR"
ZIP_NAME="HyperDL-${VERSION}.zip"
rm -f "$OUT_DIR"/HyperDL-*.zip 2>/dev/null || true
echo "-> packaging module (${ZIP_NAME})..."
python3 scripts/package_zip.py "$OUT_DIR/$ZIP_NAME" \
    module.prop customize.sh service.sh uninstall.sh bin runtime webroot
echo "build finished: $OUT_DIR/$ZIP_NAME"

# 4. Release to GitHub (source repo is the single release venue)
if [ "$RELEASE" = "true" ]; then
    if ! command -v gh >/dev/null 2>&1; then echo "error: gh not installed"; exit 1; fi
    REL_REPO="itswill00/HyperDL"
    NOTES_FILE="${PROJECT_DIR}/release_notes/${VERSION}.md"
    if [ ! -f "$NOTES_FILE" ]; then
        echo "error: release notes missing at $NOTES_FILE"
        echo "       write the HyperDL-standard description first (see AGENTS.md)"
        exit 1
    fi

    if [ -n "$(git status --porcelain)" ]; then
        echo "error: working tree is dirty, commit before releasing"
        exit 1
    fi
    git fetch origin >/dev/null 2>&1 || true
    if [ -n "$(git log --oneline "origin/main..HEAD")" ]; then
        echo "error: unpushed commits, push to origin/main before releasing"
        exit 1
    fi
    if git rev-parse "${VERSION}" >/dev/null 2>&1; then
        echo "error: tag ${VERSION} already exists locally"
        exit 1
    fi

    git tag -a "${VERSION}" -m "HyperDL ${VERSION} (b${VERSION_CODE})"
    git push origin "refs/tags/${VERSION}"
    gh release delete "${VERSION}" --repo "$REL_REPO" -y 2>/dev/null || true
    gh release create "${VERSION}" "$OUT_DIR/$ZIP_NAME" --repo "$REL_REPO" \
        --title "HyperDL ${VERSION}" --notes-file "$NOTES_FILE"
    echo "Release published: https://github.com/${REL_REPO}/releases/tag/${VERSION}"
fi
