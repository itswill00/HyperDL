#!/usr/bin/env python3
import os
import sys
import zipfile
import tempfile
import compileall

def optimize_ytdlp(ytdlp_path):
    if not os.path.isfile(ytdlp_path):
        return False

    try:
        with zipfile.ZipFile(ytdlp_path, "r") as z:
            names = z.namelist()
            if any(n.endswith(".pyc") for n in names) and not any(n.endswith(".py") for n in names):
                return True
    except Exception:
        return False

    print(f"optimizing {ytdlp_path} to bytecode (.pyc)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(ytdlp_path, "r") as z:
            z.extractall(tmpdir)

        compileall.compile_dir(tmpdir, force=True, quiet=1, legacy=True)

        for root, dirs, files in os.walk(tmpdir):
            for f in files:
                if f.endswith(".py"):
                    os.remove(os.path.join(root, f))

        tmp_out = ytdlp_path + ".optimized"
        with open(tmp_out, "wb") as f:
            f.write(b"#!/usr/bin/env python3\n")
            with zipfile.ZipFile(f, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                for root, dirs, files in os.walk(tmpdir):
                    for f in files:
                        full = os.path.join(root, f)
                        rel = os.path.relpath(full, tmpdir)
                        z.write(full, rel)

        os.chmod(tmp_out, 0o755)
        os.replace(tmp_out, ytdlp_path)

    print(f"optimized {ytdlp_path} ({os.path.getsize(ytdlp_path)} bytes)")
    return True

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else ("bin/yt-dlp" if os.path.exists("bin/yt-dlp") else "system/bin/yt-dlp")
    optimize_ytdlp(target)
