#!/bin/bash

APP_NAME="fastapi_app:app"
PORT=8000
LOG_FILE="logs/uvicorn_$(date '+%Y%m%d_%H%M%S').log"

mkdir -p logs

# 检查是否已启动
if pgrep -f "uvicorn $APP_NAME" > /dev/null; then
    echo "Server is already running."
    exit 1
fi

# 启动服务
nohup uvicorn "$APP_NAME" --host 0.0.0.0 --port "$PORT" > "$LOG_FILE" 2>&1 &
echo "Server started on port $PORT. Logs: $LOG_FILE"
