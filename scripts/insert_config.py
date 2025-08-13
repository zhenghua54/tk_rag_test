#!/usr/bin/env python3
"""
RAGBench文档插入配置文件
"""

import os
from pathlib import Path

# Dify配置
DIFY_CONFIG = {
    "base_url": os.getenv("DIFY_BASE_URL", "http://192.168.31.205"),
    "api_key": os.getenv("DIFY_API_KEY", "dataset-L7pHf6iaAwImkw5601pv3N2u"),
}

# RAGBench配置
RAGBENCH_CONFIG = {
    "data_path": os.getenv("RAGBENCH_PATH", "data/ragbench"),
    "max_documents_per_dataset": int(os.getenv("MAX_DOCS_PER_DATASET", "50")),
    "upload_delay": float(os.getenv("UPLOAD_DELAY", "0.2")),  # 秒
    "temp_dir": "temp_docs",
    "add_test_docs_for_empty_kb": True,  # 为空知识库添加测试文档以激活配置
    "test_docs_count": 2  # 测试文档数量
}

# 数据集配置
DATASET_CONFIGS = {
    "techqa": {
        "description": "Technical questions and answers dataset",
        "priority": 1
    },
    "tatqa": {
        "description": "Table and text question answering dataset", 
        "priority": 1
    },
    "pubmedqa": {
        "description": "Biomedical question answering dataset",
        "priority": 2
    },
    "msmarco": {
        "description": "Microsoft Machine Reading Comprehension dataset",
        "priority": 1
    },
    "hotpotqa": {
        "description": "Multi-hop question answering dataset",
        "priority": 2
    },
    "hagrid": {
        "description": "Hate speech detection dataset",
        "priority": 3  # 已有文档，优先级低
    },
    "finqa": {
        "description": "Financial question answering dataset",
        "priority": 2
    },
    "expertqa": {
        "description": "Expert-level question answering dataset",
        "priority": 2
    },
    "emanual": {
        "description": "Electronic manual dataset",
        "priority": 3  # 已有文档，优先级低
    },
    "delucionqa": {
        "description": "Delusion question answering dataset",
        "priority": 3  # 已有文档，优先级低
    },
    "cuad": {
        "description": "Contract Understanding Atticus Dataset",
        "priority": 1
    },
    "covidqa": {
        "description": "COVID-19 question answering dataset",
        "priority": 1
    }
}

# 文件路径配置
PATHS = {
    "scripts_dir": Path(__file__).parent,
    "project_root": Path(__file__).parent.parent,
    "ragbench_data": Path(RAGBENCH_CONFIG["data_path"]),
    "temp_dir": RAGBENCH_CONFIG["temp_dir"]
}

# 上传配置 - 默认模型配置
UPLOAD_CONFIG = {
    "indexing_technique": "high_quality",
    "process_rule": {
        "mode": "automatic"
    },
    "file_extension": ".txt",
    "encoding": "utf-8"
}

# 默认模型配置
DEFAULT_MODELS = {
    # 嵌入模型配置
    "embedding_model": {
        "provider": "siliconflow",  # 提供商
        "model": "BAAI/bge-m3",     # 模型名称
        "dimensions": 1024,          # 向量维度
        "max_tokens": 8192           # 最大token数
    },
    
    # 检索模型配置 - 混合检索
    "retrieval_model": {
        "search_method": "hybrid_search",  # 混合检索
        "reranking_enable": True,          # 启用重排序
        "reranking_mode": "rerank",        # 重排序模式
        "reranking_model": {
            "reranking_provider_name": "tongyi",      # 重排序提供商
            "reranking_model_name": "gte-rerank"      # 重排序模型
        },
        "weights": {
            "keyword_search": 0.3,         # 关键词搜索权重
            "semantic_search": 0.7         # 语义搜索权重
        },
        "top_k": 10,                      # 返回结果数量
        "score_threshold_enabled": True,   # 启用分数阈值
        "score_threshold": 0.5             # 分数阈值
    },
    
    # 索引配置
    "indexing_config": {
        "chunk_size": 500,                # 分块大小
        "chunk_overlap": 50,              # 分块重叠
        "separator": "\n",                # 分隔符
        "max_tokens": 500                 # 最大token数
    }
}

# 处理规则配置
PROCESS_RULES = {
    "mode": "custom",                     # 自定义模式
    "rules": {
        "pre_processing_rules": [
            {
                "id": "remove_extra_spaces",
                "enabled": True,
                "name": "移除多余空格"
            },
            {
                "id": "remove_urls_emails",
                "enabled": True,
                "name": "移除URL和邮箱"
            },
            {
                "id": "normalize_whitespace",
                "enabled": True,
                "name": "标准化空白字符"
            }
        ],
        "segmentation": {
            "separator": "\n\n",          # 分段分隔符
            "max_tokens": 500,            # 最大token数
            "chunk_size": 500,            # 分块大小
            "chunk_overlap": 50           # 分块重叠
        }
    }
}
