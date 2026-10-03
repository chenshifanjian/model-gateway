#!/usr/bin/env bash
# 跨平台打包脚本（Linux / macOS）。Windows 请用: pyinstaller 网关客户端.spec
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"

"$PYTHON" -m pip install -q -r requirements.txt pyinstaller
"$PYTHON" -m PyInstaller --noconfirm --clean 网关客户端.spec

echo
echo "打包完成，产物在 dist/:"
ls -lh dist/ | grep -v '\.md$' || true
