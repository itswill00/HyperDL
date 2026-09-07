#!/usr/bin/env python3
import os
import sys
import glob
import shutil
import zipfile
import subprocess
import tempfile
import compileall

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET_DIR = os.path.join(PROJECT_DIR, "runtime")
TERMUX_USR = "/data/data/com.termux/files/usr"

def main():
    if not os.path.exists(f"{TERMUX_USR}/bin/python3"):
        print("error: Termux python3 not found", file=sys.stderr)
        sys.exit(1)

    print("packaging standalone python runtime...")
    shutil.rmtree(TARGET_DIR, ignore_errors=True)

    bin_dir = os.path.join(TARGET_DIR, "bin")
    lib_dir = os.path.join(TARGET_DIR, "lib")
    dyn_dir = os.path.join(lib_dir, "python3.14", "lib-dynload")

    os.makedirs(bin_dir, exist_ok=True)
    os.makedirs(lib_dir, exist_ok=True)
    os.makedirs(dyn_dir, exist_ok=True)

    shutil.copy(f"{TERMUX_USR}/bin/python3", f"{bin_dir}/python3")
    os.chmod(f"{bin_dir}/python3", 0o755)

    for tool in ["ffmpeg", "ffprobe"]:
        tool_src = f"{TERMUX_USR}/bin/{tool}"
        if os.path.exists(tool_src):
            tool_dst = f"{bin_dir}/{tool}"
            shutil.copy(tool_src, tool_dst)
            os.chmod(tool_dst, 0o755)
            print(f"Bundled {tool} into {tool_dst}")

    core_libs = ["libpython3.14.so", "libandroid-support.so", "libcrypto.so.3", "libssl.so.3"]
    for lib in core_libs:
        src = f"{TERMUX_USR}/lib/{lib}"
        if os.path.exists(src):
            shutil.copy(src, f"{lib_dir}/{lib}")
            os.chmod(f"{lib_dir}/{lib}", 0o755)

    ca_candidates = [
        f"{TERMUX_USR}/etc/tls/cert.pem",
        f"{TERMUX_USR}/etc/ssl/cert.pem",
        "/system/etc/security/cacerts"
    ]
    for ca in ca_candidates:
        if os.path.isfile(ca):
            shutil.copy(ca, f"{lib_dir}/cacert.pem")
            break

    dyn_src = f"{TERMUX_USR}/lib/python3.14/lib-dynload"
    skip_dyn = (
        "_test",
        "_ctypes_test",
        "_xxtest",
        "xx",
        "_curses",
        "_dbm",
        "_gdbm",
        "_remote_debugging",
        "_lsprof",
        "_interp",
    )
    for f in glob.glob(f"{dyn_src}/*.so"):
        base = os.path.basename(f)
        if any(base.startswith(s) for s in skip_dyn):
            continue
        dst = os.path.join(dyn_dir, base)
        shutil.copy(f, dst)
        os.chmod(dst, 0o755)

    zip_path = os.path.join(lib_dir, "python314.zip")
    src_stdlib = f"{TERMUX_USR}/lib/python3.14"
    skip_dirs = {
        "lib-dynload", "site-packages", "test", "tests",
        "tkinter", "idlelib", "turtledemo", "pydoc_data",
        "_pyrepl", "unittest", "ensurepip", "__pycache__"
    }

    with tempfile.TemporaryDirectory() as tmp_stdlib:
        for root, dirs, files in os.walk(src_stdlib):
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith("__")]
            if any(s in root for s in skip_dirs):
                continue
            rel_dir = os.path.relpath(root, src_stdlib)
            dst_dir = os.path.join(tmp_stdlib, rel_dir) if rel_dir != "." else tmp_stdlib
            os.makedirs(dst_dir, exist_ok=True)
            for f in files:
                if f.endswith(".py") and not f.endswith("_test.py") and not f.startswith("test_"):
                    shutil.copy2(os.path.join(root, f), os.path.join(dst_dir, f))

        compileall.compile_dir(tmp_stdlib, force=True, quiet=1, legacy=True)

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for root, dirs, files in os.walk(tmp_stdlib):
                for f in files:
                    if f.endswith(".pyc"):
                        full = os.path.join(root, f)
                        rel = os.path.relpath(full, tmp_stdlib)
                        z.write(full, rel)

    sitecustomize_src = os.path.join(PROJECT_DIR, "src", "sitecustomize.py")
    py_ver_dir = os.path.join(lib_dir, "python3.14")
    if os.path.exists(sitecustomize_src):
        os.makedirs(py_ver_dir, exist_ok=True)
        shutil.copy2(sitecustomize_src, os.path.join(py_ver_dir, "sitecustomize.py"))

    env = {
        "PATH": f"{bin_dir}:/system/bin",
        "LD_LIBRARY_PATH": lib_dir,
        "PYTHONHOME": TARGET_DIR,
        "PYTHONPATH": f"{zip_path}:{dyn_dir}:{py_ver_dir}",
        "SSL_CERT_FILE": f"{lib_dir}/cacert.pem"
    }
    test_cmd = [f"{bin_dir}/python3", "-c", "import ssl, urllib.request, json, hashlib, zlib; print('Runtime verification passed.')"]
    res = subprocess.run(test_cmd, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Runtime self-test failed: {res.stderr}", file=sys.stderr)
        sys.exit(1)

    total_bytes = sum(os.path.getsize(os.path.join(r, f)) for r, d, files in os.walk(TARGET_DIR) for f in files)
    print(f"Standalone Python runtime bundled ({total_bytes / (1024*1024):.1f} MB in {TARGET_DIR})")

if __name__ == "__main__":
    main()
