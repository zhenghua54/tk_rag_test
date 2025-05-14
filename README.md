# TK RAG Demo

这是一个基于 RAG (Retrieval-Augmented Generation) 的智能文档处理系统，集成了文档解析和问答功能。

## 主要功能

- 文档解析服务
  - 支持 PDF、Word、Excel、PowerPoint 等格式文档解析
  - 自动检测文档类型
  - 提供 Markdown、Layout 和 JSON 格式输出
  - RESTful API 接口

- RAG 问答系统
  - 文档向量化和索引构建
  - 智能文本分块
  - 基于 Faiss 的向量检索
  - 支持多种 LLM 模型集成

## 环境要求

- Miniconda 3
- Python 3.10
- Apple M 系列芯片（仅使用 CPU）

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
│   ├── database/           # 数据库相关代码
│   └── utils/              # 工具函数
├── tests/                   # 测试代码
├── docs/                    # 文档目录
├── logs/                    # 日志文件目录
└── datas/                   # 数据目录
    ├── origin_data/        # 原始数据
    └── output_data/        # 输出数据
```

## 快速开始

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

## 配置说明

在 `codes/config.py` 中配置以下参数：

### 数据处理配置
- `DATA_DIR`: 数据目录路径
- `RAW_DATA_DIR`: 原始数据目录
- `PROCESSED_DATA_DIR`: 处理后的数据目录
- `VECTOR_DATA_DIR`: 向量数据目录

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

## 开发指南

1. 代码风格遵循 PEP 8 规范
2. 所有新功能都需要编写对应的单元测试
3. 提交代码前请运行完整的测试套件
4. 保持文档的及时更新

## 注意事项

1. 本项目针对 Apple M 系列芯片优化，仅使用 CPU 进行计算
2. 建议使用 Miniconda 管理 Python 环境
3. 确保系统有足够的内存用于向量检索



### 文件访问

处理后的文件可以通过以下 URL 访问：

- Markdown: `/output/{文档名}/{文档名}.md`
- Layout: `/output/{文档名}/{文档名}_layout.pdf`
- JSON: `/output/{文档名}/{文档名}_middle.json`


## 注意事项

1. 本项目针对 Apple M 系列芯片优化，仅使用 CPU 进行计算
2. 建议使用 Miniconda 管理 Python 环境
3. 确保系统有足够的内存用于向量检索
4. 建议使用 SSD 存储以提高性能

1. 确保 `datas` 目录有足够的写入权限
2. 上传的文件会保存在 `datas/origin_data` 目录
3. 处理结果会保存在 `datas/output_data/{文档名}` 目录
4. 建议使用 HTTPS 在生产环境中部署 