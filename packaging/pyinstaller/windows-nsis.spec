# -*- mode: python ; coding: utf-8 -*-
# CI / NSIS: GUI and CLI one-file exes under dist/windows-nsis/.
import os

from PyInstaller.config import CONF

_SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
_ROOT = os.path.normpath(os.path.join(_SPEC_DIR, "..", ".."))
_distpath = os.path.join(_ROOT, "dist", "windows-nsis")
CONF["distpath"] = _distpath
_icon = os.path.join(_ROOT, "icon.ico")
_version = os.path.join(_ROOT, "file_version_info.txt")
_gui_main = os.path.join(_ROOT, "src", "main_gui.py")
_cli_main = os.path.join(_ROOT, "src", "main_cli.py")
_src = os.path.join(_ROOT, "src")


def build_analysis(entrypoint):
    """Create a PyInstaller analysis for one mini-agent entrypoint."""
    return Analysis(
        [entrypoint],
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


gui_a = build_analysis(_gui_main)
gui_pyz = PYZ(gui_a.pure)

cli_a = build_analysis(_cli_main)
cli_pyz = PYZ(cli_a.pure)

gui_exe = EXE(
    gui_pyz,
    gui_a.scripts,
    gui_a.binaries,
    gui_a.datas,
    [],
    name="mini-agent",
    distpath=_distpath,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
    version=_version,
)

cli_exe = EXE(
    cli_pyz,
    cli_a.scripts,
    cli_a.binaries,
    cli_a.datas,
    [],
    name="mini-agent-cli",
    distpath=_distpath,
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
