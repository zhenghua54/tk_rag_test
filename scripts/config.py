#!/usr/bin/env python3
"""
配置文件 - RAGBench导入Dify知识库
"""

import os
from pathlib import Path

# Dify配置
DIFY_CONFIG = {
    "base_url": os.getenv("DIFY_BASE_URL", "http://192.168.31.205"),
    "api_key": os.getenv("DIFY_API_KEY", "dataset-L7pHf6iaAwImkw5601pv3N2u"),
    "embedding_model": "text-embedding-ada-002",
    "language": "en",
    "retrieval_model": "keyword_search"
}

# RAGBench配置
RAGBENCH_CONFIG = {
    "data_path": os.getenv("RAGBENCH_PATH", "data/ragbench"),
    "max_documents_per_dataset": 100,  # 每个数据集最多上传的文档数量
    "upload_delay": 0.1,  # 上传文档之间的延迟（秒）
}

# 数据集配置
DATASET_CONFIGS = {
    "techqa": {
        "description": "Technical questions and answers dataset",
        "source": "Technical QA dataset for software and technology questions"
    },
    "tatqa": {
        "description": "Table and text question answering dataset", 
        "source": "Dataset for questions requiring both table and text understanding"
    },
    "pubmedqa": {
        "description": "Biomedical question answering dataset",
        "source": "Biomedical literature question answering dataset"
    },
    "msmarco": {
        "description": "Microsoft Machine Reading Comprehension dataset",
        "source": "Large-scale machine reading comprehension dataset"
    },
    "hotpotqa": {
        "description": "Multi-hop question answering dataset",
        "source": "Multi-hop reasoning question answering dataset"
    },
    "hagrid": {
        "description": "Hate speech detection dataset",
        "source": "Hate speech and offensive language detection dataset"
    },
    "finqa": {
        "description": "Financial question answering dataset",
        "source": "Financial numerical reasoning dataset"
    },
    "expertqa": {
        "description": "Expert-level question answering dataset",
        "source": "Expert-level knowledge question answering dataset"
    },
    "emanual": {
        "description": "Electronic manual dataset",
        "source": "Electronic product manual dataset"
    },
    "delucionqa": {
        "description": "Delusion question answering dataset",
        "source": "Delusion detection and question answering dataset"
    },
    "cuad": {
        "description": "Contract Understanding Atticus Dataset",
        "source": "Legal contract understanding and question answering dataset"
    },
    "covidqa": {
        "description": "COVID-19 question answering dataset",
        "source": "COVID-19 related question answering dataset"
    }
}

# 文件路径配置
PATHS = {
    "scripts_dir": Path(__file__).parent,
    "project_root": Path(__file__).parent.parent,
    "ragbench_data": Path(RAGBENCH_CONFIG["data_path"]),
    "temp_dir": "/tmp"
}

# 日志配置
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(levelname)s - %(message)s",
    "file": "import_ragbench.log"
}
