#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "[AionUi] 正在启动自托管后端服务..."

if [ ! -f "aionui.db" ]; then
    echo "[AionUi] 首次运行，初始化数据库..."
    python3 app.py --init
fi

echo "[AionUi] 启动 Flask 服务在 http://0.0.0.0:5000 ..."
python3 app.py
