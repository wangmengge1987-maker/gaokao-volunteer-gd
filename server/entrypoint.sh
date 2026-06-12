#!/bin/bash
set -e

# 如果数据库不存在，用样本数据初始化
if [ ! -f "gaokao.db" ]; then
    echo "=== 数据库不存在，初始化中... ==="
    python scripts/init_db.py
    echo "=== 数据库初始化完成 ==="
else
    echo "=== 数据库已存在，跳过初始化 ==="
fi

# 启动服务
echo "=== 启动服务，端口: ${PORT:-80} ==="
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-80}
