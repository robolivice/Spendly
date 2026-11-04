import os

from PyInstaller.utils.hooks import collect_all

SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
REPO_DIR = os.path.dirname(SPEC_DIR)
APP_DIR = os.path.join(REPO_DIR, "Spendly")

webview_datas, webview_binaries, webview_hidden = collect_all("webview")

datas = [
    (os.path.join(APP_DIR, "templates"), "templates"),
    (os.path.join(APP_DIR, "static"), "static"),
    (os.path.join(APP_DIR, "assets"), "assets"),
] + webview_datas

hiddenimports = webview_hidden + [
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
]

a = Analysis(
    [os.path.join(APP_DIR, "desktop.py")],
    pathex=[APP_DIR],
    binaries=webview_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "pydoc",
        "test",
        "PyQt5",
        "PyQt6",
        "gi",
        "cefpython3",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Spendly",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(SPEC_DIR, "icon.ico"),
    version=os.path.join(SPEC_DIR, "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Spendly",
)
