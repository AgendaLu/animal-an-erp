"""PyInstaller 進入腳本 — 委派給 web.desktop:main。"""
import sys
from pathlib import Path

# 開發模式直接執行本檔時需要專案根目錄;打包後由 PyInstaller 打進 bundle,無害。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from web.desktop import main  # noqa: E402

if __name__ == "__main__":
    main()
