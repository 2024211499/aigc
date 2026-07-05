#!/usr/bin/env bash
# setup.sh — Linux / macOS / WSL 一键建立虚拟环境并安装依赖
# 用法：bash setup.sh  （或 chmod +x setup.sh && ./setup.sh）
set -euo pipefail

# ── 颜色输出 ──────────────────────────────────────────────────────
cyan='\033[0;36m'; green='\033[0;32m'; yellow='\033[1;33m'; reset='\033[0m'
step() { echo -e "${cyan}[${1}/${STEPS}] ${2}${reset}"; }
STEPS=4

# ── 定位根目录（脚本所在位置）────────────────────────────────────
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ── 1. 检查 Python 版本 ────────────────────────────────────────────
step 1 "Checking Python 3.10–3.12"
PY=""
for cmd in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(sys.version_info[:2])" 2>/dev/null || true)
        # 输出类似 (3, 12)
        major=$(echo "$ver" | tr -d '(),' | awk '{print $1}')
        minor=$(echo "$ver" | tr -d '(),' | awk '{print $2}')
        # Agent 模块依赖最高支持 3.12，不支持 3.13+
        if [ "${major:-0}" -eq 3 ] && [ "${minor:-0}" -ge 10 ] && [ "${minor:-0}" -le 12 ]; then
            PY="$cmd"; break
        fi
    fi
done
if [ -z "$PY" ]; then
    echo "Compatible Python version not found (3.10–3.12 required)." >&2
    echo "Current Agent dependencies do not support 3.13+, please install 3.12:" >&2
    echo "  https://www.python.org/downloads/release/python-3129/" >&2
    exit 1
fi
echo "  Using interpreter: $PY  ($("$PY" --version 2>&1))  [Supported: 3.10–3.12]"

# ── 2. 创建虚拟环境 ────────────────────────────────────────────────
step 2 "Creating .venv"
VENV="$ROOT/.venv"
if [ -d "$VENV" ]; then
    echo -e "  ${yellow}.venv already exists, skipping creation${reset}"
else
    "$PY" -m venv "$VENV"
fi

# ── 3. 激活并升级 pip ─────────────────────────────────────────────
step 3 "Upgrading pip"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install --upgrade pip --quiet

# ── 4. 安装依赖 ────────────────────────────────────────────────────
step 4 "Installing requirements.txt"
pip install -r "$ROOT/requirements.txt"

# ── 提示 ──────────────────────────────────────────────────────────
echo ""
echo -e "${green}========================================${reset}"
echo -e "${green} Setup complete! To activate the environment:${reset}"
echo ""
echo "   source .venv/bin/activate"
echo ""
echo -e "${green} To start the service:${reset}"
echo ""
echo "   cd backend && python run.py"
echo -e "${green}========================================${reset}"