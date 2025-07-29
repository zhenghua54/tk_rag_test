#!/bin/bash
APP_NAME="fastapi_app:app"
PORT=8000
LOG_DIR="logs"
LOG_FILE="$LOG_DIR/uvicorn_$(date '+%Y%m%d_%H%M%S').log"
PID_FILE="server.pid"

mkdir -p "$LOG_DIR"

# 检查是否已启动
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Server is already running with PID $(cat $PID_FILE)."
    exit 1
fi

# 启动服务
nohup uvicorn "$APP_NAME" --host 0.0.0.0 --port "$PORT" > "$LOG_FILE" 2>&1 &
PID=$!
echo $PID > "$PID_FILE"

echo "Server started on port $PORT (PID $PID) using GPU 1. Logs: $LOG_FILE"
