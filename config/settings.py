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
    
    BASE_DIR = Path(__file__).parent.absolute().parent
    
    MODEL_BASE = BASE_DIR / "models"  # 模型根目录
        
    PATHS = {
        "origin_data": str(BASE_DIR / "datas/raw"),
        "processed_data": str(BASE_DIR / "datas/processed"),
        "translated_data": str(BASE_DIR / "datas/translated"),
        "model_base": str(MODEL_BASE),
        "log_dir": str(BASE_DIR / "logs")
    }
    
    # ---------- Model Config ----------
    MODEL_PATHS = {
        "embedding": str(MODEL_BASE / "bge-m3"),
        "llm": str(MODEL_BASE / "Qwen2.5-14B-DeepSeek-R1-1M"),
        "rerank": str(MODEL_BASE / "bge-reranker-v2-m3")
    }
    
    # ---------- File Processing Config ----------
    SUPPORTED_FILE_TYPES = {
        "all": ['.doc', '.docx', '.ppt', '.pptx', '.pdf'],
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
        "collection_name": "tk_rag",
        "vector_field": "vector",
        "vector_dim": 1024,
        "output_fields": ["segment_id", "doc_id", "document_name", "summary_text", "type", "page_idx", "principal_ids","metadata"],
        "index_params": {
            "field_name": "vector",
            "index_type": "IVF_FLAT",
            "metric_type": "IP",
            "params": {"nlist": 1024},
        },
        "search_params": {
            "nprobe": 10
        }
    }
    
    MYSQL_CONFIG = {
        "host": "localhost",
        "user": "root",
        "password": "Tk@654321",
        "charset": "utf8mb4",
        "database": "rag_db",
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
