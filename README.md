# TK RAG Demo

这是一个基于 RAG (Retrieval-Augmented Generation) 的智能文档处理系统，集成了文档解析和问答功能。

## 主要功能

- 文档解析服务
  - 支持 PDF、Word、Excel、PowerPoint 等格式文档解析
  - 自动检测文档类型
  - 提供 Markdown、Layout 和 JSON 格式输出
  - RESTful API 接口

- 文件处理服务
  - 支持多种格式文件上传和存储
  - 自动转换为 PDF 格式
  - 文件信息数据库管理
  - 批量处理能力

- RAG 问答系统
  - 文档向量化和索引构建
  - 智能文本分块
  - 基于 Faiss 的向量检索
  - 支持多种 LLM 模型集成

## 环境要求

- Miniconda 3
- Python 3.10
- Apple M 系列芯片（仅使用 CPU）
- MySQL 数据库
- LibreOffice（用于文件格式转换）

## 项目结构

```
.
├── README.md                 # 项目说明文档
├── requirements.txt          # 项目依赖
├── setup.sh                 # 环境配置脚本
├── config.py                # 配置文件
├── app_streamlit.py         # Streamlit 应用入口
├── src/                     # 核心代码目录
│   ├── __init__.py         # 包初始化文件
│   ├── llm_generate.py     # LLM 生成相关代码
│   ├── query_process.py    # 查询处理相关代码
│   ├── api/                # API 相关代码
│   │   ├── libreoffice_api.py  # LibreOffice 转换接口
│   │   └── mineru_api.py       # MinerU 解析接口
│   ├── database/           # 数据库相关代码
|   |   └── milvus_connect.py    # Milvus 连接管理
│   │   └── mysql_connect.py    # MySQL 连接管理
│   └── utils/              # 工具函数
│       ├── file_parse.py       # 文件解析工具
│       ├── file_translate.py   # 文件转换工具
│       ├── file_upload.py      # 文件上传工具
│       └── get_logger.py       # 日志工具
├── docs/                    # 文档目录
├── logs/                    # 日志文件目录
└── datas/                   # 数据目录
    ├── raw/                # 原始数据
    ├── translated/         # 转换后的 PDF 文件
    └── output_data/        # 解析后的输出数据
```

## 快速开始

前置: 安装 conda, 推荐使用 miniconda
- 官方连接: https://www.anaconda.com/docs/getting-started/miniconda/install#linux-terminal-installer

1. 克隆项目：

```bash
git clone [项目地址]
cd tk_rag
```

2. 创建并激活 Conda 环境：

```bash
# 创建环境
conda create -n tk_rag python=3.10

# 激活环境
conda activate tk_rag

# 安装依赖
pip install -r requirements.txt
```

3. 安装 LibreOffice：

```bash
# macOS
brew install libreoffice

# Ubuntu
sudo apt-get install libreoffice
```

4. 配置 MySQL 数据库：

```sql
CREATE DATABASE rag_db;
```

## 配置说明

在 `config.py` 中配置以下参数：

### 数据库配置
- `MYSQL_CONFIG`: MySQL 连接配置
  - `host`: 数据库主机
  - `user`: 用户名
  - `password`: 密码
  - `charset`: 字符集
  - `database`: 数据库名

### 文件处理配置
- `SUPPORTED_FILE_TYPES`: 支持的文件类型
- `PATHS`: 文件路径配置
  - `origin_data`: 原始数据目录
  - `translated`: 转换后的 PDF 目录
  - `output_data`: 输出数据目录

### 模型配置
- `MODEL_NAME`: 使用的模型名称
- `EMBEDDING_DIM`: 嵌入向量维度
- `MAX_SEQ_LENGTH`: 最大序列长度

### 向量检索配置
- `FAISS_INDEX_TYPE`: Faiss 索引类型
- `TOP_K`: 检索返回的最大结果数

### 日志配置
- `LOG_LEVEL`: 日志级别
- `LOG_DIR`: 日志目录

## 使用说明

### 文件上传和转换

1. 上传文件：
```python
from src.utils.file_upload import upload_files, upload_file_to_db

# 上传文件到数据库
file_infos = upload_files("/path/to/files")
upload_file_to_db(file_infos)
```

2. 转换为 PDF：
```python
from src.utils.file_translate import update_file_path_to_db

# 转换文件并更新数据库
update_file_path_to_db()
```

3. 解析文件：
```python
from src.utils.file_parse import parse_file_to_db

# 解析文件并更新数据库
parse_file_to_db()
```

### 文件访问

处理后的文件可以通过以下路径访问：

- 原始文件：`datas/origin_data/{文件名}`
- PDF 文件：`datas/translated/{文件名}.pdf`
- 解析结果：`datas/output_data/{文件名}/`
  - Markdown：`{文件名}.md`
  - JSON：`{文件名}_content_list.json`
  - 图片：`images/`

## 注意事项

1. 本项目针对 Apple M 系列芯片优化，仅使用 CPU 进行计算
2. 建议使用 Miniconda 管理 Python 环境
3. 确保系统有足够的内存用于向量检索
4. 建议使用 SSD 存储以提高性能
5. 确保 `datas` 目录有足够的写入权限
6. 上传的文件会保存在 `datas/origin_data` 目录
7. 处理结果会保存在 `datas/output_data/{文档名}` 目录
8. 建议使用 HTTPS 在生产环境中部署 