#!/usr/bin/env bash
# 跨平台打包脚本（Linux / macOS）。Windows 请用: pyinstaller 网关客户端.spec
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"

# PEP 668（Arch/Debian 等系统 Python 禁止裸 pip）：没在 venv 里就自动建/用 .venv
if [ -z "${VIRTUAL_ENV:-}" ]; then
  [ -d .venv ] || "$PYTHON" -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  PYTHON=python
fi

"$PYTHON" -m pip install -q -r requirements.txt pyinstaller
"$PYTHON" -m PyInstaller --noconfirm --clean 网关客户端.spec

echo
echo "打包完成，产物在 dist/:"
ls -lh dist/ | grep -v '\.md$' || true
