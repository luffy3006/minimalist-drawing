#!/usr/bin/env python3
"""
Automated Build & Packaging Script for Minimalist Drawing
Generates:
  1. Standalone compiled Linux binary (dist/minimalist-drawing)
  2. Arch Linux package (dist/minimalist-drawing-1.0.0-1-any.pkg.tar.zst)
  3. Debian package (dist/minimalist-drawing_1.0.0_all.deb)
"""

import os
import sys
import shutil
import subprocess
import tarfile
import tempfile
import time

VERSION = "1.0.0"
PKG_NAME = "minimalist-drawing"
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(REPO_DIR, "dist")
BUILD_DIR = os.path.join(REPO_DIR, "build")


def log(msg: str):
    print(f"\033[1;34m[BUILD]\033[0m {msg}")


def log_success(msg: str):
    print(f"\033[1;32m[SUCCESS]\033[0m {msg}")


def log_err(msg: str):
    print(f"\033[1;31m[ERROR]\033[0m {msg}", file=sys.stderr)


def clean():
    log("Cleaning previous build artifacts...")
    os.makedirs(DIST_DIR, exist_ok=True)


def build_pyinstaller_binary():
    log("Building standalone PyInstaller binary for Linux...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", PKG_NAME,
        "--icon", os.path.join(REPO_DIR, "packaging", "minimalist-drawing-256.png"),
        "--add-data", f"{os.path.join(REPO_DIR, 'packaging', 'minimalist-drawing.png')}:packaging",
        "--add-data", f"{os.path.join(REPO_DIR, 'packaging', 'minimalist-drawing.svg')}:packaging",
        "--add-data", f"{os.path.join(REPO_DIR, 'autocorrect.py')}:.",
        "--clean",
        "--noconfirm",
        os.path.join(REPO_DIR, "main.py")
    ]
    res = subprocess.run(cmd, cwd=REPO_DIR)
    if res.returncode != 0:
        log_err("PyInstaller build failed!")
        return False
    binary_path = os.path.join(DIST_DIR, PKG_NAME)
    if os.path.exists(binary_path):
        os.chmod(binary_path, 0o755)
        size_mb = os.path.getsize(binary_path) / (1024 * 1024)
        log_success(f"Built standalone binary: {binary_path} ({size_mb:.1f} MB)")
        return True
    return False


def build_deb_package():
    log("Building Debian (.deb) package...")
    pkg_dir = tempfile.mkdtemp(prefix="deb_pkg_")
    try:
        debian_binary = os.path.join(pkg_dir, "debian-binary")
        with open(debian_binary, "w") as f:
            f.write("2.0\n")

        # Control archive
        control_dir = os.path.join(pkg_dir, "control_dir")
        os.makedirs(control_dir, exist_ok=True)
        control_content = f"""Package: {PKG_NAME}
Version: {VERSION}
Section: graphics
Priority: optional
Architecture: all
Maintainer: Archit <luffy3006@users.noreply.github.com>
Depends: python3, python3-pyqt6
Homepage: https://github.com/luffy3006/minimalist-drawing
Description: Fast, minimalist infinite canvas drawing and scratchpad application
 Minimalist Drawing is a high-performance infinite canvas drawing application
 built with PyQt6. Designed for fast sketching, note-taking, math, and problem
 solving with smooth Quad-Bezier strokes, instant Clear Screen with undo history,
 and geometric shape auto-correction.
"""
        with open(os.path.join(control_dir, "control"), "w") as f:
            f.write(control_content)

        control_tar = os.path.join(pkg_dir, "control.tar.xz")
        with tarfile.open(control_tar, "w:xz") as tar:
            tar.add(os.path.join(control_dir, "control"), arcname="./control")

        # Data archive
        data_dir = os.path.join(pkg_dir, "data_dir")
        usr_bin = os.path.join(data_dir, "usr", "bin")
        usr_share_app = os.path.join(data_dir, "usr", "share", PKG_NAME)
        usr_desktop = os.path.join(data_dir, "usr", "share", "applications")
        usr_icons_svg = os.path.join(data_dir, "usr", "share", "icons", "hicolor", "scalable", "apps")
        usr_icons_256 = os.path.join(data_dir, "usr", "share", "icons", "hicolor", "256x256", "apps")
        usr_meta = os.path.join(data_dir, "usr", "share", "metainfo")
        usr_doc = os.path.join(data_dir, "usr", "share", "doc", PKG_NAME)

        for d in [usr_bin, usr_share_app, usr_desktop, usr_icons_svg, usr_icons_256, usr_meta, usr_doc]:
            os.makedirs(d, exist_ok=True)

        # Copy source files to /usr/share/minimalist-drawing
        shutil.copy(os.path.join(REPO_DIR, "main.py"), os.path.join(usr_share_app, "main.py"))
        shutil.copy(os.path.join(REPO_DIR, "autocorrect.py"), os.path.join(usr_share_app, "autocorrect.py"))
        os.makedirs(os.path.join(usr_share_app, "packaging"), exist_ok=True)
        shutil.copy(os.path.join(REPO_DIR, "packaging", "minimalist-drawing.png"), os.path.join(usr_share_app, "packaging", "minimalist-drawing.png"))
        shutil.copy(os.path.join(REPO_DIR, "packaging", "minimalist-drawing.svg"), os.path.join(usr_share_app, "packaging", "minimalist-drawing.svg"))

        # Wrapper script in /usr/bin/minimalist-drawing
        launcher_path = os.path.join(usr_bin, PKG_NAME)
        with open(launcher_path, "w") as f:
            f.write(f"""#!/bin/sh
exec python3 /usr/share/{PKG_NAME}/main.py "$@"
""")
        os.chmod(launcher_path, 0o755)

        # Desktop, Icons, Metadata, Doc
        shutil.copy(os.path.join(REPO_DIR, "packaging", "minimalist-drawing.desktop"), os.path.join(usr_desktop, f"{PKG_NAME}.desktop"))
        shutil.copy(os.path.join(REPO_DIR, "packaging", "minimalist-drawing.svg"), os.path.join(usr_icons_svg, f"{PKG_NAME}.svg"))
        shutil.copy(os.path.join(REPO_DIR, "packaging", "minimalist-drawing-256.png"), os.path.join(usr_icons_256, f"{PKG_NAME}.png"))
        shutil.copy(os.path.join(REPO_DIR, "packaging", "io.github.luffy3006.minimalist_drawing.metainfo.xml"), os.path.join(usr_meta, "io.github.luffy3006.minimalist_drawing.metainfo.xml"))
        shutil.copy(os.path.join(REPO_DIR, "LICENSE"), os.path.join(usr_doc, "copyright"))

        data_tar = os.path.join(pkg_dir, "data.tar.xz")
        with tarfile.open(data_tar, "w:xz") as tar:
            for item in os.listdir(data_dir):
                tar.add(os.path.join(data_dir, item), arcname=f"./{item}")

        # Assemble deb with ar
        deb_filename = f"{PKG_NAME}_{VERSION}_all.deb"
        deb_path = os.path.join(DIST_DIR, deb_filename)
        ar_cmd = ["ar", "rc", deb_path, deb_binary := debian_binary, control_tar, data_tar]
        res = subprocess.run(ar_cmd)
        if res.returncode == 0 and os.path.exists(deb_path):
            log_success(f"Built Debian package: {deb_path} ({os.path.getsize(deb_path) / 1024:.1f} KB)")
            return True
        else:
            log_err("Failed assembling deb archive with ar!")
            return False
    finally:
        shutil.rmtree(pkg_dir, ignore_errors=True)


def build_arch_package():
    log("Building Arch Linux (.pkg.tar.zst) package...")
    pkg_dir = tempfile.mkdtemp(prefix="arch_pkg_")
    try:
        root_dir = os.path.join(pkg_dir, "pkgroot")
        usr_bin = os.path.join(root_dir, "usr", "bin")
        usr_share_app = os.path.join(root_dir, "usr", "share", PKG_NAME)
        usr_desktop = os.path.join(root_dir, "usr", "share", "applications")
        usr_icons_svg = os.path.join(root_dir, "usr", "share", "icons", "hicolor", "scalable", "apps")
        usr_icons_256 = os.path.join(root_dir, "usr", "share", "icons", "hicolor", "256x256", "apps")
        usr_meta = os.path.join(root_dir, "usr", "share", "metainfo")
        usr_license = os.path.join(root_dir, "usr", "share", "licenses", PKG_NAME)

        for d in [usr_bin, usr_share_app, usr_desktop, usr_icons_svg, usr_icons_256, usr_meta, usr_license]:
            os.makedirs(d, exist_ok=True)

        shutil.copy(os.path.join(REPO_DIR, "main.py"), os.path.join(usr_share_app, "main.py"))
        shutil.copy(os.path.join(REPO_DIR, "autocorrect.py"), os.path.join(usr_share_app, "autocorrect.py"))
        os.makedirs(os.path.join(usr_share_app, "packaging"), exist_ok=True)
        shutil.copy(os.path.join(REPO_DIR, "packaging", "minimalist-drawing.png"), os.path.join(usr_share_app, "packaging", "minimalist-drawing.png"))
        shutil.copy(os.path.join(REPO_DIR, "packaging", "minimalist-drawing.svg"), os.path.join(usr_share_app, "packaging", "minimalist-drawing.svg"))

        launcher_path = os.path.join(usr_bin, PKG_NAME)
        with open(launcher_path, "w") as f:
            f.write(f"""#!/bin/sh
exec python3 /usr/share/{PKG_NAME}/main.py "$@"
""")
        os.chmod(launcher_path, 0o755)

        shutil.copy(os.path.join(REPO_DIR, "packaging", "minimalist-drawing.desktop"), os.path.join(usr_desktop, f"{PKG_NAME}.desktop"))
        shutil.copy(os.path.join(REPO_DIR, "packaging", "minimalist-drawing.svg"), os.path.join(usr_icons_svg, f"{PKG_NAME}.svg"))
        shutil.copy(os.path.join(REPO_DIR, "packaging", "minimalist-drawing-256.png"), os.path.join(usr_icons_256, f"{PKG_NAME}.png"))
        shutil.copy(os.path.join(REPO_DIR, "packaging", "io.github.luffy3006.minimalist_drawing.metainfo.xml"), os.path.join(usr_meta, "io.github.luffy3006.minimalist_drawing.metainfo.xml"))
        shutil.copy(os.path.join(REPO_DIR, "LICENSE"), os.path.join(usr_license, "LICENSE"))

        # .PKGINFO
        build_date = int(time.time())
        pkginfo_path = os.path.join(root_dir, ".PKGINFO")
        with open(pkginfo_path, "w") as f:
            f.write(f"""pkgname = {PKG_NAME}
pkgver = {VERSION}-1
pkgdesc = Fast, minimalist infinite canvas drawing and scratchpad application
url = https://github.com/luffy3006/minimalist-drawing
builddate = {build_date}
packager = Archit <luffy3006@users.noreply.github.com>
size = 250000
arch = any
license = MIT
depend = python
depend = python-pyqt6
""")

        # Package with tar and zstd
        arch_pkg_name = f"{PKG_NAME}-{VERSION}-1-any.pkg.tar.zst"
        arch_pkg_path = os.path.join(DIST_DIR, arch_pkg_name)
        tar_cmd = ["tar", "-C", root_dir, "-c", ".PKGINFO", "usr"]
        zstd_cmd = ["zstd", "-T0", "-19", "-o", arch_pkg_path]

        p1 = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE)
        p2 = subprocess.Popen(zstd_cmd, stdin=p1.stdout, stdout=subprocess.PIPE)
        p1.stdout.close()
        p2.communicate()

        if p2.returncode == 0 and os.path.exists(arch_pkg_path):
            log_success(f"Built Arch package: {arch_pkg_path} ({os.path.getsize(arch_pkg_path) / 1024:.1f} KB)")
            return True
        else:
            log_err("Failed generating Arch Linux package!")
            return False
    finally:
        shutil.rmtree(pkg_dir, ignore_errors=True)


def main():
    clean()
    success = True
    success &= build_deb_package()
    success &= build_arch_package()
    success &= build_pyinstaller_binary()

    if success:
        log_success("All packages and executables built successfully in dist/:")
        for f in os.listdir(DIST_DIR):
            fpath = os.path.join(DIST_DIR, f)
            size = os.path.getsize(fpath) / (1024 * 1024)
            print(f"  • {f} ({size:.2f} MB)")
    else:
        log_err("One or more builds failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
