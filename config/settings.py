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
        "model_base": str(MODEL_BASE),
        "log_dir": str(BASE_DIR / "logs"),
        "libreoffice_path": "/usr/bin/libreoffice",
        "tmp_dir": str(BASE_DIR / "tmp"),  # 临时目录
    }

    # ---------- Model Config ----------
    MODEL_PATHS = {
        "embedding": str(MODEL_BASE / "bge-m3"),
        # "llm": str(MODEL_BASE / "Qwen2.5-14B-DeepSeek-R1-1M"),
        "llm": str(MODEL_BASE / "Qwen2.5-7B-Instruct-1M"),
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
        "output_fields": ["segment_id", "doc_id", "document_name", "summary_text", "type", "page_idx", "principal_ids",
                          "metadata"],
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
        "file_info_table": "file_info",
        "segment_info_table": "chunk_info",
        "permission_info_table": "permission_info",
    }

    # VLLM 配置
    VLLM_CONFIG = {
        # 基础推理配置
        "tensor_parallel_size": 1,
        "gpu_memory_utilization": 0.9,
        "trust_remote_code": True,  # 信任远程代码
        "dtype": "bfloat16",    # 使用 bfloat16 以减少显存使用
        "max_model_len": 4096,  # 限制最大序列长度
        "enforce_eager": True,  # 禁用 Torch 的 Lazy 模式，使用 eager 模式以提高性能
        "tokenizer_mode": "auto",   # 自动选择分词器模式
        "disable_custom_all_reduce": True,  # 禁用自定义 all_reduce

        # 摘要生成采样配置
        "summary_temperature": 0.3,
        "summary_max_tokens": 1024,

        # RAG 生成采样配置
        "rag_temperature": 0.7,
        "rag_top_p": 0.95,
        "rag_max_tokens": 4096,
        "rag_presence_penalty": 0.1,
        "rag_frequency_penalty": 0.1,
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
