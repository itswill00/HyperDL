#!/usr/bin/env python3
import sys
import re
import os
import json

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def parse_args():
    bump_type = "patch"
    custom_ver = None
    notes = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("patch", "minor", "major"):
            bump_type = arg
        elif arg == "--notes" and i + 1 < len(args):
            notes = args[i + 1]
            i += 1
        elif arg.startswith("v") and "." in arg:
            custom_ver = arg
        elif "." in arg and not arg.startswith("-"):
            custom_ver = f"v{arg}"
        i += 1
    return bump_type, custom_ver, notes

def calculate_version(curr_ver, curr_code, bump_type, custom_ver):
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)$", curr_ver)
    if not m:
        raise ValueError(f"Invalid current version format: {curr_ver}")
    
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))

    if custom_ver:
        cm = re.match(r"^v?(\d+)\.(\d+)\.(\d+)$", custom_ver)
        if not cm:
            raise ValueError(f"Invalid custom version format: {custom_ver}")
        n_major, n_minor, n_patch = int(cm.group(1)), int(cm.group(2)), int(cm.group(3))
    else:
        if bump_type == "major":
            n_major, n_minor, n_patch = major + 1, 0, 0
        elif bump_type == "minor":
            n_major, n_minor, n_patch = major, minor + 1, 0
        else:  # patch
            n_major, n_minor, n_patch = major, minor, patch + 1

    new_ver = f"v{n_major}.{n_minor}.{n_patch}"
    new_ver_clean = f"{n_major}.{n_minor}.{n_patch}"
    new_code = (n_major * 10000) + (n_minor * 1000) + (n_patch * 10)
    return new_ver, new_ver_clean, new_code

def update_file(path, pattern, replacement):
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    new_content = re.sub(pattern, replacement, content, flags=re.M)
    if new_content != content:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    return False

def main():
    bump_type, custom_ver, notes = parse_args()
    prop_path = os.path.join(PROJECT_DIR, "module.prop")
    
    if not os.path.exists(prop_path):
        print(f"error: {prop_path} not found")
        sys.exit(1)

    with open(prop_path, "r", encoding="utf-8") as f:
        prop_content = f.read()

    vm = re.search(r"^version=(.+)$", prop_content, re.MULTILINE)
    vcm = re.search(r"^versionCode=(\d+)$", prop_content, re.MULTILINE)

    if not vm or not vcm:
        print("error: version or versionCode missing in module.prop")
        sys.exit(1)

    curr_ver = vm.group(1).strip()
    curr_code = int(vcm.group(1).strip())

    new_ver, new_ver_clean, new_code = calculate_version(curr_ver, curr_code, bump_type, custom_ver)

    print(f"==================================================")
    print(f"  HyperDL Version Calculation")
    print(f"==================================================")
    print(f"  Current: {curr_ver} (code: {curr_code})")
    print(f"  Target:  {new_ver} (code: {new_code}) [{bump_type.upper()}]")
    print(f"--------------------------------------------------")

    # 1. module.prop
    update_file(prop_path, r"^version=.+$", f"version={new_ver}")
    update_file(prop_path, r"^versionCode=\d+$", f"versionCode={new_code}")
    print(f"  [x] module.prop -> {new_ver} ({new_code})")

    # 2. update.json
    update_json_path = os.path.join(PROJECT_DIR, "update.json")
    if os.path.exists(update_json_path):
        with open(update_json_path, "r", encoding="utf-8") as f:
            try:
                uj = json.load(f)
            except Exception:
                uj = {}
        uj["version"] = new_ver
        uj["versionCode"] = new_code
        uj["zipUrl"] = f"https://github.com/itswill00/HyperDL-Release/releases/download/{new_ver}/HyperDL-{new_ver}.zip"
        if notes:
            uj["notes"] = notes
        with open(update_json_path, "w", encoding="utf-8") as f:
            json.dump(uj, f, indent=2)
            f.write("\n")
        print(f"  [x] update.json -> {new_ver} ({new_code})")

    # 3. webui/package.json
    pkg_path = os.path.join(PROJECT_DIR, "webui", "package.json")
    update_file(pkg_path, r'"version":\s*"[^"]+"', f'"version": "{new_ver_clean}"')
    print(f"  [x] webui/package.json -> {new_ver_clean}")

    # 4. webui/src/App.vue
    vue_path = os.path.join(PROJECT_DIR, "webui", "src", "App.vue")
    update_file(vue_path, r"\{\{\s*sysInfo\.version\s*\|\|\s*'v[^']+'\s*\}\}", f"{{{{ sysInfo.version || '{new_ver}' }}}}")
    print(f"  [x] webui/src/App.vue -> {new_ver}")

    # 5. src/main.c
    main_c_path = os.path.join(PROJECT_DIR, "src", "main.c")
    update_file(main_c_path, r'char mod_version\[\d+\] = "v[^"]+";', f'char mod_version[32] = "{new_ver}";')
    print(f"  [x] src/main.c -> {new_ver}")

    # 6. README.md
    readme_path = os.path.join(PROJECT_DIR, "README.md")
    update_file(readme_path, r'Release-v[\d\.]+-black\.svg', f'Release-{new_ver}-black.svg')
    update_file(readme_path, r'HyperDL-v[\d\.]+\.zip', f'HyperDL-{new_ver}.zip')
    update_file(readme_path, r'HyperDL-v[\d\.]+-b\d+-Standalone\.zip', f'HyperDL-{new_ver}-b{new_code}-Standalone.zip')
    print(f"  [x] README.md -> {new_ver}")

    print(f"==================================================")
    print(f"All 6 files synchronized successfully to {new_ver} ({new_code})")

if __name__ == "__main__":
    main()
