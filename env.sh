# setup_env_full.sh - 完整配置
#!/bin/bash

echo "🚀 配置完整TK-RAG环境变量..."


# 创建完整的.env文件
cat > .env << EOF
# =============================================================================
# TK-RAG完整环境配置
# =============================================================================

# 环境配置
ENV=dev

# LLM配置
LLM_NAME=qwen-turbo-2025-02-11
DASHSCOPE_API_KEY=sk-16881649dca1455c936da5474e571fb0	
DASHSCOPE_API_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# CUDA配置
CUDA_DEVICE_ID=0

# 数据库配置
DB_NAME=zh_db
MYSQL_HOST=192.168.6.202
MYSQL_USER=zh
MYSQL_PASSWORD=Zh@654321!
MYSQL_PORT=3306

# Milvus配置
# MILVUS_HOST=192.168.6.202
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_URI=http://${MILVUS_HOST}:19530
MILVUS_TOKEN=

# LibreOffice路径
LIBREOFFICE_PATH=/usr/bin/libreoffice

# 状态同步配置
STATUS_SYNC_ENABLED=true
STATUS_SYNC_TIMEOUT=10
STATUS_SYNC_RETRY_ATTEMPTS=3
STATUS_SYNC_RETRY_DELAY=1.0
EOF

echo "✅ 完整.env文件已创建"
echo "🎯 现在可以启动完整的TK-RAG系统了"