# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import shutil
import subprocess
from getpass import getpass

# Ensure UPX is found by adding its folder to the PATH
os.environ["PATH"] = r"C:\Program Files\UPX;" + os.environ["PATH"]

# Read the version from version.txt
with open("version.txt", "r") as f:
    version = f.read().strip()

# Define the output directory name
output_dir = f"VIPrestore {version}"
dist_dir_path = os.path.join("dist", output_dir)

# Clean up any existing output directory
if os.path.exists(dist_dir_path):
    shutil.rmtree(dist_dir_path)

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[
        # Include the UI files – add more if needed:
        ("main.ui", "."),
        ("about_dialog.ui", "."),
        ("login_dialog.ui", "."),
        # Include version file and other resources:
        ("version.txt", "."),
        ("logos/*.ico", "logos"),
        ("logos/*.png", "logos"),
        ("logos/*.gif", "logos"),
        ("fonts/*.ttf", "fonts"),
        ("remotesystems.json", "."),
        (r"venv\Lib\site-packages\pyvis\templates", "pyvis/templates"),
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    target_arch="x64",
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

icon_path = os.path.abspath(os.path.join(os.getcwd(), "logos", "viprestore_icon.ico"))

# --- ONE-DIR MODE ---
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=f"VIPrestore {version}",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=icon_path,
    version_info={
        "version": version,
        "company_name": "TV 2",
        "file_description": "VIPrestore Application",
        "internal_name": "VIPrestore",
        "original_filename": f"VIPrestore {version}.exe",
        "product_name": "VIPrestore",
        "file_version": version,
        "product_version": version,
    },
)

app_coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name=f"VIPrestore {version}",
)

# --- Post-build steps ---
# The .exe will be in dist/VIPrestore {version}/VIPrestore {version}.exe
exe_file = os.path.join(dist_dir_path, f"VIPrestore {version}.exe")

# Sign the .exe
cert_password = getpass("Enter certificate password (leave empty to skip signing): ")
if cert_password.strip():
    if os.path.exists(exe_file):
        sign_tool = r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe"
        cert_path = r"C:\Users\Magnus\cert.pfx"
        cmd = [
            sign_tool,
            "sign",
            "/f", cert_path,
            "/p", cert_password,
            "/tr", "http://timestamp.digicert.com",
            "/td", "sha256",
            "/fd", "sha256",
            exe_file
        ]
        print("Signing executable...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("Executable signed successfully.")
        else:
            print("Error signing executable:")
            print(result.stdout)
            print(result.stderr)
    else:
        print(f"Executable not found at: {exe_file}")
else:
    print("Skipping signing of executable.")

# --- Create Inno Setup installer ---
iscc = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if os.path.exists(iscc):
    print("Creating installer with Inno Setup...")
    cmd = [iscc, "inno.iss"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("Installer created successfully.")

        # Sign the installer if we have a certificate password
        installer_path = os.path.join(dist_dir_path, f"VIPrestore-{version}-Setup.exe")
        if cert_password.strip() and os.path.exists(installer_path):
            cmd = [
                sign_tool,
                "sign",
                "/f", cert_path,
                "/p", cert_password,
                "/tr", "http://timestamp.digicert.com",
                "/td", "sha256",
                "/fd", "sha256",
                installer_path
            ]
            print("Signing installer...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print("Installer signed successfully.")
            else:
                print("Error signing installer:")
                print(result.stdout)
                print(result.stderr)
    else:
        print("Error creating installer:")
        print(result.stdout)
        print(result.stderr)
else:
    print(f"Warning: Inno Setup Compiler not found at {iscc}")
