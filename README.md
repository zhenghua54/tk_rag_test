# TK RAG 项目

基于 RAG (Retrieval-Augmented Generation) 技术构建的企业知识库问答系统。

## 项目结构

```
tk_rag/
├── src/                               # 源代码目录
│   ├── api/                           # API 接口
│   │   ├── base.py                    # API 基础组件(响应、错误码等)
│   │   ├── chat.py                    # 聊天相关接口
│   │   ├── document.py                # 文档管理接口
│   │   └── __init__.py               # API 模块初始化
│   ├── core/                          # 核心业务逻辑
│   │   ├── document/                  # 文档处理
│   │   ├── llm/                       # 大语言模型
│   │   └── rag/                       # RAG 实现
│   ├── database/                      # 数据库操作
│   │   ├── mysql/                     # MySQL 相关
│   │   ├── milvus/                    # Milvus 向量数据库
│   │   └── elasticsearch/             # Elasticsearch 全文搜索
│   ├── services/                      # 业务服务层
│   │   ├── base.py                    # 服务基类
│   │   ├── chat.py                    # 聊天服务
│   │   ├── document.py                # 文档服务
│   │   └── mock.py                    # Mock 数据服务
│   └── utils/                         # 工具函数
│       ├── common/                    # 通用工具
│       ├── file/                      # 文件操作
│       └── logger/                    # 日志工具
├── tests/                             # 测试代码
├── datas/                             # 数据目录
│   ├── raw/                           # 原始文档
│   └── processed/                     # 处理后的文档
├── models/                            # 模型目录
│   ├── bge-m3/                        # 向量模型
│   ├── Qwen2.5-7B-Instruct-1M/        # LLM模型
│   └── bge-reranker-v2-m3/            # 重排序模型
├── logs/                              # 日志目录
├── config/                            # 配置目录
│   └── settings.py                    # 配置文件
├── scripts/                           # 脚本目录
│   └── init/                          # 初始化脚本
│       ├── init_all.py                # 项目初始化脚本
│       ├── init_es.py                 # Elasticsearch 数据库初始化脚本
│       ├── init_milvus.py             # Milvus 数据库初始化脚本
│       ├── init_mysql.py              # mysql 数据库初始化脚本
│       └── schema/                    # 数据库schema
│           ├── milvus_schema.json     # Milvus集合schema
│           ├── mysql_schema.sql       # MySQL表结构
│           └── es_schema.json         # ES索引schema
├── app.py                             # FastAPI应用入口
├── requirements.txt                   # 依赖包
├── .gitignore                         # Git忽略文件配置
├── .env                               # 环境配置信息
├── README.md                          # 项目文档
└── Demo1.0 接口文档.md                 # API接口文档
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
- Ubuntu 22.04 amd64

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

### 2. 安装数据库

```bash
# 安装 mysql8.0 版本
wget https://dev.mysql.com/get/mysql-apt-config_0.8.29-1_all.deb  # 下载安装包
sudo dpkg -i mysql-apt-config_0.8.29-1_all.deb  # 添加官方 APT 仓库
sudo apt update
sudo apt install -y mysql-server # 安装 mysql 服务
systemctl status mysql  # 检查服务状态

# 安装 milvus 2.5.10 docker compose版本
wget https://github.com/milvus-io/milvus/releases/download/v2.5.12/milvus-standalone-docker-compose.yml -O docker-compose.yml  # 下载安装脚本
sudo docker compose up -d   # 执行安装
# 官方安装文档: https://milvus.io/docs/install_standalone-docker-compose.md

# 安装 ES 并启动
执行脚本 "./install_es_ik.sh"，安装 elasticsearch 和 IK 分词器

# 打开系统防火墙端口
sudo ufw allow 3306/tcp
sudo ufw allow 19530/tcp
sudo ufw allow 9200/tcp
```

### 3. 安装工具

```bash
# 2.1 安装 pytorch == 12.8
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# 2.2 安装 vllm(暂未使用), 注意修改本地 cuda 版本 == 12.8
pip install vllm --extra-index-url https://download.pytorch.org/whl/cu128

# 2.3 安装 MinerU-GPU
# 安装 应用
pip install -U magic-pdf[full] -i https://mirrors.aliyun.com/pypi/simple

# 从 ModelScope 下载模型
pip install modelscope
wget https://gcore.jsdelivr.net/gh/opendatalab/MinerU@master/scripts/download_models.py -O download_models.py
python download_models.py

# 官方安装文档: https://github.com/opendatalab/MinerU/blob/master/docs/README_Ubuntu_CUDA_Acceleration_zh_CN.md

# 2.4 安装 Libreoffice
sudo apt-get install libreoffice
```

### 4. 安装软件包

```bash
# 进入项目文件夹安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 5. 初始化项目

运行初始化脚本：

```bash
python scripts/init/init_all.py
```

该脚本将：

1. 创建必要的目录结构
2. 初始化 MySQL 数据库（包括表结构）
3. 初始化 Milvus 数据库（包括集合和索引）
4. 初始化 ES 数据库(包括表结构和索引)

### 6. 验证初始化

```bash
# 6.1 检查 mysql 数据库连接
python src/database/mysql/connection.py

# 6.2 检查 Milvus 数据库连接
python src/database/milvus/connection.py

# 6.3 使用 HTTPS 连接, 检查 ES 服务状态
curl -k -u user:passwd https://localhost:9200
```

### 7. 启动 FastAPI

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

#### 接口文档

访问 Swagger 文档来查看和测试这些接口：

- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc

#### 接口 url

- 健康检查：http://localhost:8000/api/v1/health
- 聊天接口：http://localhost:8000/api/v1/rag_chat
- 上传文档：http://localhost:8000/api/v1/documents
- 删除文档：http://localhost:8000/api/v1/documents/{doc_id}

## 其他工具推荐

### 1. ES 数据查询

```bash
# Elasticsearch Head：轻量级的 Chrome 插件
sudo docker run -p 9100:9100 mobz/elasticsearch-head:5
```
