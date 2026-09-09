# -*- mode: python ; coding: utf-8 -*-

import os

from PyInstaller.utils.hooks import collect_all

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

packages = [
    "av",
    "ctranslate2",
    "faster_whisper",
    "huggingface_hub",
    "numpy",
    "tokenizers",
    "websockets",
]

datas = []
binaries = []
hiddenimports = ["_webrtcvad", "pyaudiowpatch", "soundcard", "webrtcvad"]
for package in packages:
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

analysis = Analysis(
    [os.path.join(SPECPATH, "backend_entry.py")],
    pathex=[os.path.join(PROJECT_ROOT, "backend")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[os.path.join(SPECPATH, "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="wpmchecker-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
