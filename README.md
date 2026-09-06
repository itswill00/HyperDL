# HyperDL

A minimalist media downloader module for rooted Android devices (KernelSU, APatch, and Magisk).

## Overview

HyperDL provides a fast, ad-free local downloader for social media content, accessible directly through your root manager's WebUI. It runs locally on your device with no third-party tracking, subscriptions, or intrusive redirects.

## Features

- **Multi-Platform Support**: Direct downloading for TikTok (watermark-free video, audio, and photo albums), Instagram (reels and posts), X/Twitter, and YouTube.
- **Monochrome WebUI**: Clean, lightweight single-page interface matching modern Material Design 3 and KernelSU design guidelines.
- **Root Bridge Integration**: Seamless communication with the underlying Android system via KernelSU and APatch native shell bridges.
- **Background Clipboard Monitoring**: Optional automated download when supported media links are copied to the system clipboard.
- **Direct Storage Access**: Automatically saves downloads to `/storage/emulated/0/Download/HyperDL` without storage permission prompts or SAF restrictions.

## Structure

```
HyperDL_Module/
├── build.sh                 # Minimal build and packaging script
├── module.prop              # Module metadata
├── customize.sh             # Installation script
├── service.sh               # Boot service script
├── uninstall.sh             # Cleanup script
├── engine/
│   ├── downloader.py        # Core media resolution and download logic
│   ├── bridge.sh            # Shell interface between WebUI and system
│   └── clipboard_daemon.sh  # Background clipboard monitoring daemon
├── webroot/
│   └── index.html           # Inlined single-file WebUI distribution
└── webui/
    ├── src/
    │   ├── App.vue          # Main view and layout
    │   ├── assets/main.css  # Monochrome design tokens and styles
    │   └── helpers/shell.js # KernelSU / APatch execution bridge
    └── vite.config.js       # Single-file bundle configuration
```

## Building

To build the flashable zip package:

```sh
./build.sh
```

To build and deploy directly to a connected live device:

```sh
./build.sh --deploy
```

The output zip file will be placed in `/storage/emulated/0/Download/HyperDL-v1.0.0.zip`.

## License

GPL-3.0 © @itswill00
