#!/bin/bash

# 配置变量
APP_NAME="fastapi_app:app"
PORT=8000
PID_FILE=".server.pid"
CONDA_ENV="rag"

# 设置时区为东八区
export TZ="Asia/Shanghai"

# 检查是否已经运行
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "服务已在运行，PID: $PID"
        exit 1
    else
        echo "发现无效的PID文件，删除..."
        rm -f "$PID_FILE"
    fi
fi

# 获取conda环境路径
CONDA_PATH=$(conda info --base)
ENV_PATH="$CONDA_PATH/envs/$CONDA_ENV"

# 启动服务（直接使用环境中的python）
echo "启动服务..."
nohup "$ENV_PATH/bin/python" -m uvicorn "$APP_NAME" \
    --host 0.0.0.0 \
    --port "$PORT" \
    --log-level debug \
    > /dev/null 2>&1 &

# 记录进程ID
echo $! > "$PID_FILE"
echo "服务已启动，PID: $!"
echo "日志文件位置: logs/app.log"
echo "错误日志位置: logs/error.log"