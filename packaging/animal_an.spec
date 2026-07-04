# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Animal-AN ERP 桌面打包(onedir)。

規格 §7:Windows 與 Mac 各自平台打包(不可交叉編譯);
執行檔與 .db 分離 — 資料庫存於執行檔同層 data/,更新時整包換新、保留 data/。

Build:
    macOS/Linux: scripts/build_desktop.sh
    Windows:     scripts\\build_desktop.bat
產物: dist/animal-an-erp/
"""
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# uvicorn 以字串動態載入 loop/protocol 實作,靜態分析抓不到,全部收進來
hiddenimports = collect_submodules("uvicorn")

a = Analysis(
    ["launch.py"],
    pathex=[".."],
    binaries=[],
    datas=[("../web/static", "web/static")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "tkinter"],  # 桌面 GUI 走瀏覽器,不打包 Qt
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="animal-an-erp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # 保留 console:使用者看得到「系統執行中」,關窗即關機
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="animal-an-erp",
)
