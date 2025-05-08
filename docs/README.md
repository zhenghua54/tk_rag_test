# TK RAG Demo

这是一个基于 RAG (Retrieval-Augmented Generation) 的文档问答系统演示项目。

## 环境要求

- Miniconda 3
- Python 3.8+
- Apple M 系列芯片（仅使用 CPU）

## 项目结构

```
.
├── README.md                 # 项目说明文档
├── requirements.txt          # 项目依赖
├── codes/                    # 核心代码目录
│   ├── config.py            # 配置文件
│   ├── database/            # 数据库相关代码
│   │   └── faiss_db.py      # Faiss 向量数据库操作
│   ├── utils/               # 工具函数
│   │   ├── file_to_markdown.py           # 通用文件转 Markdown
│   │   ├── markdown_chunker.py           # Markdown 文本分块
│   │   ├── office_to_markdown_langchain.py # 使用 Langchain 转换 Office 文档
│   │   ├── office_to_markdown_mammoth.py   # 使用 Mammoth 转换 Office 文档
│   │   └── pdf_to_markdown.py             # PDF 转 Markdown
│   └── scripts/             # 处理脚本
│       └── build_faiss_index.py  # 构建 Faiss 索引
├── data/                    # 数据目录
│   ├── raw/                # 原始数据
│   ├── processed/          # 处理后的数据
│   └── vectors/            # 向量数据
│       ├── faiss/         # FAISS 索引文件
│       └── metadata/      # 元数据文件
├── tests/                  # 测试代码
│   ├── test_faiss_db.py          # Faiss 数据库测试
│   ├── test_llm_chunker.py       # LLM 分块器测试
│   ├── test_milvus_connection.py # Milvus 连接测试
│   ├── test_ollama_chunker.py    # Ollama 分块器测试
│   ├── test_qwen.py             # Qwen 模型测试
│   └── test_vllm_parser.py      # vLLM 解析器测试
└── logs/                   # 日志文件目录
```

## 安装

1. 克隆项目：

```bash
git clone [项目地址]
cd tk_rag
```

2. 创建并激活 Conda 环境：

```bash
# 创建环境
conda create -n tk_rag python=3.8

# 激活环境
conda activate tk_rag

# 安装依赖
pip install -r requirements.txt
```

3. 配置环境变量：

```bash
# 创建 .env 文件
cp .env.example .env

# 编辑 .env 文件，设置必要的环境变量
```

## 使用方法

1. 文档预处理：

```bash
# 将文档转换为 Markdown 格式
python -m codes.utils.file_to_markdown input_file output_file

# 或使用特定转换器
python -m codes.utils.pdf_to_markdown input.pdf output.md
python -m codes.utils.office_to_markdown_langchain input.docx output.md
```

2. 文本分块：

```bash
# 使用 Markdown 分块器
python -m codes.utils.markdown_chunker input.md

# 或使用 Ollama 分块器（测试）
python -m tests.test_ollama_chunker
```

3. 构建索引：

```bash
# 构建 Faiss 索引
python -m codes.scripts.build_faiss_index
```

4. 运行测试：

```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试
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

## 注意事项

1. 本项目针对 Apple M 系列芯片优化，仅使用 CPU 进行计算
2. 建议使用 Miniconda 管理 Python 环境
3. 确保系统有足够的内存用于向量检索
4. 建议使用 SSD 存储以提高性能

## 文件格式支持

- PDF 文档
- Word 文档 (.docx)
- Excel 文件 (.xlsx)
- PowerPoint 文件 (.pptx)
- 纯文本文件 (.txt)
- Markdown 文件 (.md)

## 开发指南

1. 代码风格遵循 PEP 8 规范
2. 所有新功能都需要编写对应的单元测试
3. 提交代码前请运行完整的测试套件
4. 保持文档的及时更新

## 许可证

[许可证类型]

# MinerU 文档解析服务

这是一个基于 MinerU 的文档解析服务，提供 RESTful API 接口，支持 PDF 和 Office 文档的解析。

## 功能特点

- 支持 PDF 文档解析
- 支持 Office 文档解析（Word、Excel、PPT）
- 自动检测文档类型
- 提供解析后的 Markdown、Layout 和 JSON 格式输出
- RESTful API 接口
- 文件访问服务

## 安装依赖

```bash
pip install -r requirements.txt
```

## 启动服务

```bash
python api.py
```

服务将在 http://localhost:8000 启动。

## API 文档

启动服务后，可以访问 http://localhost:8000/docs 查看完整的 API 文档。

### 主要接口

1. 文档处理接口
    - 路径：`/process`
    - 方法：POST
    - 参数：
        - file: 上传的文件
        - doc_type: 文档类型（可选，默认为 "auto"）
    - 返回：
      ```json
      {
          "success": true,
          "message": "文档处理成功",
          "data": {
              "markdown": {
                  "path": "输出路径",
                  "url": "访问URL"
              },
              "layout": {
                  "path": "输出路径",
                  "url": "访问URL"
              },
              "json": {
                  "path": "输出路径",
                  "url": "访问URL"
              }
          }
      }
      ```

2. 健康检查接口
    - 路径：`/health`
    - 方法：GET
    - 返回：
      ```json
      {
          "status": "healthy"
      }
      ```

### 文件访问

处理后的文件可以通过以下 URL 访问：

- Markdown: `/output/{文档名}/{文档名}.md`
- Layout: `/output/{文档名}/{文档名}_layout.pdf`
- JSON: `/output/{文档名}/{文档名}_middle.json`

## 目录结构

```
.
├── api.py              # API 服务
├── config.py           # 配置文件
├── local_file.py       # PDF 处理
├── ms_office.py        # Office 处理
├── requirements.txt    # 依赖管理
├── datas/             # 数据目录
│   ├── origin_data/   # 原始文件
│   └── output_data/   # 输出文件
└── README.md          # 说明文档
```

## 注意事项

1. 本项目针对 Apple M 系列芯片优化，仅使用 CPU 进行计算
2. 建议使用 Miniconda 管理 Python 环境
3. 确保系统有足够的内存用于向量检索
4. 建议使用 SSD 存储以提高性能

1. 确保 `datas` 目录有足够的写入权限
2. 上传的文件会保存在 `datas/origin_data` 目录
3. 处理结果会保存在 `datas/output_data/{文档名}` 目录
4. 建议使用 HTTPS 在生产环境中部署 