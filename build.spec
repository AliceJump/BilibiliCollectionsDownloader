# build.spec — PyInstaller specification for BilibiliCollectionsDownloader
#
# Usage:
#   pip install pyinstaller "pywebview[edgechromium]"
#   pyinstaller build.spec
#
# Output: dist/BiliCollectionDownloader.exe  (Windows)
#         dist/BiliCollectionDownloader      (macOS / Linux)

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import sys

block_cipher = None

# Bundle index.html into the root of the archive
added_files = [
    ("index.html", "."),
]

# hidden_imports for seleniumwire / webdriver-manager
hidden_imports = (
    collect_submodules("webview")
    + collect_submodules("flask")
    + collect_submodules("jinja2")
    + collect_submodules("werkzeug")
    + collect_submodules("seleniumwire")
    + collect_submodules("selenium")
    + [
        "requests",
        "engineio",
        "clr_loader",   # needed by pythonnet / edgechromium on Windows
        "webdriver_manager",
        "webdriver_manager.chrome",
    ]
)

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=added_files + collect_data_files("webview"),
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="BiliCollectionDownloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,        # no black console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="icon.ico",    # uncomment and provide icon.ico to set an app icon
)
