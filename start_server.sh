#!/bin/bash

# 配置变量
APP_NAME="fastapi_app:app"
PORT=8000
LOG_DIR="logs"
PID_FILE="server.pid"
CONDA_ENV="rag"
DEBUG_LOG="logs/startup_debug.log"

# 设置时区为东八区
export TZ="Asia/Shanghai"

# 创建调试日志文件
mkdir -p "$LOG_DIR"
echo "$(date '+%Y-%m-%d %H:%M:%S') - 开始启动服务" > "$DEBUG_LOG"

# 检查 conda 环境是否存在
echo "$(date '+%Y-%m-%d %H:%M:%S') - 检查 conda 环境" >> "$DEBUG_LOG"
if ! conda env list | grep -q "^${CONDA_ENV} "; then
    echo "错误: conda 环境 '${CONDA_ENV}' 不存在"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 错误: conda 环境不存在" >> "$DEBUG_LOG"
    exit 1
fi

# 激活 conda 环境
echo "激活 conda 环境: ${CONDA_ENV}"
echo "$(date '+%Y-%m-%d %H:%M:%S') - 激活 conda 环境: ${CONDA_ENV}" >> "$DEBUG_LOG"
source $(conda info --base)/etc/profile.d/conda.sh
conda activate ${CONDA_ENV}

# 检查 Python 环境
echo "$(date '+%Y-%m-%d %H:%M:%S') - 检查 Python 环境" >> "$DEBUG_LOG"
echo "Python 路径: $(which python)" >> "$DEBUG_LOG"
echo "Python 版本: $(python --version)" >> "$DEBUG_LOG"

# 检查项目依赖
echo "$(date '+%Y-%m-%d %H:%M:%S') - 检查项目依赖" >> "$DEBUG_LOG"
if ! python -c "import fastapi, uvicorn" 2>> "$DEBUG_LOG"; then
    echo "错误: 缺少必要的依赖包"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 错误: 缺少依赖包" >> "$DEBUG_LOG"
    exit 1
fi

# 检查是否已启动
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "服务已在运行，PID: $(cat $PID_FILE)"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 服务已在运行" >> "$DEBUG_LOG"
    exit 1
fi

# 检查端口是否被占用
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "错误: 端口 $PORT 已被占用"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 错误: 端口被占用" >> "$DEBUG_LOG"
    exit 1
fi

# 启动服务 - 先尝试直接启动以查看错误
echo "启动服务..."
echo "$(date '+%Y-%m-%d %H:%M:%S') - 启动服务" >> "$DEBUG_LOG"

# 使用调试模式启动，将输出重定向到调试日志
nohup uvicorn "$APP_NAME" \
    --host 0.0.0.0 \
    --port "$PORT" \
    --log-level debug \
#    --reload \
    >> "$DEBUG_LOG" 2>&1 &
PID=$!

# 等待几秒检查进程是否存活
sleep 3
if ! kill -0 "$PID" 2>/dev/null; then
    echo "错误: 服务启动失败，请查看调试日志: $DEBUG_LOG"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 错误: 服务启动失败" >> "$DEBUG_LOG"
    exit 1
fi

echo $PID > "$PID_FILE"

echo "服务已启动:"
echo "  - 端口: $PORT"
echo "  - PID: $PID"
echo "  - 应用日志: $LOG_DIR/app.log"
echo "  - 错误日志: $LOG_DIR/error.log"
echo "  - 调试日志: $DEBUG_LOG"
echo "  - 时区: $(date '+%Y-%m-%d %H:%M:%S %Z')"

echo "$(date '+%Y-%m-%d %H:%M:%S') - 服务启动成功，PID: $PID" >> "$DEBUG_LOG"