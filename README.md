<h1 align="center">HyperDL</h1>

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL_v3-black.svg" alt="License">
  <img src="https://img.shields.io/badge/Root-KernelSU%20%7C%20APatch%20%7C%20Magisk-black.svg" alt="Root">
  <img src="https://img.shields.io/badge/Architecture-ARM64-black.svg" alt="Architecture">
  <img src="https://img.shields.io/badge/UI-Material_3_Monochrome-black.svg" alt="UI">
  <img src="https://img.shields.io/badge/Release-v1.3.11-black.svg" alt="Release">
</p>

<p align="center">
  <i>Autonomous, zero-dependency local media extraction module for rooted Android devices.</i><br>
  <i>Maintained by @noticesa</i>
</p>

---

## Overview

HyperDL is an autonomous, on-device media downloader root module designed for KernelSU, APatch, and Magisk environments. Unlike cloud-based download utilities that route media queries through third-party proxies, log request metadata, or impose bandwidth throttling, HyperDL executes entirely on the local device hardware.

The module packages an isolated ARM64 native runtime, compiled Python bytecode extractors, and an embedded single-page WebUI to provide instantaneous media resolution and direct filesystem storage without relying on external system packages or Termux environments.

---

## Architecture

```
                       +-------------------------------+
                       |    Root Manager / WebUI       |
                       |    (KernelSU / APatch / MMRL) |
                       +---------------+---------------+
                                       |
                           ksu.exec() / IPC
                                       |
                                       v
                       +---------------+---------------+
                       |   Native C Bridge Binary      |
                       |   (system/bin/libhyperdl.so)  |
                       +-------+---------------+-------+
                               |               |
              Direct SQLite DL |               | Dynamic Spawning
              MediaStore Index |               |
                               v               v
               +---------------+---+   +---------------+---------------+
               | /system/lib64/    |   | Standalone Python 3 Runtime   |
               | libsqlite.so      |   | (runtime/bin/python3)         |
               +-------------------+   +---------------+---------------+
                                                       |
                                        +--------------+--------------+
                                        |                             |
                                        v                             v
                        +---------------+-------+     +---------------+-------+
                        | Core Extractor        |     | Standalone yt-dlp     |
                        | (hyperdl.bundle .pyc) |     | (.pyc zipapp archive) |
                        +-----------------------+     +-----------------------+
                                        |                             |
                                        +--------------+--------------+
                                                       |
                                          Streaming / Chunked I/O
                                                       |
                                                       v
                                      +-------------------------------+
                                      | /storage/emulated/0/          |
                                      | Download/HyperDL/             |
                                      +-------------------------------+
```

### Core Components

1. **Native C Bridge (`system/bin/libhyperdl.so`)**:
   - Compiled C99 ELF binary with full compiler optimization (`-O3`).
   - Direct integration with `/system/lib64/libsqlite.so` to query Android MediaStore databases in under 1ms, replacing legacy `content query` JVM invocations that require up to 1.4s.
   - Self-healing embedded fallback: compressed Base64 Python extraction payload compiled into `.rodata` for recovery if external bundles are missing or corrupted.
   - Non-blocking background session manager with POSIX process detachment and atomic PID tracking.

2. **Standalone ARM64 Python Runtime (`runtime/`)**:
   - Self-contained Python 3 environment targeting Android Bionic libc.
   - Standard library packed into a deflated, bytecode-compiled archive (`runtime/lib/python314.zip`) for near-instant import resolution.
   - Stripped shared dependencies (`libpython3.14.so`, `libcrypto.so.3`, `libssl.so.3`, `libandroid-support.so`) with local CA certificate bundle.
   - Zero dependence on Termux, system Python, or external package managers.

3. **Core Extractor Package (`system/bin/hyperdl.bundle`)**:
   - Packaged zipapp containing precompiled Python bytecode (`.pyc`).
   - Zero cold-start compilation latency.
   - Custom HTTP chunk streaming pipeline with resume capabilities and transient network recovery.

4. **Standalone yt-dlp Utility (`system/bin/yt-dlp`)**:
   - Dedicated fallback and YouTube extraction pipeline.
   - Bytecode-compiled archive reducing cold startup from 11.0s to 1.5s on ARM64.
   - Android client emulation (`youtube:player_client=android`) to eliminate playback throttling and solve client validation challenges.

5. **Material 3 Monochrome WebUI (`webroot/index.html`)**:
   - Built with Vue 3 and Vite, bundled into a single standalone HTML artifact.
   - Integrated platform detection badges with visual feedback.
   - Netscape HTTP cookie manager for authenticated and age-gated media downloads.
   - Live execution console with status tracking and native media player intent triggers.

6. **Clipboard Monitoring Service (`system/bin/hyperdl_daemon`)**:
   - Background daemon utilizing Android system clipboard events via `cmd clipboard get`.
   - Automatic regex-based link validation and hands-free media capture.

---

## Platform Support Matrix

| Platform | Format Options | Extraction Strategy | Fallback Provider |
| :--- | :--- | :--- | :--- |
| **TikTok** | Video (No Watermark), Audio (FLAC HD), Photos | TikWM API | SSR HTML Scrape / yt-dlp |
| **YouTube** | Video (Resolution Picker 4K-144p), Audio (FLAC HD) | Android Client Bytecode yt-dlp | Embedded Stream Resolver |
| **Instagram** | Reels, Posts, Carousel Media | GraphQL API / JSON Embed | yt-dlp (Cookie-Aware) |
| **Facebook** | Reels, Public Videos, Watch Clips | Direct Progressive Stream Scrape | yt-dlp Extractor |
| **Pinterest** | Videos, Pins, Story Media, Original Images | PinResource Unauth JSON API | yt-dlp Extractor |
| **Reddit** | Videos (MP4), Image Galleries, Single Posts | Reddit JSON API / Old Reddit | yt-dlp Extractor |
| **X (Twitter)** | Videos, Photos, Animated GIFs | GraphQL API / FxTwitter / VxTwitter | yt-dlp Extractor |
| **Direct URLs** | MP4, WEBM, MP3, M3U8 Streams | Chunked Direct Streamer | Python urllib Pipeline |

---

## Directory Layout

```
HyperDL/
├── build.sh                 # Zero-dependency build, package, and deploy script
├── module.prop              # Magisk and KernelSU module metadata
├── customize.sh             # On-device module installation script
├── service.sh               # Late-start service initialization script
├── uninstall.sh             # Module removal and cache purge script
├── scripts/
│   ├── bundle_engine.py     # Compiles extractor into .pyc bundle and C header
│   ├── bundle_runtime.py    # Bundles standalone ARM64 Python runtime
│   └── optimize_ytdlp.py    # Optimizes yt-dlp into pure bytecode archive
├── src/
│   └── main.c               # High-performance native C bridge
├── system/bin/
│   ├── libhyperdl.so        # Native 64-bit ELF bridge binary
│   ├── hyperdl.bundle       # Compiled bytecode Python extractor
│   ├── hyperdl_daemon       # Background clipboard listener daemon
│   └── yt-dlp               # Bytecode-optimized standalone yt-dlp
├── engine/
│   └── downloader.py        # Core extraction algorithms and stream pipelines
├── webroot/
│   └── index.html           # Inlined single-file WebUI distribution
└── webui/
    ├── src/
    │   ├── App.vue          # Multi-tab view (Downloader, Cookies, Terminal)
    │   ├── assets/main.css  # Material Design 3 monochrome theme
    │   ├── components/      # Vector icons and platform chips
    │   └── helpers/shell.js # KernelSU / APatch execution bridge
    ├── package.json
    └── vite.config.js       # Vite single-file configuration
```

---

## Installation

### Method 1: Flashing via Root Manager (Recommended)

1. Download the latest release package (`HyperDL-v1.2.1.zip`) from the Releases page.
2. Open your root manager (**KernelSU**, **APatch**, or **Magisk**).
3. Navigate to **Modules** > **Install from storage**.
4. Select the zip file and confirm installation.
5. Launch the module WebUI directly from your root manager.

### Method 2: Live Local Deployment

For local development or testing directly on the device:

```sh
./build.sh --deploy
```

This compiles the native C binary, packages the WebUI, syncs the standalone runtime, and updates `/data/adb/modules/hyperdl` live without requiring a reboot.

---

## Build System

### Requirements

The build pipeline runs entirely in Termux on Android or any Linux environment with ARM64 cross-compilers:

- `clang`
- `zip`
- `node` and `npm`
- `python3`

### Command Line Options

```
Usage: ./build.sh [OPTIONS]

Options:
  -d, --deploy       Deploy module directly to /data/adb/modules/hyperdl
  -o, --output DIR   Specify custom output directory for zip releases
  -c, --clean        Clean build caches before build
  -h, --help         Show this help information
```

### Build Targets

By default, compilation outputs to `/sdcard/HyperDL_Releases/`:

- `HyperDL-v1.3.11-b13110-Standalone.zip`: Canonical release package with full embedded runtime.
- `HyperDL-v1.3.11.zip`: Standard version alias.
- `HyperDL-latest.zip`: Latest build alias for update distribution.

Upon completion, `build.sh` issues an Android MediaStore broadcast (`MEDIA_SCANNER_SCAN_FILE`) to make the package immediately visible to system file managers.

---

## Community & Support

- **Telegram**: Join [@noticesa](https://t.me/noticesa) for updates, direct assistance, and discussions.
- **Support Development**: If you find HyperDL helpful, support continued development through [SociaBuzz Tribe](https://sociabuzz.com/noticesa/tribe).

---

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

Developed and maintained by [@noticesa](https://t.me/noticesa).
