#!/bin/bash

# 设置错误时退出
set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_message() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 未安装，请先安装 $1"
        exit 1
    fi
}

# 检查 Python 版本
check_python_version() {
    local python_version=$(python -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    if [[ $(echo "$python_version >= 3.8" | bc -l) -eq 1 ]]; then
        print_message "Python 版本: $python_version"
    else
        print_error "需要 Python 3.8 或更高版本"
        exit 1
    fi
}

# 检查并创建 Conda 环境
setup_conda_env() {
    local env_name="tk_rag"
    
    if conda env list | grep -q "^$env_name "; then
        print_warning "Conda 环境 $env_name 已存在"
    else
        print_message "创建 Conda 环境 $env_name..."
        conda create -n $env_name python=3.8 -y
    fi
    
    print_message "激活 Conda 环境 $env_name..."
    eval "$(conda shell.bash hook)"
    conda activate $env_name
}

# 安装依赖
install_dependencies() {
    print_message "安装依赖包..."
    pip install --upgrade pip
    pip install -r requirements.txt
}

# 检查 CUDA 是否可用
check_cuda() {
    if command -v nvidia-smi &> /dev/null; then
        print_message "检测到 NVIDIA GPU，将安装 GPU 版本的依赖..."
        pip uninstall -y faiss-cpu
        pip install faiss-gpu
    else
        print_warning "未检测到 NVIDIA GPU，将使用 CPU 版本"
    fi
}

# 检查 magic-pdf 包
check_magic_pdf() {
    if ! pip show magic-pdf &> /dev/null; then
        print_warning "magic-pdf 包未安装，如果需要 PDF 处理功能，请手动安装"
    fi
}

# 创建必要的目录
create_directories() {
    print_message "创建必要的目录..."
    
    # 项目根目录
    mkdir -p codes
    mkdir -p codes/database
    mkdir -p codes/models
    mkdir -p codes/utils
    mkdir -p codes/scripts
    mkdir -p codes/api
    
    # 数据目录
    mkdir -p datas
    mkdir -p datas/origin_data
    mkdir -p datas/output_data
    
    # 日志目录
    mkdir -p logs
    
    # 测试目录
    mkdir -p tests
}

# 主函数
main() {
    print_message "开始环境部署..."
    
    # 检查必要的命令
    check_command conda
    check_command python
    
    # 检查 Python 版本
    check_python_version
    
    # 设置 Conda 环境
    setup_conda_env
    
    # 安装依赖
    install_dependencies
    
    # 检查 CUDA
    check_cuda
    
    # 检查 magic-pdf
    check_magic_pdf
    
    # 创建目录
    create_directories
    
    print_message "环境部署完成！"
    print_message "请确保已正确配置 config.py 中的相关参数"
    print_message "可以通过运行 'python codes/scripts/build_vector_db.py --help' 测试环境是否正常"
}

# 执行主函数
main 