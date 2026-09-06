<h1 align="center">HyperDL</h1>

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL_v3-black.svg" alt="License">
  <img src="https://img.shields.io/badge/Root-KernelSU%20%7C%20APatch%20%7C%20Magisk-black.svg" alt="Root">
  <img src="https://img.shields.io/badge/Architecture-ARM64-black.svg" alt="Architecture">
  <img src="https://img.shields.io/badge/UI-Monochrome%20WebUI-black.svg" alt="UI">
  <img src="https://img.shields.io/badge/Release-v1.0.0-black.svg" alt="Release">
</p>

<p align="center">
  <i>A minimalist, ad-free local media downloader module for rooted Android devices.</i><br>
  <i>Crafted by @itswill00</i>
</p>

---

## Overview

**HyperDL** is a lightweight root module that provides a local, private media downloading utility accessible directly through your root manager (KernelSU, APatch, or MMRL). 

Unlike public downloader services that require subscriptions, show intrusive redirects, or log requests through third-party servers, HyperDL executes directly on your hardware. Downloads are saved directly to your local storage without storage access framework (SAF) overhead or rate limits.

---

## Key Features

- **Multi-Platform Support**: Streamlined resolution for TikTok (watermark-free video, audio, and photo albums), Instagram (reels and posts), X (Twitter), and YouTube.
- **Monochrome WebUI**: Clean, single-page interface built with Vue 3, following modern Material Design 3 and KernelSU design guidelines.
- **Root Bridge Integration**: Direct communication with the Android environment via native KernelSU and APatch shell bridges (`ksu.exec`).
- **Background Clipboard Monitoring**: Optional automated service that captures copied media links in the background and saves them silently.
- **Direct Storage Pipeline**: Saves all media directly to `/storage/emulated/0/Download/HyperDL/` with built-in intent launching to open files in your default player.
- **Zero Third-Party Relays**: Direct client-to-platform fetching without external telemetry or intermediate logging servers.

---

## Repository Structure

```
HyperDL/
├── build.sh                 # Minimal Unix build and deploy script
├── module.prop              # Magisk and KernelSU module metadata
├── customize.sh             # On-device module installer
├── service.sh               # Boot service initialization
├── uninstall.sh             # Cleanup script
├── src/
│   └── main.c               # Native C bridge implementation
├── system/bin/
│   └── libhyperdl.so        # Stripped 64-bit native ELF binary (15 KB)
├── engine/
│   ├── downloader.py        # Core extraction and streaming logic
│   └── clipboard_daemon.sh  # Background clipboard monitoring daemon
├── webroot/
│   └── index.html           # Inlined single-file WebUI distribution
└── webui/
    ├── src/
    │   ├── App.vue          # Multi-tab view (Downloader, Cookies, Console)
    │   ├── assets/main.css  # Monochrome design tokens and styles
    │   ├── components/      # Vector icons and UI elements
    │   └── helpers/shell.js # KernelSU / APatch native bridge
    ├── package.json
    └── vite.config.js       # Single-file build configuration
```

---

## Installation

### Method 1: Flashing Module (Recommended)
1. Download `HyperDL-v1.0.0.zip` from the latest release.
2. Open your root manager (**KernelSU**, **APatch**, or **Magisk**).
3. Navigate to **Modules** &rarr; **Install from storage**.
4. Select the zip file and reboot if prompted, or launch the WebUI directly.

### Method 2: Live Local Deploy
If developing locally in Termux or an ADB root shell:

```sh
./build.sh --deploy
```

The script will compile the WebUI bundle, package the module, and deploy it straight to `/data/adb/modules/hyperdl`.

---

## Building from Source

### Prerequisites
- Node.js (`node`) and `npm`
- `zip` utility
- Python 3 (`python3`)

### Compilation

Clone the repository and run the build script:

```sh
git clone https://github.com/itswill00/HyperDL.git
cd HyperDL
./build.sh
```

The compiled, flashable zip file will be generated at `/storage/emulated/0/Download/HyperDL-v1.0.0.zip`.

---

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

Developed with precision by [@itswill00](https://github.com/itswill00).
