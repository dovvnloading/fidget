# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for Fidget.

Built one-dir rather than one-file on purpose: the app re-launches its own
executable to run the controller, and a one-file build would unpack the whole
bundle a second time for that child process. One-dir also starts faster and
keeps the signed executable a stable, inspectable artefact.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

REPO = Path(SPECPATH).parent

# pywebview loads its WebView2 interop assemblies from webview/lib at runtime;
# they are data, not imports, so analysis alone never finds them.
webview_datas, webview_binaries, webview_hidden = collect_all("webview")

# uvicorn resolves its loop and protocol implementations by string at startup.
uvicorn_hidden = collect_submodules("uvicorn")

datas = [
    # The built React interface, served by the controller.
    (str(REPO / "frontend" / "dist"), "frontend/dist"),
    # Window, taskbar and Alt-Tab icon.
    (str(REPO / "fidget" / "assets"), "fidget/assets"),
    # Executed by ACE-Step's *separate* interpreter, so it has to stay a real
    # .py file on disk rather than being frozen into the bundle.
    (str(REPO / "fidget" / "worker" / "ace_worker.py"), "fidget/worker"),
    *webview_datas,
]

hiddenimports = [
    *webview_hidden,
    *uvicorn_hidden,
    "clr_loader",
    "pythonnet",
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "backend.server",
    "backend.desktop",
]

a = Analysis(
    [str(REPO / "fidget" / "fidget.py")],
    pathex=[str(REPO), str(REPO / "fidget")],
    binaries=webview_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "PIL", "pytest"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Fidget",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX-packed executables trip antivirus heuristics.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(REPO / "fidget" / "assets" / "fidget.ico"),
    version=str(REPO / "packaging" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Fidget",
)
