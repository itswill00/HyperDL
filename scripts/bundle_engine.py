#!/usr/bin/env python3
import os
import sys
import zlib
import base64
import shutil
import tempfile
import subprocess

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PY = os.path.join(PROJECT_DIR, "engine", "downloader.py")
OUT_BUNDLE = os.path.join(PROJECT_DIR, "system", "bin", "hyperdl.bundle")
OUT_HEADER = os.path.join(PROJECT_DIR, "src", "embedded_engine.h")

def main():
    if not os.path.exists(SRC_PY):
        print(f"error: {SRC_PY} not found", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(OUT_BUNDLE), exist_ok=True)
    os.makedirs(os.path.dirname(OUT_HEADER), exist_ok=True)

    with open(SRC_PY, "rb") as f:
        code = f.read()

    compressed = base64.b64encode(zlib.compress(code, 9)).decode("ascii")
    byte_vals = [f"0x{b:02x}" for b in compressed.encode("ascii")] + ["0x00"]
    chunk_size = 16
    lines = [
        "    " + ", ".join(byte_vals[i : i + chunk_size]) + ","
        for i in range(0, len(byte_vals), chunk_size)
    ]
    array_content = "\n".join(lines)

    header_content = f"""#ifndef EMBEDDED_ENGINE_H
#define EMBEDDED_ENGINE_H

static const char EMBEDDED_ENGINE_B64[] = {{
{array_content}
}};

#endif
"""
    with open(OUT_HEADER, "w") as f:
        f.write(header_content)

    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "__main__.py"), "w") as f:
            f.write("from downloader import main\nif __name__ == '__main__':\n    main()\n")
        
        shutil.copy(SRC_PY, os.path.join(tmpdir, "downloader.py"))
        subprocess.run([sys.executable, "-m", "compileall", "-b", "-q", tmpdir], check=True)
        os.remove(os.path.join(tmpdir, "downloader.py"))

        if os.path.exists(OUT_BUNDLE):
            os.remove(OUT_BUNDLE)
        subprocess.run([sys.executable, "-m", "zipapp", tmpdir, "-c", "-o", OUT_BUNDLE], check=True)
        os.chmod(OUT_BUNDLE, 0o755)

    print(f"Bundled: {os.path.getsize(OUT_BUNDLE)} bytes ({OUT_BUNDLE})")

if __name__ == "__main__":
    main()
