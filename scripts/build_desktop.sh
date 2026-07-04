#!/usr/bin/env bash
# 打包 macOS/Linux 桌面版 → dist/animal-an-erp/
# 需求:專案 .venv 已建好(pip install -e ".[dev]")
set -euo pipefail
cd "$(dirname "$0")/.."

PY=.venv/bin/python
"$PY" -m pip show pyinstaller >/dev/null 2>&1 || "$PY" -m pip install "pyinstaller>=6.0"

"$PY" -m PyInstaller packaging/animal_an.spec \
    --distpath dist --workpath build/pyinstaller -y

echo
echo "✓ 打包完成: dist/animal-an-erp/"
echo "  啟動: dist/animal-an-erp/animal-an-erp"
echo "  資料庫會建立在 dist/animal-an-erp/data/animal_an.db"
