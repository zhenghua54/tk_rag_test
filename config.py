"""配置模块

提供项目所需的配置信息，包括：
1. 路径配置
2. 模型配置
3. 数据库配置
4. 系统配置
"""

import os
import torch
from pathlib import Path

# 禁用 HuggingFace 警告
os.environ["TOKENIZERS_PARALLELISM"] = "false"


class Config:
    """配置类：用于管理项目的所有配置信息"""
    
    # ---------- Project Paths ----------
    BASE_DIR = Path(__file__).parent.absolute()
    MODEL_BASE = Path("/data/models")  # 模型根目录
        
    PATHS = {
        "origin_data": str(BASE_DIR / "datas/raw"),
        "processed_data": str(BASE_DIR / "datas/processed"),
        "translated_data": str(BASE_DIR / "datas/translated"),
        "model_base": str(MODEL_BASE),
        "log_dir": str(BASE_DIR / "logs")
    }
    
    # ---------- Model Config ----------
    MODEL_PATHS = {
        "embedding": str(MODEL_BASE / "BAAI/bge-m3"),
        "llm": str(MODEL_BASE / "Qwen/Qwen2.5-7B"),
        "rerank": str(MODEL_BASE / "BAAI/bge-reranker-v2-m3")
    }
    
    # ---------- File Processing Config ----------
    MINERU_CONFIG = {
        "pdf": {
            "output_format": "txt",
            "encoding": "utf-8",
        },
        "office": {
            "output_format": "txt",
            "encoding": "utf-8",
        }
    }
    
    SUPPORTED_FILE_TYPES = {
        "all": ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.odp', '.pdf'],
        "libreoffice": ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'],
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
        "collection_name": "tk_rag",
        "vector_field": "vector",
        "vector_dim": 1024,
        "output_fields": ["title", "document_source", "partment", "role", "doc_id"],
        "index_params": {
            "field_name": "vector",
            "index_type": "IVF_FLAT",
            "metric_type": "IP",
            "params": {"nlist": 1024},
        },
        "search_params": {
            "nprobe": 10
        },
        "fields": {
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
    
    MYSQL_CONFIG = {
        "host": "localhost",
        "user": "root",
        "password": "Tk@654321",
        "charset": "utf8mb4",
        "database": "rag_db",
    }
    
    @classmethod
    def ensure_dirs(cls) -> None:
        """确保必要的目录存在"""
        for _, path in cls.PATHS.items():
            os.makedirs(path, exist_ok=True)


# 初始化配置
Config.ensure_dirs()

if __name__ == "__main__":
    # 打印当前配置
    print(f"Device: {Config.DEVICE}")
    print("\nPaths:")
    for name, path in Config.PATHS.items():
        print(f"  {name}: {path}")
    print("\nModel Paths:")
    for name, path in Config.MODEL_PATHS.items():
        print(f"  {name}: {path}")
