# -*- mode: python ; coding: utf-8 -*-
# CI: one-file binary at dist/linux/mini-agent.
import os

from PyInstaller.config import CONF

_SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
_ROOT = os.path.normpath(os.path.join(_SPEC_DIR, "..", ".."))
CONF["distpath"] = os.path.join(_ROOT, "dist", "linux")
_main = os.path.join(_ROOT, "src", "main.py")
_src = os.path.join(_ROOT, "src")

a = Analysis(
    [_main],
    pathex=[_src],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="mini-agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
