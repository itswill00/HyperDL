# HyperDL Project Guidelines

## Core Invariants
1. **Android 10+ WebView Safety**:
   - Never use `window.confirm()`, `window.alert()`, or `window.prompt()`. Always use custom in-app Vue modals.
   - Do NOT wrap full-screen modal overlays in Vue `<transition>`. Older WebViews can drop `transitionend` events and freeze touch input.
   - Never use `backdrop-filter: blur(...)` in WebUI overlays; use solid semi-transparent colors (e.g. `rgba(0, 0, 0, 0.75)`).
   - Use optimistic UI updates for list deletions and mutations.
   - Never invoke `pauseDownload()` on `window.onoffline`. Android WebViews emit false offline events during network handovers.

2. **Native C Bridge Performance**:
   - Never run blocking `system("am ...")` calls in `src/main.c`. Always execute system scans and background notifications asynchronously with `(...) &`.
   - Batch file operations whenever possible to prevent multiple bridge invocations.
   - Verify process liveness using `/proc/<pid>` and `errno == EPERM`. Never mutate active tasks to paused if PID is alive.

3. **Python Extractor**:
   - Keep all standard library imports (`subprocess`, `shutil`, `html as pyhtml`) at top-level module scope in `engine/downloader.py`.
   - Status writes to `STATUS_FILE` and `ACTIVE_TASK_FILE` must be atomic (`.tmp` + `os.replace`).
   - Video requests must never fall back to static image/thumbnail cover files (`og:image`).

4. **Tone & Branding**:
   - Avoid robotic words. Specifically, do NOT use the word "engine" in user-facing texts, logs, or UI.
   - Keep UI text in English and chat communication in casual Indonesian.

5. **Version Bump & Release Invariant**:
   - Every fix or update MUST bump version and versionCode across `module.prop`, `update.json`, `webui/package.json`, `webui/src/App.vue`, `src/main.c`, and `README.md`.
   - Always run Vite build and copy `webui/dist/index.html` to `webroot/index.html` after modifying `webui/`.
   - Run `./build.sh --deploy` to test and deploy to live `/data/adb/modules/hyperdl`.
   - Release zips are stored strictly in `/sdcard/HyperDL_Releases/`.
