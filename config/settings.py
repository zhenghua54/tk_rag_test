"""配置模块

提供项目所需的配置信息，包括：
1. 路径配置
2. 模型配置
3. 数据库配置
4. 系统配置
5. API配置
"""

import os
import torch
from pathlib import Path

# 禁用 HuggingFace 警告
os.environ["TOKENIZERS_PARALLELISM"] = "false"


class Config:
    """配置类：用于管理项目的所有配置信息"""

    # ---------- Project Paths ----------

    BASE_DIR = Path(__file__).parent.absolute().parent

    MODEL_BASE = BASE_DIR / "models"  # 模型根目录

    PATHS = {
        "origin_data": str(BASE_DIR / "datas/raw"),
        "processed_data": str(BASE_DIR / "datas/processed"),
        "model_base": str(MODEL_BASE),
        "log_dir": str(BASE_DIR / "logs"),
        "libreoffice_path": "/usr/bin/libreoffice",
    }

    # ---------- API Config ----------
    API_VERSION = "v1"
    API_PREFIX = f"/api/{API_VERSION}"
    USE_MOCK = True  # 是否使用mock服务
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 文件大小限制 (50MB)

    # ---------- Model Config ----------
    MODEL_PATHS = {
        "embedding": str(MODEL_BASE / "bge-m3"),
        "llm": str(MODEL_BASE / "Qwen2.5-7B-Instruct-1M"),
        "rerank": str(MODEL_BASE / "bge-reranker-v2-m3")
    }

    # ---------- File Processing Config ----------
    SUPPORTED_FILE_TYPES = {
        "all": ['.doc', '.docx', '.ppt', '.pptx', '.pdf', '.txt'],
        "libreoffice": ['.doc', '.docx', '.ppt', '.pptx'],
    }

    # ---------- System Config ----------
    DEVICE = "cuda" if torch.cuda.is_available() else ("mps" if torch.mps.is_available() else "cpu")

    # ---------- Database Config ----------
    MILVUS_CONFIG = {
        "uri": "http://localhost:19530/",
        "host": "localhost",
        "port": 19530,
        "token": "root:Milvus",
        "db_name": "default",
        "collection_name": "rag_collection",
        "schema_path": str(BASE_DIR / "scripts" / "init" / "schema" / "milvus_schema.json"),
        "vector_field": "vector",
        "vector_dim": 1024,
        "output_fields": ["segment_id", "doc_id", "document_name", "summary_text", "type", "page_idx", "principal_ids",
                          "metadata"],
        "index_params": {
            "field_name": "vector",
            "index_type": "IVF_FLAT",
            "metric_type": "IP",
            "params": {"nlist": 1024},
        },
        "search_params": {
            "nprobe": 50
        }
    }

    MYSQL_CONFIG = {
        "host": "localhost",
        "user": "root",
        "password": "Tk@654321",
        "charset": "utf8mb4",
        "database": "rag_db",
        "file_info_table": "doc_info",
        "segment_info_table": "segment_info",
        "permission_info_table": "permission_info",
        "schema_path": str(BASE_DIR / "scripts" / "init" / "schema" / "mysql_schema.sql"),
    }
    
    # ---------- ES Config ----------
    ES_CONFIG = {
        "host": "http://localhost:9200",  # ES 服务器地址
        "timeout": 30,  # 请求超时时间（秒）
        "index_name": "rag_index",  # ES 索引（数据库）名称
        "schema_path": str(BASE_DIR / "scripts" / "init" / "schema" / "es_schema.json"),  # schema 配置文件路径
        # 安全配置
        "username": os.getenv("ES_USER"),  # ES 用户名
        "password": os.getenv("ES_PASSWORD"),  # ES 密码
        "verify_certs": False  # 是否验证证书
    }

    # ---------- BM25 Config ----------
    BM25_CONFIG = {
        "batch_size": 1000,  # 每批处理的文档数量
        "max_docs": 10000,   # 最大文档数量
        "memory_limit": 1024  # 内存限制（MB）
    }

    # ---------- Segment Config ----------
    SEGMENT_CONFIG = {
        "batch_size": 10,  # 每批处理的记录数
        "max_text_length": 1000,  # 最大文本长度
        "memory_limit": 1024,  # 内存限制（MB）
        "vector_batch_size": 10  # 向量生成的批处理大小
    }

if __name__ == "__main__":
    # 打印当前配置
    print(f"Base Dir: {Config.BASE_DIR}")
    print(f"Device: {Config.DEVICE}")
    print("\nPaths:")
    for name, path in Config.PATHS.items():
        print(f"  {name}: {path}")
    print("\nModel Paths:")
    for name, path in Config.MODEL_PATHS.items():
        print(f"  {name}: {path}")
