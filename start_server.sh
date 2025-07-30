#!/bin/bash

# 配置变量
APP_NAME="fastapi_app:app"
PORT=8000
LOG_DIR="logs"
PID_FILE="server.pid"
CONDA_ENV="rag"

# 设置时区为东八区
export TZ="Asia/Shanghai"

# 检查 conda 环境是否存在
if ! conda env list | grep -q "^${CONDA_ENV} "; then
    echo "错误: conda 环境 '${CONDA_ENV}' 不存在"
    exit 1
fi

# 激活 conda 环境
echo "激活 conda 环境: ${CONDA_ENV}"
source $(conda info --base)/etc/profile.d/conda.sh
conda activate ${CONDA_ENV}

# 检查是否已启动
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "服务已在运行，PID: $(cat $PID_FILE)"
    exit 1
fi

# 确保日志目录存在
mkdir -p "$LOG_DIR"

# 启动服务 - 使用项目内置的日志系统
echo "启动服务..."
nohup uvicorn "$APP_NAME" \
    --host 0.0.0.0 \
    --port "$PORT" \
    --log-config /dev/null \
    --access-log \
    --log-level info \
    > /dev/null 2>&1 &
PID=$!
echo $PID > "$PID_FILE"

echo "服务已启动:"
echo "  - 端口: $PORT"
echo "  - PID: $PID"
echo "  - 应用日志: $LOG_DIR/app.log"
echo "  - 错误日志: $LOG_DIR/error.log"
echo "  - 时区: $(date '+%Y-%m-%d %H:%M:%S %Z')"