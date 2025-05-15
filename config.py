import logging
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

    }

    # ---------- Ensure Directories ----------
    @classmethod
    def ensure_dirs(cls):
        """确保目录存在"""
        for _, path in cls.PATHS.items():
            os.makedirs(path, exist_ok=True)

    # ---------- Logging Config ----------
    @classmethod
    def get_logger(cls):
        """配置全局日志"""
        LOG_FILE_PATH = os.path.join(cls.PATHS["logs_dir"], "rag_project.log")

        logger = logging.getLogger("RAGProject")
        logger.setLevel(logging.DEBUG)

        if not logger.handlers:  # 避免重复添加 handler
            # 控制台 handle (INFO 级别)
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
            console_handler.setFormatter(console_formatter)

            # 文件 handler (DEBUG 级别)
            file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(filename)s:%(lineno)d - %(message)s",
                                               "%Y-%m-%d %H:%M:%S")
            file_handler.setFormatter(file_formatter)

            # 添加 handler 到 logger
            logger.addHandler(console_handler)
            logger.addHandler(file_handler)

        # 启动提示
        logger.info("Config 初始化完成,日志已配置")
        return logger

    def get_doc_output_dir(config: object, doc_path: str, ) -> dict:
        """
        获取文档的输出目录

        Args:
            doc_path (str): 文档的完整路径
            config (Config): 配置文件

        Returns:
            dict: 包含以下字段的字典：
                - output_path (str): 文档的输出目录（包含 markdown 文件和图片子目录）
                - output_markdown_path (str): 转换生成的 markdown 文件路径
                - output_image_path (str): markdown 文件中图片资源的存储路径
                - output_jsonl_path (str): markdown 文件语义切块后保存的 jsonl 文件路径
        """
        # 提取文档名（去除扩展名）
        doc_name = os.path.splitext(os.path.basename(doc_path))[0]

        # 构建输出目录路径
        output_data_dir = Config.PATHS["processed_data"]

        # 构建输出路径
        output_path = os.path.join(output_data_dir, doc_name)
        output_markdown_path = os.path.join(output_path, f"{doc_name}.md")  # 输出 markdown 文件路径
        output_image_path = os.path.join(output_path, "images")  # 输出 markdown 内的图片路径
        output_jsonl_path = os.path.join(output_path, f"{doc_name}.jsonl")  # markdown 文件切块后保存的 jsonl 文件

        return {
            "output_path": output_path,
            "output_markdown_path": output_markdown_path,
            "output_image_path": output_image_path,
            "output_jsonl_path": output_jsonl_path,
        }


# 初始化配置 (目录和日志)
Config.ensure_dirs()
logger = Config.get_logger()
