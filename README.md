# TK RAG 项目

基于 RAG (Retrieval-Augmented Generation) 技术构建的企业知识库问答系统。

## 项目结构

```
tk_rag/
├── src/                          # 源代码目录
│   ├── api/                      # API 接口
│   │   ├── libreoffice_api.py    # 文档转换 API
│   │   └── mineru_api.py         # PDF 解析 API
│   ├── core/                     # 核心业务逻辑
│   │   ├── document/             # 文档处理
│   │   ├── llm/                  # 大语言模型
│   │   └── rag/                  # RAG 实现
│   ├── database/                 # 数据库操作
│   │   ├── mysql/                # MySQL 相关
│   │   └── milvus/               # Milvus 向量数据库
│   └── utils/                    # 工具函数
│       ├── common/               # 通用工具
│       ├── file/                 # 文件操作
│       └── logger/               # 日志工具
├── tests/                        # 测试代码
├── datas/                        # 数据目录
│   ├── raw/                      # 原始文档
│   ├── processed/                # 处理后的文档
│   └── translated/               # 转换后的文档
├── models/                       # 模型目录
├── logs/                         # 日志目录
├── config.py                     # 配置文件
├── requirements.txt              # 依赖包
└── README.md                     # 项目文档
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

1. 克隆项目
```bash
git clone http://192.168.31.71:18080/wumingxing/tk_rag.git
cd tk_rag
```

2. 创建并激活 Conda 环境：

```bash
# 创建环境
conda create -n tk_rag python=3.10

# 激活环境
conda activate tk_rag

# 安装依赖
pip install -r requirements.txt -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
```

3. 配置数据库
```python
# config.py
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "your_password",
    "charset": "utf8mb4",
    "database": "rag_db",
}

MILVUS_CONFIG = {
    "uri": "http://localhost:19530/",
    "host": "localhost",
    "port": 19530,
    "token": "your_token",
    "db_name": "default",
    "collection_name": "tk_rag",
}
```

4. 下载模型
```bash
python download_models.py
```

5. 安装 Libreoffice
```bash
sudo apt-get install libreoffice
```

## 使用说明

1. 文档上传
```python
from src.utils.file_toolkit _upload import upload_files

# 上传文档
file_infos = upload_files("/path/to/your/documents")
```

2. 文档处理
```python
from src.utils.file_toolkit _translate import translate_file
from src.utils.file_toolkit _parse import parse_file_to_db

# 转换为 PDF
translate_file()

# 解析文档
parse_file_to_db()
```

3. 启动服务
```bash
streamlit run app_streamlit.py
```

## 常见问题

1. 模型下载失败
   - 检查网络连接
   - 确认模型路径配置
   - 尝试手动下载

2. 数据库连接错误
   - 检查数据库配置
   - 确认数据库服务运行状态
   - 验证用户权限

## 更新日志

### v0.1.0 (2024-03-xx)
- 初始版本发布
- 基础文档处理功能
- RAG 问答系统实现




## 联系方式

- 项目维护者：[Your Name]
- 邮箱：[your.email@example.com] 