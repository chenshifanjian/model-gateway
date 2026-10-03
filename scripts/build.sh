#!/usr/bin/env bash
# 跨平台打包脚本（Linux / macOS）。Windows 请用: pyinstaller 网关客户端.spec
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"

# PEP 668（Arch/Debian 等系统 Python 禁止裸 pip）：没在 venv 里就自动建/用 .venv
# 有 .venv-gui（系统 Python + gi/WebKit2，见指南"坑"）就用它 → 产物带原生窗口；
# 否则回退普通 .venv → 产物 headless（浏览器访问）
if [ -z "${VIRTUAL_ENV:-}" ]; then
  if [ -d .venv-gui ]; then
    source .venv-gui/bin/activate
  else
    [ -d .venv ] || "$PYTHON" -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
  fi
  PYTHON=python
fi

# 依赖安装：venv 里可能没有 pip 模块（uv venv 默认不装），按 pip → uv 顺序降级
if "$PYTHON" -m pip --version >/dev/null 2>&1; then
  "$PYTHON" -m pip install -q -r requirements.txt pyinstaller
elif command -v uv >/dev/null 2>&1; then
  uv pip install -q --python "$PYTHON" -r requirements.txt pyinstaller
else
  echo "错误：需要 pip 或 uv 之一来安装依赖" >&2
  exit 1
fi
"$PYTHON" -m PyInstaller --noconfirm --clean 网关客户端.spec

echo
echo "打包完成，产物在 dist/:"
ls -lh dist/ | grep -v '\.md$' || true
