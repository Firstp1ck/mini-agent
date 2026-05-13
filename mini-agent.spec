# -*- mode: python ; coding: utf-8 -*-
#
# Windows shell icon (Explorer / Desktop):
#   PyInstaller embeds RT_ICON from icon.ico (build log: "Copying icon to EXE"). Copying the .exe to another
#   folder does not remove those bytes — if the icon "reverts" at the new path, Windows is showing a cached
#   or generic shell icon for that path. Fix: F5 in the folder, sign out, run scripts\Clear-WindowsIconCache.ps1,
#   or wait; avoid judging the icon only inside Cursor/VS Code (often a generic .exe glyph).
#   This spec outputs to dist\windows\ and uses icon.ico without 256px PNG-in-ICO to reduce Explorer quirks.
#
#   Network "server" copy: if the icon is wrong only on \\server\share or after SCP/FTP, the usual cause is a
#   corrupted or altered PE (text-mode FTP, wrong line endings, AV rewriting the file). Compare SHA256 and
#   file size local vs remote; use binary-safe transfer (robocopy, scp -O, sftp binary, WinSCP binary). UNC
#   paths also use the client icon cache — try a new filename on the share once.
import os

from PyInstaller.config import CONF

_ROOT = os.path.dirname(os.path.abspath(SPEC))
CONF["distpath"] = os.path.join(_ROOT, "dist", "windows")
_icon = os.path.join(_ROOT, "icon.ico")
_version = os.path.join(_ROOT, "file_version_info.txt")

a = Analysis(
    ["src\\main.py"],
    pathex=["src"],
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
    icon=_icon,
    version=_version,
)
