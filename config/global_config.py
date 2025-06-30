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


class GlobalConfig:
    """配置类：用于管理项目的所有配置信息"""
    # API配置
    API_TITLE = "rag Demo API"
    API_DESCRIPTION = "RAG系统API文档"
    API_VERSION = "v1"
    API_PREFIX = f"/api/{API_VERSION}"
    USE_MOCK = False  # 是否使用 Mock 数据

    # 项目目录配置
    BASE_DIR = Path(__file__).parent.absolute().parent
    MODEL_BASE = BASE_DIR / "models"  # 模型根目录
    PATHS = {
        "origin_data": str(BASE_DIR / "datas/raw"),
        "processed_data": str(BASE_DIR / "datas/processed"),
        "model_base": str(MODEL_BASE),
        "log_dir": str(BASE_DIR / "logs"),
        "libreoffice_path": "/usr/bin/libreoffice",
        "mysql_schema_path": str(BASE_DIR / "databases" / "schema" / "mysql_schema.sql"),
        "milvus_schema_path": str(BASE_DIR / "databases" / "schema" / "milvus_schema.json"),
        "milvus_hybrid_schema_path": str(BASE_DIR / "databases" / "schema" / "milvus_hybrid_schema.json"),
        "es_schema_path": str(BASE_DIR / "databases" / "schema" / "es_schema.json"),  # schema 配置文件路径
    }

    # 模型相关配置
    MODEL_PATHS = {
        "embedding": str(MODEL_BASE / "embedding" / "bge-m3"),
        "rerank": str(MODEL_BASE / "reranker" / "bge-reranker-v2-m3")
    }
    LLM_NAME = "qwen-turbo-1101"

    # 文件处理配置
    SUPPORTED_FILE_TYPES = {
        "all": ['.doc', '.docx', '.ppt', '.pptx', '.pdf', '.txt'],
        "libreoffice": ['.doc', '.docx', '.ppt', '.pptx'],
    }
    # FILE_STATUS = {
    #     "normal": ["uploaded", "parsed", "merged", "chunked", "splited"],
    #     "error": ["parse_failed", "merge_failed", "chunk_failed", "split_failed"],
    # }
    FILE_STATUS = {
        "normal": {
            "uploaded": "待处理",
            "parsed": "处理中",
            "merged": "处理中",
            "chunked": "处理中",
            "splited": "处理完成"
        },
        "error": {
            "parse_failed": "解析失败",
            "merge_failed": "处理失败",
            "chunk_failed": "切块失败",
            "split_failed": "切页失败",
        }
    }
    FILE_MAX_SIZE = 50  # Mb

    # 禁止字符集：Windows + 控制字符（包括不可打印ASCII），保持全平台兼容
    UNSUPPORTED_FILENAME_CHARS = set(
        '<>:"/\\|?*' + ''.join(chr(c) for c in range(0x00, 0x20))  # 控制字符
    )

    # 系统相关配置
    DEVICE = "cuda" if torch.cuda.is_available() else ("mps" if torch.mps.is_available() else "cpu")

    # 数据库配置
    DB_NAME = 'tk_rag'
    MILVUS_CONFIG = {
        "uri": "http://localhost:19530/",
        "host": "localhost",
        "port": 19530,
        # "token": "root:Milvus",
        "token": os.getenv("MILVUS_TOKEN"),
        "db_name": DB_NAME,
        "collection_name": "rag_collection",
        "vector_field": "vector",
        "vector_dim": 1024,
        "output_fields": ["seg_id", "seg_parent_id", "doc_id", "seg_content", "seg_type", "permission_ids"],
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
        "user": os.getenv("MYSQL_USER"),
        "passwd": os.getenv("MYSQL_PASSWORD"),
        "port": 3306,
        "charset": "utf8mb4",
        "database": DB_NAME,
        "file_info_table": "doc_info", # 文件信息表
        "segment_info_table": "segment_info", # 段落信息表
        "permission_info_table": "permission_info", # 权限信息表
        "doc_page_info_table": "doc_page_info", # 文档切页信息表
        "chat_sessions_table": "chat_sessions", # 聊天会话表
        "chat_messages_table": "chat_messages", # 聊天消息表
    }
    MYSQL_FIELD = {
        "max_path_len": 1000,
        "max_name_len": 500,
    }

    ES_CONFIG = {
        "host": "http://localhost:9200",  # ES 服务器地址
        "timeout": 30,  # 请求超时时间（秒）
        "index_name": DB_NAME,  # ES 索引（数据库）名称
        "username": os.getenv("ES_USER"),  # ES 用户名
        "password": os.getenv("ES_PASSWORD"),  # ES 密码
        "verify_certs": False  # 是否验证证书
    }

    # 分块配置
    SEGMENT_CONFIG = {
        "batch_size": 10,  # 每批处理的记录数
        "max_text_length": 1000,  # 最大文本长度
        "memory_limit": 1024,  # 内存限制（MB）
        "vector_batch_size": 10  # 向量生成的批处理大小
    }

    # 提示词模板
    PROMPT_TEMPLATE = {
        "table_summary": {
            "prompt_file": "prompts/table_summary_prompt.txt",
            "model": LLM_NAME,
            "temperature": 0.3,
            "max_tokens": 1024
        },
        "text_summary": {
            "prompt_file": "prompts/text_summary_prompt.txt",
            "model": LLM_NAME,
            "temperature": 0.5,
            "max_tokens": 1024
        },
        "rag_system_prompt": {
            "prompt_file": "prompts/rag_system_prompt.j2",
            "temperature": 0.3,
            "top_p": 0.9
        },

    }


if __name__ == "__main__":
    # 打印当前配置
    print(f"Base Dir: {GlobalConfig.BASE_DIR}")
    print(f"Device: {GlobalConfig.DEVICE}")
    print("\nPaths:")
    for name, path in GlobalConfig.PATHS.items():
        print(f"  {name}: {path}")
    print("\nModel Paths:")
    for name, path in GlobalConfig.MODEL_PATHS.items():
        print(f"  {name}: {path}")
