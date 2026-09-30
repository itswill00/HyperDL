# HyperDL Project Guidelines

All project content — code, comments, docs, UI text, and this file — must be written in full English.
Chat communication with the user stays casual Indonesian, but nothing committed to the repository
is allowed to contain Indonesian.

## Core Invariants
1. **Android 10+ WebView Safety**:
   - Never use `window.confirm()`, `window.alert()`, or `window.prompt()`. Always use custom in-app Vue modals.
   - Do NOT wrap full-screen modal overlays in Vue `<transition>`. Older WebViews can drop `transitionend` events and freeze touch input.
   - Never use `backdrop-filter: blur(...)` in WebUI overlays; use solid semi-transparent colors (e.g. `rgba(0, 0, 0, 0.75)`).
   - Use optimistic UI updates for list deletions and mutations.
   - Never invoke `pauseDownload()` on `window.onoffline`. Android WebViews emit false offline events during network handovers.
   - Flex containers with text inputs (e.g. search/URL input bars) MUST have `min-width: 0; width: 100%;` on input elements and `overflow: hidden;` on wrappers to prevent buttons (like Paste) from overflowing off-screen on compact mobile viewports.

2. **Native C Bridge Performance**:
   - Never run blocking `system("am ...")` calls in `src/main.c`. Always execute system scans and background notifications asynchronously with `(...) &`.
   - Batch file operations whenever possible to prevent multiple bridge invocations.
   - Verify process liveness using `/proc/<pid>` and `errno == EPERM`. Never mutate active tasks to paused if PID is alive.

3. **Python Extractor**:
   - Keep all standard library imports (`subprocess`, `shutil`, `html as pyhtml`) at top-level module scope in `engine/_impl.py`.
   - Status writes to `STATUS_FILE` and `ACTIVE_TASK_FILE` must be atomic (`.tmp` + `os.replace`).
   - Video requests must never fall back to static image/thumbnail cover files (`og:image`).
   - Always use `(d.get("key") or {})` when traversing dynamic social media JSON to prevent `NoneType` crashes on `null` fields.
   - For HLS `.m3u8` streams, remux with FFmpeg using `-f mp4` and `.tmp.mp4` temporary files; do not pass concurrent chunk flags to yt-dlp on HLS.
   - Guard against signed-URL resume drift: if a download fails with a range error (HTTP 416), purge the stale partial and retry once from the start rather than forcing resume.
   - Resolution probes are cached in `/data/adb/hyperdl/cache/probe_cache.json` (TTL 6h, capped at 200 entries, `0600`). The cache MUST only hold the format/height list, never signed stream URLs, so downloads always re-resolve fresh URLs.
   - Any cache read must fail open on a corrupt or unreadable file, and writes must be atomic (`.tmp` + `os.replace`).

4. **Tone & Branding**:
   - Avoid robotic words. Specifically, do NOT use the word "engine" in user-facing texts, logs, or UI.
   - Keep all UI text, release notes, and documentation in English.

5. **Version Bump & Release Invariant**:
   - Never bump version on your own. Only bump when the user explicitly asks for it.
   - When asked to bump, update version and versionCode across `module.prop`, `update.json`, `webui/package.json`, `webui/src/App.vue`, `src/main.c`, and `README.md`.
   - `scripts/bump_version.py` is the single supported way to bump. Run it and verify the six files stayed in sync.
   - Always run Vite build and copy `webui/dist/index.html` to `webroot/index.html` after modifying `webui/`.
   - Run `./build.sh --deploy` to test and deploy to live `/data/adb/modules/hyperdl`.
   - Release zips live strictly in internal `releases/` (`HyperDL-vX.Y.Z.zip`). Never mirror to `/sdcard`.
   - **Full-Zip Only**: every change (extractor `engine/`, WebUI `webui/`, bridge `src/main.c`) is ALWAYS released as a **Full Zip** (`HyperDL-vX.Y.Z.zip`). OTA is gone for good; never produce `HyperDL-OTA-*.zip` under any circumstance.

6. **Strict Release Gate (Mandatory User Confirmation)**:
   - Creating a GitHub release tag (`gh release create`), pushing a release tag, or updating public release feed metadata is FORBIDDEN until all of the following hold:
     1. Every change has been tested locally and deployed to the device (`./build.sh --deploy`).
     2. The user has been explicitly asked to try the new feature or fix on their own device or WebUI.
     3. The user has given firm confirmation that everything is stable, safe, and bug-free.
   - ONLY after an explicit green light from the user may the agent run `./build.sh --release` or publish any release.

7. **Single-Venue Releases (Source Repo = Release Repo)**:
   - Effective v1.3.45, `itswill00/HyperDL` is the ONLY release venue. Source code, git tags, GitHub Releases, flashable binaries, and `update.json` metadata all live in this repository.
   - `./build.sh --release` creates the tag and GitHub Release on the `origin` remote (`itswill00/HyperDL`). There is no separate release repo anymore.
   - `update.json` and `module.prop:updateJson` MUST point at the source repo raw URL (`https://raw.githubusercontent.com/itswill00/HyperDL/main/update.json`) and the source repo asset URL (`https://github.com/itswill00/HyperDL/releases/download/...`).
   - The old `itswill00/HyperDL-Release` repo is a historical archive (releases up to v1.3.42). Publishing, tagging, or pushing anything there is FORBIDDEN.
   - `--release` no longer clones or pushes metadata to any other repo. It packages the local zip, then runs `gh release create` against the source repo. It refuses to publish when the working tree is dirty, when unpushed commits exist, when the tag already exists, or when `release_notes/vX.Y.Z.md` is missing.

8. **Release Notes Standard (HyperDL Tag Description)**:
   - Notes live in `release_notes/vX.Y.Z.md` and are versioned alongside the code. Write them in **full GitHub-flavored Markdown**, because that is what renders on the release page.
   - Structure, in order:
     1. `# HyperDL vX.Y.Z` as the only H1.
     2. A blockquote metadata line carrying versionCode, release type, and the previous version (e.g. `> **b13450** · full-zip release · changes since \`v1.3.42\``).
     3. A one-paragraph summary of what this release delivers, written for someone deciding whether to update.
     4. A `---` rule, then a `## Highlights` table (Area | What changed) for at-a-glance scanning.
     5. One `##` section per category, using `##`/`###` headings, `-` bullets, inline code for errors, file names, and commands, and `**bold**` for the fix summary at the start of each bullet. Each bullet stays one to two lines, uses the active voice, and MUST explain WHY for fixes.
     6. `---`, then an install section as a two-column table (Method | Steps).
     7. A changelog link, then the required closing line: `Update from your root manager or flash \`HyperDL-vX.Y.Z.zip\`.`
   - Rules:
     - Never dump a per-commit changelog, never leave TODO or placeholder text, and keep technical notes understandable to a first-time user.
     - Wrap error messages, paths, commands, and filenames in inline code.
     - Use a `---` horizontal rule to separate major blocks; do not rely on blank lines alone.
     - Exactly one H1 per release description.
   - The one-sentence summary from the intro paragraph is reused verbatim as the `notes` field in `update.json`.
   - Every release also ships a Telegram post in `release_notes/vX.Y.Z.tg.md`, written in Telegram Markdown (`*bold*`, triple-backtick pre block). Fixed skeleton:
     `*HyperDL vX.Y.Z* (code)` → `*Changelog:*` + pre block of `•` bullets (one line per change, terse, no prose) → `*Notes:*` (Android 10+ arm64, flash via KernelSU/APatch/Magisk) → `*Links:*` (channel + support).

9. **Vault (18+) Privacy Invariant**:
   - Isolated routing: `get_target_directory()` + `download_with_ytdlp_direct()` send URLs matching `vault_domains.conf` to `$OUTDIR/.vault/Stream` with `.nomedia` (hidden from Gallery).
   - Single source of truth: `src/main.c` `b64_domains` holds 20 domains (12 base + 8 new: beeg.com, spankbang.com, tube8.com, youjizz.com, 4tube.com, nuvid.com, sunporno.com, tnaflix.com) — all backed by the `bin/yt-dlp` extractor.
   - `cmd_toggle_vault` must merge idempotently: if `vault_domains.conf` already exists, only append lines that are missing (preserve user edits) and never overwrite the whole file.
   - The DoH bypass (`src/sitecustomize.py`) and the clipboard daemon (`bin/hyperdl_daemon`) must read the same `vault_domains.conf` for domain filtering.

10. **Strict Standalone Module Isolation (Zero Termux Runtime Dependency)**:
    - The Magisk / KernelSU / APatch module MUST be 100% standalone and isolated inside `/data/adb/modules/hyperdl/` and `/system/`.
    - Termux is strictly the local build and compilation environment; runtime code (`src/main.c`, `engine/`, `bin/hyperdl_daemon`, and `webui/src/helpers/shell.js`) must NEVER reference `/data/data/com.termux/...`.
    - Bundled ELF binaries (`python3`, dynamic extensions `.so`, `ffmpeg.bin`, `ffprobe.bin`) must have relative RUNPATHs (`$ORIGIN/../lib`, `$ORIGIN/../..`) set via `patchelf` during packaging.
    - Python stdlib must be packaged as stripped `.pyc` bytecode inside a single compressed archive (`python314.zip`) without GUI, tests, or unused debug modules.

---

## Communication

- Repository content: **English only**, no exceptions. This includes code comments, commit messages, release notes, docs, and UI strings.
- Chat replies: casual Indonesian, matching how the user writes.
