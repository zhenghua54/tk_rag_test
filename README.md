# TK RAG 项目

基于 RAG (Retrieval-Augmented Generation) 技术构建的企业知识库问答系统。

## 项目结构

```
tk_rag/
├── src/                               # 源代码目录
│   ├── api/                           # API 接口
│   │   ├── office_convert.py     # 文档转换 API
│   │   └── mineru_api.py              # PDF 解析 API
│   ├── core/                          # 核心业务逻辑
│   │   ├── document/                  # 文档处理
│   │   ├── llm/                       # 大语言模型
│   │   └── rag/                       # RAG 实现
│   ├── database/                      # 数据库操作
│   │   ├── mysql/                     # MySQL 相关
│   │   └── milvus/                    # Milvus 向量数据库
│   └── utils/                         # 工具函数
│       ├── common/                    # 通用工具
│       ├── file/                      # 文件操作
│       └── logger/                    # 日志工具
├── tests/                             # 测试代码
├── datas/                             # 数据目录
│   ├── raw/                           # 原始文档
│   ├── processed/                     # 处理后的文档
│   └── translated/                    # 转换后的文档
├── models/                            # 模型目录
├── logs/                              # 日志目录
├── config.py                          # 配置文件
├── requirements.txt                   # 依赖包
└── README.md                          # 项目文档
```

## 功能特性

1. 文档处理
   - 支持多种格式文档（PDF、Word、Excel、PowerPoint）
   - 自动转换为 PDF 格式
   - PDF 文档解析和结构化

2. 向量存储
   - 使用 Milvus 向量数据库
   - 支持文档分块和向量化
   - 高效的相似度检索

3. 问答系统
   - 基于 RAG 的问答生成
   - 支持上下文理解和多轮对话
   - 答案来源可追溯

## 环境要求

- Python 3.10
- MySQL 8.0+
- Milvus 2.5.10
- LibreOffice（用于文档转换）
- Miniconda 3

## 快速开始

### 1. 创建并激活 Conda 环境：

```bash
# 安装 Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash ~/Miniconda3-latest-Linux-x86_64.sh
source ~/.bashrc

# 创建环境
conda create -n tk_rag python=3.10

# 激活环境
conda activate tk_rag
```

### 2. 安装软件包

```bash
# 安装 pytorch
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# 安装 MinerU-GPU 版本
# 安装 应用
pip install -U magic-pdf[full] -i https://mirrors.aliyun.com/pypi/simple
# 从 ModelScope 下载模型
pip install modelscope
wget https://gcore.jsdelivr.net/gh/opendatalab/MinerU@master/scripts/download_models.py -O download_models.py
python download_models.py

官方安装文档: https://github.com/opendatalab/MinerU/blob/master/docs/README_Ubuntu_CUDA_Acceleration_zh_CN.md

# 进入项目文件夹安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 安装 Libreoffice
sudo apt-get install libreoffice
```

### 3. 数据库准备

1. MySQL 数据库
   - 确保 MySQL 服务已启动
   - 默认配置：
     - 主机：localhost
     - 用户：root
     - 密码：Tk@654321
     - 数据库：rag_db

2. Milvus 数据库
   - 确保 Milvus 服务已启动
   - 默认配置：
     - 主机：localhost
     - 端口：19530
     - 数据库：default
     - 集合：tk_rag

### 4. 初始化项目

运行初始化脚本：
```bash
python scripts/init_project.py
```

该脚本将：
1. 创建必要的目录结构
2. 初始化 MySQL 数据库（包括表结构）
3. 初始化 Milvus 数据库（包括集合和索引）

### 5. 验证初始化

1. 检查 MySQL 数据库：
   ```bash
   python src/database/mysql/connection.py
   ```

2. 检查 Milvus 数据库：
   ```bash
   python src/database/milvus/connection.py
   ```