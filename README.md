# TK RAG 项目

基于 RAG (Retrieval-Augmented Generation) 技术构建的企业知识库问答系统。

## 项目介绍

TK RAG 是一个完整的企业知识库问答系统，通过结合检索增强生成(RAG)
技术，为企业提供高质量的知识检索和问答服务。系统支持多种文档格式，采用混合检索策略(BM25+向量检索)，并提供完整的权限管理和来源追踪功能。

### 核心特性

- **多源文档处理**：支持PDF、Word、Excel、PowerPoint等多种格式文档的自动转换和解析
- **混合检索策略**：结合BM25和向量检索的混合检索方案，提高检索准确度
- **结构化存储**：使用MySQL、Milvus和Elasticsearch实现结构化和向量化数据管理
- **部门权限控制**：支持基于部门ID的文档权限管理
- **多轮对话**：支持上下文理解和多轮对话能力
- **来源可追溯**：回答内容提供明确的来源文档及置信度信息

## 项目结构

```
tk_rag/
├── src/                                     # 源代码目录
│   ├── api/                                 # API 接口
│   │   ├── base.py                          # API 基础组件(响应、错误码等)
│   │   ├── chat_api.py                      # 聊天相关接口
│   │   ├── document_api.py                  # 文档管理接口
│   │   ├── error_codes.py                   # 错误代码
│   │   ├── response.py                      # 响应构造
│   │   ├── __init__.py                      # API 模块初始化
│   │   └── request/                         # RAG 实现
│   │       ├── chat_ragchat_request.py      # RAG 聊天接口参数定义
│   │       ├── document_delete_request.py   # 文档删除接口参数定义
│   │       └── document_upload_request.py   # 文档上传接口参数定义
│   ├── core/                                # 核心业务逻辑
│   │   ├── lifecycle/                       # 周期初始化管理
│   │   ├── document/                        # 文档处理
│   │   │   ├── content_chunker.py           # 文档内容分块
│   │   │   ├── content_merger.py            # 文档内容按页合并
│   │   │   ├── doc_convert.py               # 文档转换 PDF
│   │   │   ├── doc_parse.py                 # 文档解析
│   │   │   └── __init__.py                  # 文档模块初始化
│   │   └── rag/                             # RAG 实现
│   │       ├── embedder.py                  # 向量嵌入器
│   │       ├── hybrid_retriever.py          # 混合检索器
│   │       ├── llm_generator.py             # LLM生成模块
│   │       ├── llm.py                       # LLM基础封装
│   │       ├── reranker.py                  # 重排序器
│   │       ├── __init__.py                  # RAG模块初始化
│   │       └── retrieval/                   # 检索模块
│   │           ├── bm25_retriever.py        # BM25检索
│   │           ├── text_retriever.py        # 元数据查询
│   │           ├── vector_retriever.py      # 向量检索
│   │           └── __init__.py              # 检索模块初始化
│   ├── database/                            # 数据库操作
│   │   ├── mysql/                           # MySQL 相关
│   │   ├── milvus/                          # Milvus 向量数据库
│   │   └── elasticsearch/                   # Elasticsearch 全文搜索
│   ├── services/                            # 业务服务层
│   │   ├── base.py                          # 服务基类
│   │   ├── chat.py                          # 聊天服务
│   │   ├── document.py                      # 文档服务
│   │   └── mock.py                          # Mock 数据服务
│   ├── middleware/                          # 中间件
│   │   └── base_middleware.py               # 基础请求中间件
│   └── utils/                               # 工具函数
│       ├── common/                          # 通用工具
│       │   ├── logger.py                    # log 日志工具
│       │   ├── similar_count.py             # 向量相似度计算
│       │   └── unit_convert.py              # 体积单位转换工具
│       ├── validator/                       # 验证工具类
│       │   ├── args_validator.py            # 参数校验
│       │   ├── content_validator.py         # 内容校验
│       │   ├── file_validator.py            # 文档校验
│       │   ├── system_validator.py          # 系统检查
│       │   └── __init__.py                  # 验证模块初始化
│       ├── doc_toolkit.py                   # 文档工具
│       ├── extract_summary.py               # LLM 摘要提取工具
│       ├── table_toolkit.py                 # 表格工具
│       └── __init__.py                      # 工具模块初始化
├── tests/                                   # 测试代码
├── datas/                                   # 数据目录
│   ├── raw/                                 # 原始文档
│   └── processed/                           # 处理后的文档
├── models/                                  # 模型目录
│   ├── bge-m3/                              # 向量模型
│   └── bge-reranker-v2-m3/                  # 重排序模型
├── logs/                                    # 日志目录
├── config/                                  # 配置目录
│   └── settings.py                          # 配置文件
├── scripts/                                 # 脚本目录
│   ├── install_es_ik.sh                     # ES + IK 分词器安装脚本
│   ├── install_kibana.sh                    # kibana 安装脚本
│   ├── raw/                                 # 原始文档
│   └── init/                                # 初始化脚本
│       ├── init_all.py                      # 项目初始化脚本
│       ├── init_es.py                       # Elasticsearch 数据库初始化脚本
│       ├── init_milvus.py                   # Milvus 数据库初始化脚本
│       ├── init_mysql.py                    # mysql 数据库初始化脚本
│       └── schema/                          # 数据库schema
│           ├── milvus_schema.json           # Milvus集合schema
│           ├── mysql_schema.sql             # MySQL表结构
│           └── es_schema.json               # ES索引schema
├── app.py                                   # FastAPI应用入口
├── requirements.txt                         # 依赖包
├── .gitignore                         # Git忽略文件配置
├── .env                               # 环境配置信息
└── README.md                          # 项目文档
```

## 技术架构

### 数据处理流程

1. **文档上传** - 接收并验证文档格式与大小
2. **文档转换** - 将各种格式统一转换为PDF
3. **文档解析** - 使用MinerU-GPU解析PDF结构信息
4. **文本切块** - 基于内容语义进行智能文本分段
5. **向量化存储** - 将文本段落转换为向量并存入Milvus
6. **全文索引** - 在Elasticsearch建立全文索引

### 检索回答流程

1. **接收查询** - 处理用户问题并验证权限
2. **混合检索** - 结合BM25和向量检索获取相关文档片段
3. **重排序** - 对检索结果进行二次精排
4. **生成回答** - 使用LLM合成最终回答
5. **来源追溯** - 提供引用来源及置信度

## 功能特性

### 1. 文档处理

- **多格式支持**：PDF、Word、Excel、PowerPoint等
- **自动转换**：使用LibreOffice将各种格式转换为PDF
- **结构化解析**：使用MinerU-GPU提取PDF文档结构和内容
- **智能分块**：基于语义和结构的智能文本切块策略

### 2. 混合检索系统

- **向量检索**：使用Milvus存储和检索文本向量
- **全文检索**：使用Elasticsearch提供BM25全文检索
- **混合排序**：融合两种检索结果并按相关度排序
- **重排序优化**：使用重排序模型进行精确相关性排序

### 3. 问答生成

- **上下文理解**：支持多轮对话和上下文理解
- **答案生成**：基于检索结果生成连贯、准确的回答
- **来源追踪**：提供答案的来源文档和页码信息
- **置信度评分**：显示每个引用来源的置信度

### 4. 权限管理

- **部门权限**：基于部门ID控制文档访问权限
- **多部门共享**：支持文档在多个部门间共享
- **权限校验**：查询时自动过滤无权限文档

## 环境要求

- Python 3.10
- MySQL 8.0+
- Milvus 2.5.10
- Elasticsearch 7.17+
- LibreOffice 7.6.4（用于文档转换）
- Miniconda 3
- Ubuntu 22.04 amd64
- CUDA 12.8（推荐，用于加速模型推理）

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
# 3.1 安装 pytorch == 12.8
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# 3.2 安装 vllm(暂未使用), 注意修改本地 cuda 版本 == 12.8
pip install vllm --extra-index-url https://download.pytorch.org/whl/cu128

# 3.3 安装 MinerU-GPU
# 安装 应用
pip install -U magic-pdf[full] -i https://mirrors.aliyun.com/pypi/simple

# 从 ModelScope 下载模型
pip install modelscope
wget https://gcore.jsdelivr.net/gh/opendatalab/MinerU@master/scripts/download_models.py -O download_models.py
python download_models.py

# 官方安装文档: https://github.com/opendatalab/MinerU/blob/master/docs/README_Ubuntu_CUDA_Acceleration_zh_CN.md

# 3.4 安装 Libreoffice
sudo apt-get install libreoffice=7.6.4.1-0ubuntu0.22.04.1
```

### 4. 安装软件包

```bash
# 进入项目文件夹安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 5. 初始化项目

运行初始化脚本：

```bash
python scripts/init_all.py
```

该脚本将：

1. 创建必要的目录结构
2. 初始化 MySQL 数据库（包括表结构）
3. 初始化 Milvus 数据库（包括集合和索引）
4. 初始化 ES 数据库(包括表结构和索引)

### 6. 验证初始化

```bash
# 6.1 检查 mysql 数据库连接
python src/databases/mysql/connection.py

# 6.2 检查 Milvus 数据库连接
python src/databases/milvus/connection.py

# 6.3 使用 HTTPS 连接, 检查 ES 服务状态
curl -k -u user:passwd https://localhost:9200
```

### 7. 启动 FastAPI

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

## API 接口

系统提供以下核心接口：

### 接口文档

访问 Swagger 文档来查看和测试这些接口：

- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc

### 主要接口

- **健康检查**：`GET /api/v1/health`
- **RAG聊天**：`POST /api/v1/chat/rag_chat`
- **上传文档**：`POST /api/v1/documents/upload`
- **删除文档**：`DELETE /api/v1/documents/delete`

详细接口规范请参考 [Demo1.0 接口文档.md](Demo1.0%20接口文档.md)

## 高级配置

### 模型配置

系统使用多个模型协同工作：

1. **文本向量化模型**：默认使用BGE-M3，可在配置中修改
2. **文本重排序模型**：默认使用BGE-Reranker-V2-M3，可在配置中修改
3. **LLM模型**：默认使用外部API，支持配置为本地Qwen2.5-7B-Instruct

### 自定义拓展

1. **添加新的文档处理器**：
    - 在`src/core/document`中添加新的文档处理类
    - 实现所需的解析和转换方法

2. **自定义检索策略**：
    - 在`src/core/rag/retrieval`中实现新的检索器
    - 在`hybrid_retriever.py`中整合新检索器

## 其他工具推荐

### 1. ES 数据查询

```bash
# Elasticsearch Head：轻量级的 Chrome 插件
sudo docker run -p 9100:9100 mobz/elasticsearch-head:5
```

### 2. Milvus 管理工具

```bash
# Attu - Milvus图形化界面
docker run -p 8000:3000 -e MILVUS_URL=localhost:19530 zilliz/attu:latest
```

### 3. 监控工具

```bash
# Prometheus + Grafana监控
# 在config/monitoring目录下有相关配置文件
docker-compose -f docker-compose-monitoring.yml up -d
```

## 常见问题

1. **文档解析失败**：
    - 检查文档是否有密码保护
    - 确认文档格式是否受支持
    - 查看日志获取详细错误信息

2. **检索结果不准确**：
    - 调整混合检索权重参数
    - 增加检索结果数量
    - 考虑更新向量模型

3. **系统响应缓慢**：
    - 检查数据库连接状态
    - 验证服务器资源使用情况
    - 调整并发配置参数