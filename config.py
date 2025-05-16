import os

import torch

"""
配置类：用于初始化项目的路径配置、模型路径与模型加载设置等。
"""

# 禁用 HuggingFace 警告:fork 后 tokenizer 的多进程是风险操作,huggingface 会自动禁用 tokenizer 内部的多进程
os.environ["TOKENIZERS_PARALLELISM"] = "false"


class Config:
    # ---------- ENV Config ----------
    ENV = "dev"

    # ---------- Project Paths ----------
    if ENV == "dev":
        # BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        # MODEL_PATH = os.path.join(BASE_DIR, "models")
        BASE_DIR = "/Users/jason/PycharmProjects/tk_rag"  # 临时指定项目根目录
        MODEL_BASE = "/Users/jason/models"  # 临时指定模型根目录

    PATHS = {
        "origin_data": os.path.join(BASE_DIR, "datas/raw"),
        "processed_data": os.path.join(BASE_DIR, "datas/processed"),
        "translated_data": os.path.join(BASE_DIR, "datas/translated"),
        "model_base": MODEL_BASE,
        "logs_dir": os.path.join(BASE_DIR, "logs")
    }

    # ---------- Model Config ----------
    MODEL_PATHS = {
        "embedding": os.path.join(MODEL_BASE, "BAAI/bge-m3"),
        "llm": os.path.join(MODEL_BASE, "Qwen/Qwen2.5-7B"),
        "rerank": os.path.join(MODEL_BASE, "BAAI/bge-reranker-v2-m3")
    }

    OLLAMA_CONFIG = {
        "url": "http://localhost:11434",
        "model": "qwen2.5:latest"
    }

    # ---------- File Processing Config ----------
    MINERU_CONFIG = {  # MinerU 工具处理文件时的格式要求（针对 pdf 和 office 文件
        "pdf": {
            "output_format": "txt",  # 输出为纯文本格式
            "encoding": "utf-8",  # 使用 utf-8 编码
        },
        "office": {
            "output_format": "txt",  # 输出为纯文本格式
            "encoding": "utf-8",  # 使用 utf-8 编码
        }
    }

    SUPPORTED_FILE_TYPES = {  # 支持的文件类型映射（用于文件分类）
        "all": ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.odp', '.pdf'],
        "pdf": [".pdf"],
        "office": [".doc", ".docx", ".ppt", ".pptx"]
    }
    # ---------- System Config ----------
    DEVICE = "cuda" if torch.cuda.is_available() else ("mps" if torch.mps.is_available() else "cpu")

    # ---------- Database Config ----------
    MILVUS_CONFIG = {
        "uri": "http://milvus.wumingxing.xyz:19530/",
        "host": "milvus.wumingxing.xyz",
        "port": 19530,
        "token": "root:Milvus",
        "db_name": "tk_db",
        "collection_name": "enterprise_doc_vectors",
        "vector_field": "vector",  # 向量字段名
        "vector_dim": 1024,  # 向量维度
        "output_fields": ["title", "document_source", "partment", "role", "doc_id"],  # 检索结果输出字段
        "index_params": {  # 检索参数配置
            "field_name": "vector",
            "index_type": "IVF_FLAT",
            "metric_type": "IP",  # (内积)余弦相似度
            "params": {"nlist": 1024},
        },
        "search_params": {  # 搜索配置参数
            "nprobe": 10
        },
        "fields": {  # 集合字段配置
            "id": {"datatype": "INT64", "is_primary": True},
            "vector": {"datatype": "FLOAT_VECTOR", "dim": 1024},
            "text_chunk": {"datatype": "VARCHAR", "max_length": 10000},
            "title": {"datatype": "VARCHAR", "max_length": 10000},
            "document_source": {"datatype": "VARCHAR", "max_length": 10000},
            "partment": {"datatype": "VARCHAR", "max_length": 10000},
            "role": {"datatype": "VARCHAR", "max_length": 10000},
            "doc_id": {"datatype": "VARCHAR", "max_length": 10000}
        }
    }

    # ---------- MySQL Config ----------
    MYSQL_CONFIG = {
        "host": "localhost",
        "user": "root",
        "password": "Nihao123!",
        "charset": "utf8mb4",
        "database": "rag_db",
        "fields": ["doc_id",  # 使用 SHA256 哈希值作为 doc_id，确保文档唯一性
                   "source_document_name",  # 文件名通常不超过 255 个字符
                   "source_document_type",  # 文档类型
                   "source_document_path",  # 文档路径
                   "source_document_pdf_path"   # 文档转换为 PDF 的路径
                   "source_document_json_path",  # 文档 json 路径
                   "source_document_markdown_path",  # 文档 markdown 路径
                   "source_document_images_path"]  # 文档图片路径
    }

    # ---------- Ensure Directories ----------
    @classmethod
    def ensure_dirs(cls):
        """确保目录存在"""
        for _, path in cls.PATHS.items():
            os.makedirs(path, exist_ok=True)



# 初始化配置 (目录和日志)
Config.ensure_dirs()