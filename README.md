<h1 align="center">HyperDL</h1>

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL_v3-black.svg" alt="License">
  <img src="https://img.shields.io/badge/Root-KernelSU%20%7C%20APatch%20%7C%20Magisk-black.svg" alt="Root">
  <img src="https://img.shields.io/badge/Architecture-ARM64-black.svg" alt="Architecture">
  <img src="https://img.shields.io/badge/UI-Material_3_Monochrome-black.svg" alt="UI">
  <img src="https://img.shields.io/badge/Release-v1.3.45-black.svg" alt="Release">
</p>

<p align="center">
  <i>On-device media downloader for rooted Android. No cloud, no accounts, no Termux needed at runtime.</i><br>
  <i>Maintained by @noticesa</i>
</p>

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Cookies (Optional)](#cookies-optional)
- [Audio Format](#audio-format)
- [Private Vault](#private-vault)
- [Clipboard Auto-Download](#clipboard-auto-download)
- [Platform Support](#platform-support)
- [Architecture](#architecture)
- [Directory Layout](#directory-layout)
- [Build System](#build-system)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Community & Support](#community--support)
- [License](#license)

---

## Features

- **Fully on-device** — links resolve and download locally; nothing passes through third-party proxies.
- **Zero runtime dependencies** — ships its own Python 3 stack, `ffmpeg`, and media pipeline. Termux is only used to build, never to run.
- **Material 3 monochrome WebUI** — single-file Vue app served straight from your root manager.
- **12+ platforms** — TikTok, YouTube, Instagram, Facebook, Pinterest, Reddit, X, Bluesky, Threads, Bilibili, Streamable, plus direct file and HLS links.
- **Resolution picker** — YouTube video from 144p up to 4K, audio up to FLAC.
- **Smart resume** — interrupted downloads continue where they stopped; stale resume state that triggers HTTP 416 is detected and restarted from scratch automatically.
- **Cookie-aware extraction** — optional Netscape cookies unlock age-gated and login-walled media, with clear errors that tell expired sessions apart from missing ones.
- **Clipboard watcher** — optional background daemon grabs supported links the moment they are copied.
- **Private vault** — matching links land in a hidden, gallery-excluded folder.

> [!TIP]
> Everything below runs as root on the device itself. There is no server component and no account to create.

---

## Requirements

| Requirement | Details |
| :--- | :--- |
| Device | Android 10+, ARM64 |
| Root | KernelSU, APatch, or Magisk (plus a manager that can open module WebUI, e.g. MMRL) |
| Network | Active internet connection while downloading |
| Build only | Termux or ARM64 Linux with `clang`, `zip`, `node` + `npm`, `python3` |

> [!NOTE]
> Root is required because HyperDL installs as a system module and reads/writes outside the app sandbox.

---

## Installation

### Method 1: Flash the release zip (recommended)

1. Download `HyperDL-v1.3.45.zip` from the [Releases page](https://github.com/itswill00/HyperDL/releases).
2. Open your root manager (**KernelSU**, **APatch**, or **Magisk**).
3. Go to **Modules** > **Install from storage** and pick the zip.
4. Open the module WebUI from your root manager — no reboot needed.

### Method 2: Live local deploy (developers)

```sh
./build.sh --deploy
```

This rebuilds the native bridge, rebundles the extractor and WebUI, syncs the runtime, and updates `/data/adb/modules/hyperdl` in place.

---

## Usage

1. Paste a supported link into the **Downloader** tab.
2. Pick a format (video resolution or audio).
3. Hit download and watch live progress in the console.
4. Finished files land in `/storage/emulated/0/Download/HyperDL/`, grouped by platform and uploader.

| WebUI Tab | What it does |
| :--- | :--- |
| **Downloader** | Paste links, pick formats, track progress, manage the download list |
| **Cookies** | View and manage the optional cookie session used for gated media |
| **Terminal** | Run commands and inspect live output on-device |

> [!TIP]
> Copying a supported link while the clipboard daemon is active fills the input for you — no manual paste needed.

---

## Cookies (Optional)

Cookies are **never required** for public media. They only matter for age-gated posts, private content, or platforms throttling anonymous access.

- Cookie file: `/data/adb/hyperdl/cookies.txt` (Netscape HTTP format).
- Manage it from the **Cookies** tab — no file manager round-trips.
- Errors distinguish a **missing** session ("try without cookies") from an **expired** one ("refresh your cookies") per platform.

```sh
# Example: export from a desktop browser profile, then place at:
/data/adb/hyperdl/cookies.txt
```

> [!WARNING]
> A cookie file is a live login session. Never share it publicly or commit it to git.

---

## Audio Format

Default audio output is MP3. To change it, write one word to the config file:

| Value | Output |
| :--- | :--- |
| `mp3` | MP3 (default) |
| `flac` | Lossless FLAC |
| `m4a` | M4A |
| `opus` | Opus |

```sh
echo "flac" > /data/adb/hyperdl/audio_format.conf
```

---

## Private Vault

The vault keeps selected downloads out of the gallery. When enabled, matching links are routed to a hidden folder carrying a `.nomedia` marker:

```text
Download/HyperDL/.vault/Stream/
```

- Toggle: WebUI action backed by `/data/adb/hyperdl/vault.enabled`.
- Domain list: `/data/adb/hyperdl/vault_domains.conf` (safe to extend with your own entries — updates only append missing lines, never overwrite yours).

<details>
<summary>How the routing works</summary>

The extractor checks every URL against `vault_domains.conf`. On a match, the output directory switches to `.vault/Stream` and a `.nomedia` file is ensured at `.vault/` so gallery apps skip the whole tree. The clipboard watcher and DNS bypass read the same list, so behavior stays consistent everywhere.

</details>

---

## Clipboard Auto-Download

A lightweight daemon watches the system clipboard for supported links:

```sh
# Start / stop (flag file controls auto-start on boot)
touch /data/adb/hyperdl/autodl.enabled   # enable
rm /data/adb/hyperdl/autodl.enabled      # disable
sh /data/adb/modules/hyperdl/bin/hyperdl_daemon start
sh /data/adb/modules/hyperdl/bin/hyperdl_daemon stop
```

---

## Platform Support

| Platform | Format Options | Extraction Strategy | Fallback Provider |
| :--- | :--- | :--- | :--- |
| **TikTok** | Video (no watermark), Audio (FLAC HD), Photos | TikWM API | SSR HTML scrape / yt-dlp |
| **YouTube** | Video (resolution picker 4K–144p), Audio (FLAC HD) | Android-client yt-dlp | Embedded stream resolver |
| **Instagram** | Reels, Posts, Carousel media | GraphQL API / JSON embed | yt-dlp (cookie-aware) |
| **Facebook** | Reels, Public videos, Watch clips | Direct progressive stream scrape | yt-dlp extractor |
| **Pinterest** | Videos, Pins, Story media, Original images | PinResource unauth JSON API | yt-dlp extractor |
| **Reddit** | Videos (MP4), Galleries, Single posts | Reddit JSON API / old Reddit | yt-dlp extractor |
| **X (Twitter)** | Videos, Photos, Animated GIFs | GraphQL API / FxTwitter / VxTwitter | yt-dlp extractor |
| **Bluesky** | Videos (MP4), Photos, Galleries | AT Protocol public XRPC | yt-dlp extractor |
| **Threads** | Videos (MP4), Photos | OpenGraph embedded scrape | yt-dlp extractor |
| **Bilibili** | Videos, Audio | Web API / scraper | yt-dlp DASH remuxing |
| **Streamable** | Videos (MP4) | Streamable JSON API | yt-dlp extractor |
| **Direct URLs** | MP4, WEBM, MP3, M3U8 streams | Chunked direct streamer | Python urllib pipeline |

---

## Architecture

```text
                +-------------------------------+
                |    Root Manager / WebUI       |
                |    (KernelSU / APatch / MMRL) |
                +---------------+---------------+
                                |
                        ksu.exec() / IPC
                                |
                                v
                +---------------+---------------+
                |     Native C Bridge           |
                | (bin/libhyperdl.so, C99 -O3)  |
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

1. **Native C bridge (`bin/libhyperdl.so`)**
   - C99 ELF binary compiled with full optimization (`-O3`).
   - Queries Android MediaStore via `/system/lib64/libsqlite.so` in under 1ms — replacing legacy `content query` JVM calls that take up to 1.4s.
   - Ships a self-healing embedded fallback (compressed Base64 extractor payload in `.rodata`) for recovery when bundles are missing or corrupted.
   - Non-blocking background session manager with POSIX detachment and atomic PID tracking.

2. **Standalone ARM64 Python runtime (`runtime/`)**
   - Self-contained Python 3 stack targeting Android Bionic libc.
   - Standard library packed as stripped bytecode in `runtime/lib/python314.zip` for near-instant imports.
   - Bundled shared libraries (`libpython3.14.so`, `libcrypto.so.3`, `libssl.so.3`, `libandroid-support.so`) plus a local CA bundle.

3. **Core extractor package (`bin/hyperdl.bundle`)**
   - Zipapp of precompiled `.pyc` modules — zero cold-start compile latency.
   - Chunked HTTP streaming with resume support and transient-network recovery.

4. **Standalone yt-dlp (`bin/yt-dlp`)**
   - Fallback and primary YouTube pipeline as a bytecode-optimized archive (cold start cut from ~11s to ~1.5s on ARM64).
   - Android client emulation to avoid throttling and client-validation failures.

5. **Material 3 monochrome WebUI (`webroot/index.html`)**
   - Vue 3 + Vite app bundled into one standalone HTML file.
   - Platform badges, Netscape cookie manager, live console, and native player intents.

6. **Clipboard daemon (`bin/hyperdl_daemon`)**
   - Watches Android clipboard events, validates links by regex, and hands them to the extractor hands-free.

---

## Directory Layout

```text
HyperDL/
├── build.sh                 # Build, package, deploy, and release script
├── module.prop              # Magisk / KernelSU module metadata
├── customize.sh             # On-device installation script
├── service.sh               # Late-start service initialization
├── uninstall.sh             # Module removal and cache purge
├── update.json              # Release-feed metadata (served from this repo)
├── AGENTS.md                # Contributor invariants — read before changing code
├── bin/
│   ├── libhyperdl.so        # Native 64-bit ELF bridge (built from src/main.c)
│   ├── hyperdl.bundle       # Compiled bytecode extractor (built from engine/)
│   ├── hyperdl_daemon       # Clipboard listener daemon
│   ├── clip.jar             # Clipboard helper
│   └── yt-dlp               # Bytecode-optimized standalone yt-dlp
├── engine/
│   ├── downloader.py        # Public entry point (re-exports _impl)
│   └── _impl.py             # Extraction logic and stream pipelines
├── runtime/                 # Standalone ARM64 Python 3 + ffmpeg (git-ignored build output)
├── scripts/
│   ├── bundle_engine.py     # Compiles the extractor into .pyc bundle and C header
│   ├── bundle_runtime.py    # Assembles the standalone ARM64 Python runtime
│   ├── optimize_ytdlp.py    # Converts yt-dlp into a pure bytecode archive
│   └── bump_version.py      # Version bump helper used by build.sh --bump
├── src/
│   ├── main.c               # Native C bridge source
│   └── sitecustomize.py     # On-device Python bootstrap
├── release_notes/
│   └── vX.Y.Z.md            # GitHub Release description per version
├── tests/
│   └── test_engine.py       # Unit tests (run with unittest)
├── webroot/
│   └── index.html           # Inlined single-file WebUI (built from webui/)
├── webui/
│   ├── src/
│   │   ├── App.vue          # Multi-tab view (Downloader, Cookies, Terminal)
│   │   ├── assets/main.css  # Material 3 monochrome theme
│   │   ├── components/      # Vector icons and platform chips
│   │   └── helpers/shell.js # KernelSU / APatch execution bridge
│   ├── package.json
│   └── vite.config.js       # Single-file build configuration
└── releases/                # Release zips (internal build output)
```

---

## Build System

### Command Line Options

| Option | Action |
| :--- | :--- |
| `-b, --bump [type]` | Bump version (`patch` \| `minor` \| `major`, default: `patch`) |
| `-d, --deploy` | Deploy to `/data/adb/modules/hyperdl` for live testing |
| `-c, --clean` | Remove build artifacts |
| `-r, --release` | Tag and publish the Full Zip to this repo |
| `-h, --help` | Show help |

### Typical Workflows

```sh
./build.sh --deploy          # rebuild + push live to the device
./build.sh --clean           # wipe dist, binaries, and caches
./build.sh                   # package releases/HyperDL-vX.Y.Z.zip
./build.sh --release         # package, tag, and publish to this repo
```

### Build Targets

Packaging outputs a single Full Zip to internal `releases/`:

- `HyperDL-v1.3.45.zip` — canonical release package with the full embedded runtime.

> [!IMPORTANT]
> Every release is a **Full Zip**. There is no OTA/delta mechanism — never create or expect `HyperDL-OTA-*.zip` files.

### Running Tests

```sh
python3 -m unittest discover -s tests -v
```

---

## Troubleshooting

<details>
<summary><strong>Download fails with <code>HTTP Error 416</code></strong></summary>

Fixed in v1.3.45: YouTube downloads no longer force resume against short-lived signed URLs, and any range error is automatically retried from the start after purging stale partials. Update the module and try again.

</details>

<details>
<summary><strong><code>403 Forbidden</code> or "login required"</strong></summary>

Public links should work without cookies. For gated content, add a Netscape cookie file via the **Cookies** tab. If cookies are already set, the session likely expired — re-export them from your browser.

</details>

<details>
<summary><strong>First YouTube download is slow to start</strong></summary>

Normal. The bundled yt-dlp pays a one-time cold-start cost (~1.5s) while resolving the stream. Subsequent downloads in the same session start faster.

</details>

<details>
<summary><strong>WebUI opens blank</strong></summary>

Open it through your root manager's module WebUI action (MMRL recommended). Deploy fresh with `./build.sh --deploy` if `webroot/index.html` is missing or outdated.

</details>

<details>
<summary><strong>Clipboard links are not captured</strong></summary>

Make sure the daemon flag exists and the daemon is running:

```sh
touch /data/adb/hyperdl/autodl.enabled
sh /data/adb/modules/hyperdl/bin/hyperdl_daemon start
```

</details>

---

## FAQ

<details>
<summary><strong>Do I need Termux installed to use HyperDL?</strong></summary>

No. Termux is only the build environment. The module carries its own Python runtime and tools.

</details>

<details>
<summary><strong>Where do my downloads go?</strong></summary>

`/storage/emulated/0/Download/HyperDL/`, organized by platform and uploader. Vault matches go to the hidden `.vault/Stream/` subfolder instead.

</details>

<details>
<summary><strong>Does HyperDL upload my links anywhere?</strong></summary>

No. Resolution and downloading happen on the device. The only network traffic is the direct request to the platform hosting the media.

</details>

<details>
<summary><strong>How do updates work?</strong></summary>

Full-Zip releases ship from this repository's [Releases page](https://github.com/itswill00/HyperDL/releases) feed (`update.json`). Flash the new zip over the old one — no data wipe needed. Older versions (up to v1.3.42) stay archived in the former HyperDL-Release repo.

</details>

---

## Community & Support

- **Telegram**: [@noticesa](https://t.me/noticesa) for updates, direct assistance, and discussions.
- **Support development**: if HyperDL saves you time, consider supporting via [SociaBuzz Tribe](https://sociabuzz.com/noticesa/tribe).

---

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

Developed and maintained by [@noticesa](https://t.me/noticesa).
