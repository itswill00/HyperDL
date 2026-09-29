#!/usr/bin/env python3
import os
import sys
import zipfile
import tempfile
import sys as _sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
try:
    from engine._impl import _repack_pyc
    if not callable(_repack_pyc):
        _repack_pyc = None
except Exception:
    _repack_pyc = None

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
    tmp_out = ytdlp_path + ".optimized"
    if _repack_pyc:
        _repack_pyc(ytdlp_path, tmp_out)
    else:
        import compileall
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(ytdlp_path, "r") as z:
                z.extractall(tmpdir)
            compileall.compile_dir(tmpdir, force=True, quiet=1, legacy=True)
            for root, dirs, files in os.walk(tmpdir):
                for f in files:
                    if f.endswith(".py"):
                        os.remove(os.path.join(root, f))
            with open(tmp_out, "wb") as f:
                f.write(b"#!/usr/bin/env python3\n")
                with zipfile.ZipFile(f, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                    for root, dirs, files in os.walk(tmpdir):
                        for fi in files:
                            full = os.path.join(root, fi)
                            z.write(full, os.path.relpath(full, tmpdir))
    os.chmod(tmp_out, 0o755)
    os.replace(tmp_out, ytdlp_path)

    print(f"optimized {ytdlp_path} ({os.path.getsize(ytdlp_path)} bytes)")
    return True

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else ("bin/yt-dlp" if os.path.exists("bin/yt-dlp") else "system/bin/yt-dlp")
    optimize_ytdlp(target)
