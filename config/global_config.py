"""配置模块

提供项目所需的配置信息，包括：
1. 路径配置
2. 模型配置
3. 数据库配置
4. 系统配置
5. API配置
"""

import os
from pathlib import Path

import torch

# 禁用 HuggingFace 警告
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from dotenv import load_dotenv

load_dotenv()


class GlobalConfig:
    """配置类：用于管理项目的所有配置信息"""

    # 环境配置
    ENV = os.getenv("ENV", "dev")  # 环境标识，dev(开发环境), prod(生产环境)

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
        "libreoffice_path": os.getenv("LIBREOFFICE_PATH", "/usr/bin/libreoffice"),
        "mysql_schema_path": str(BASE_DIR / "databases" / "schema" / "mysql_schema_v2.sql"),
        "milvus_flat_schema": str(BASE_DIR / "databases" / "schema" / "milvus_flat_schema_v2.json"),
    }

    # 模型相关配置
    MODEL_PATHS = {
        "embedding": str(MODEL_BASE / "embedding" / "bge-m3"),
        "rerank": str(MODEL_BASE / "rerank" / "bge-reranker-v2-m3"),
    }
    LLM_NAME = os.getenv("LLM_NAME", "qwen")

    LLM_CONFIG = {
        "qwen-turbo-1101": {
            "name": "qwen-turbo-1101",
            "api_key": os.getenv("DASHSCOPE_API_KEY"),
            "base_url": os.getenv("DASHSCOPE_API_BASE_URL"),
            "qpm": 60,  # 每分钟调用次数
            "tpm": 5000000,  # 每分钟Token数限制
            "max_tokens_per_request": 4000,  # 单次请求最大Token数
            "retry_attempts": 5,  # 重试次数
            "retry_delay_base": 2,  # 重试延迟基数
            "retry_delay_max": 60,  # 最大重试延迟
        },
        "qwen2.5-72b-instruct": {
            "name": "qwen2.5-72b-instruct",
            "api_key": os.getenv("DASHSCOPE_API_KEY"),
            "base_url": os.getenv("DASHSCOPE_API_BASE_URL"),
            "qpm": 1200,  # 每分钟调用次数
            "tpm": 1000000,  # 每分钟Token数限制
            "max_tokens_per_request": 4000,  # 单次请求最大Token数
            "retry_attempts": 5,  # 重试次数
            "retry_delay_base": 2,  # 重试延迟基数
            "retry_delay_max": 60,  # 最大重试延迟
        },
        "qwen2.5-32b-instruct": {
            "name": "qwen2.5-32b-instruct",
            "api_key": os.getenv("DASHSCOPE_API_KEY"),
            "base_url": os.getenv("DASHSCOPE_API_BASE_URL"),
            "qpm": 1200,  # 每分钟调用次数
            "tpm": 1000000,  # 每分钟Token数限制
            "max_tokens_per_request": 4000,  # 单次请求最大Token数
            "retry_attempts": 5,  # 重试次数
            "retry_delay_base": 2,  # 重试延迟基数
            "retry_delay_max": 60,  # 最大重试延迟
        },
        "pangu": {},
    }

    @classmethod
    def get_llm_config(cls, model_name: str | None = None) -> dict:
        """获取指定模型的配置"""
        model_name = model_name or cls.LLM_NAME
        if model_name not in cls.LLM_CONFIG:
            raise ValueError(f"不支持的模型: {model_name}")
        return cls.LLM_CONFIG[model_name]

    @classmethod
    def get_current_llm_config(cls) -> dict:
        """获取当前使用的模型配置"""
        return cls.get_llm_config(cls.LLM_NAME)

    # 文件处理配置
    SUPPORTED_FILE_TYPES = {
        "all": [".doc", ".docx", ".ppt", ".pptx", ".pdf", ".txt", ".xls", ".xlsx", ".csv"],
        "libreoffice": [".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".csv"],
    }

    FILE_STATUS = {
        "normal": {
            "uploaded": "待处理",
            "parsed": "处理中",
            "merged": "处理中",
            "chunked": "处理中",
            "splited": "处理完成",
        },
        "error": {
            "parse_failed": "解析失败",
            "merge_failed": "处理失败",
            "chunk_failed": "切块失败",
            "split_failed": "切页失败",
        },
    }
    FILE_MAX_SIZE = 50  # Mb

    # 状态同步关键状态点定义
    STATUS_SYNC_MILESTONES = {
        "layout_ready": "parsed",  # MinerU 解析完成, 可以获取 layout 版面 PDF
        "fully_processed": "splited",  # 全文完全处理完成, 可以获取所有信息
        "processing_failed": "failed",  # 处理失败, 前端需要显示错误状态
    }

    # 需要同步到外部系统的状态映射
    EXTERNAL_STATUS_MAPPING = {
        "parsed": "layout_ready",  # 内部状态 -> 外部状态
        "splited": "fully_processed",  # 内部状态 -> 外部状态
        # 失败状态映射
        "parse_failed": "processing_failed",  # 解析失败
        "merge_failed": "processing_failed",  # 合并失败
        "chunk_failed": "processing_failed",  # 切块失败
        "split_failed": "processing_failed",  # 切页失败
    }

    # 失败状态集合(用于快速判断是否为失败状态)
    FAILURE_STATUSES = {"parse_failed", "merge_failed", "chunk_failed", "split_failed"}

    # 禁止字符集：Windows + 控制字符（包括不可打印ASCII），保持全平台兼容
    UNSUPPORTED_FILENAME_CHARS = set(
        '<>:"/\\|?*' + "".join(chr(c) for c in range(0x00, 0x20))  # 控制字符
    )

    # GPU 配置
    CUDA_DEVICE_ID = os.getenv("CUDA_DEVICE_ID", "0")  # 默认使用 GPU 0
    DEVICE = f"cuda:{CUDA_DEVICE_ID}" if torch.cuda.is_available() else ("mps" if torch.mps.is_available() else "cpu")
    # 模型显存占用配置
    GPU_CONFIG={
        "device_id": int(CUDA_DEVICE_ID),
        "rerank_max_memory": "16GiB",     # Rerank模型最大显存
    }
    

    # 数据库配置 - 根据环境动态配置
    # 数据库名称
    DB_NAME = os.getenv("DB_NAME", "tk_rag_dev" if ENV == "dev" else "tk_rag")

    # MySQL配置
    MYSQL_CONFIG = {
        "host": os.getenv("MYSQL_HOST", "192.168.6.202" if ENV == "dev" else "localhost"),
        "user": os.getenv("MYSQL_USER"),
        "passwd": os.getenv("MYSQL_PASSWORD"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "charset": "utf8mb4",
        "database": DB_NAME,
        "file_info_table": "doc_info",  # 文件信息表
        "segment_info_table": "segment_info",  # 段落信息表
        "permission_info_table": "permission_doc_link",  # 权限信息表
        "doc_page_info_table": "doc_page_info",  # 文档切页信息表
        "chat_sessions_table": "chat_sessions",  # 聊天会话表
        "chat_messages_table": "chat_messages",  # 聊天消息表
    }

    # Milvus配置FLAT 集合
    MILVUS_CONFIG = {
        "uri": os.getenv("MILVUS_URI"),
        "host": os.getenv("MILVUS_HOST"),
        "port": int(os.getenv("MILVUS_PORT")),
        "token": os.getenv("MILVUS_TOKEN"),
        "db_name": DB_NAME,
        "collection_name": "rag_flat",  # 更新为新的 FLAT collection
        "vector_field": "seg_dense_vector",  # 新字段名
        "vector_dim": 1024,
        "output_fields": ["doc_id", "seg_id", "seg_content", "seg_type", "seg_page_idx", "created_at"],
        "search_batch_size": 1000,
        "index_params": {
            "field_name": "seg_dense_vector",  # 新字段名
            "index_type": "FLAT",  # 更新为 FLAT 索引
            "metric_type": "IP",
            "params": {},  # FLAT 不需要额外的索引参数
        },
        "search_params": {
            "top_k": 20,  # 返回结果数量
            "round_decimal": 8,  # 分数精度，提高结果稳定性
            "consistency_level": "STRONG",  # 一致性级别
        },
    }

    MYSQL_FIELD = {"max_path_len": 1000, "max_name_len": 500}

    SEGMENT_CONFIG = {
        "batch_size": 10,  # 每批处理的记录数
        "max_text_length": 1000,  # 最大文本长度
        "memory_limit": 1024,  # 内存限制（MB）
        "vector_batch_size": 10,  # 向量生成的批处理大小
    }

    # 提示词模板
    PROMPT_TEMPLATE = {
        "table_summary_v2": {
            "prompt_file": "prompts/table_summary.j2",
            "model": LLM_NAME,
            "temperature": 0,
            "top_p": 0.9,  # 默认值
            "max_tokens": 4096,
            "stop": ["[END]"],
        },
        # "rag_system_prompt": {"prompt_file": "prompts/rag_system_prompt.j2", "temperature": 0.1, "top_p": 0.9},
        "rag_system_prompt": {"prompt_file": "prompts/rag_system_prompt_v2.j2", "temperature": 0.1, "top_p": 0.9},
        "query_rewrite": {"prompt_file": "prompts/query_rewrite_prompt.j2", "temperature": 0.3, "max_tokens": 200},
    }

    # 状态同步配置
    STATUS_SYNC_CONFIG = {
        "enabled": os.getenv("STATUS_SYNC_ENABLED", "true").lower() == "true",  # 是否启用状态同步
        # "base_url": os.getenv("STATUS_SYNC_BASE_URL"),  # 状态同步接口基础URL
        "timeout": int(os.getenv("STATUS_SYNC_TIMEOUT", "10")),  # 状态同步请求超时时间（秒）
        "retry_attempts": int(os.getenv("STATUS_SYNC_RETRY_ATTEMPTS", "3")),  # 状态同步重试次数
        "retry_delay": float(os.getenv("STATUS_SYNC_RETRY_DELAY", "1.0")),  # 状态同步重试延迟（秒）
        "api_path": "/cbm/api/v5/knowledgeFile/parseStatusUpdated",  # 状态更新接口路径
    }


if __name__ == "__main__":
    # 打印当前配置
    print(f"Environment: {GlobalConfig.ENV}")
    print(f"Base Dir: {GlobalConfig.BASE_DIR}")
    print(f"Device: {GlobalConfig.DEVICE}")
    print(f"Database Name: {GlobalConfig.DB_NAME}")
    print(f"MySQL Host: {GlobalConfig.MYSQL_CONFIG['host']}")
    print(f"Milvus Host: {GlobalConfig.MILVUS_CONFIG['host']}")
    print("\nPaths:")
    for name, path in GlobalConfig.PATHS.items():
        print(f"  {name}: {path}")
    print("\nModel Paths:")
    for name, path in GlobalConfig.MODEL_PATHS.items():
        print(f"  {name}: {path}")
