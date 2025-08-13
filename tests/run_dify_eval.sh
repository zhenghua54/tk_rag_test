#!/bin/bash

# Dify RAGAS评估脚本快速启动器

echo "=========================================="
echo "Dify平台RAG系统性能评估工具"
echo "=========================================="

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到python3命令"
    echo "请确保已安装Python 3.7+"
    exit 1
fi

# 检查依赖
echo "检查依赖包..."
python3 -c "import ragas, datasets, aiohttp, pandas" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ 缺少必要的依赖包"
    echo "正在安装依赖..."
    pip3 install -r requirements_dify_eval.txt
    if [ $? -ne 0 ]; then
        echo "❌ 依赖安装失败，请手动安装"
        exit 1
    fi
fi

echo "✅ 依赖检查完成"

# 检查数据目录
if [ ! -d "data/ragbench" ]; then
    echo "⚠️  警告: 未找到data/ragbench目录"
    echo "请确保RagBench数据集已正确放置"
    echo "目录结构应该是: data/ragbench/{task_name}/{split}-00000-of-00001.parquet"
fi

# 运行评估脚本
echo ""
echo "启动评估脚本..."
python3 evaluate_dify_rag_with_ragas.py

echo ""
echo "评估完成！结果保存在evaluation_results目录中"
