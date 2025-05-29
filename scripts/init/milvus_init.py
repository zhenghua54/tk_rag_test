"""Milvus 数据库初始化脚本"""

import json
from pathlib import Path
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility
from config.settings import Config
from src.utils.common.logger import logger

def load_schema():
    """加载 Milvus schema 配置"""
    schema_path = Path(__file__).parent / "milvus_schema.json"
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def init_milvus():
    """初始化 Milvus 数据库"""
    # 连接 Milvus
    connections.connect(
        alias="default",
        host=Config.MILVUS_CONFIG["host"],
        port=Config.MILVUS_CONFIG["port"],
        token=Config.MILVUS_CONFIG["token"],
        db_name=Config.MILVUS_CONFIG["db_name"]
    )

    # 加载 schema 配置
    schema_config = load_schema()
    
    # 创建字段
    fields = []
    for field_config in schema_config["fields"]:
        field = FieldSchema(
            name=field_config["name"],
            dtype=getattr(DataType, field_config["type"]),
            description=field_config.get("description", ""),
            is_primary=field_config.get("is_primary", False),
            **{k: v for k, v in field_config.items() 
               if k not in ["name", "type", "description", "is_primary"]}
        )
        fields.append(field)

    # 创建 schema
    schema = CollectionSchema(
        fields=fields,
        description="天宽认知大模型文档向量库",
        enable_dynamic_field=True
    )

    # 如果集合已存在，记录日志并跳过创建
    if utility.has_collection(schema_config["collection_name"]):
        logger.info(f"集合 {schema_config['collection_name']} 已存在，跳过创建")
        return

    # 创建新集合
    collection = Collection(
        name=schema_config["collection_name"],
        schema=schema
    )

    # 创建索引
    index_params = {
        "index_type": Config.MILVUS_CONFIG["index_params"]["index_type"],
        "metric_type": Config.MILVUS_CONFIG["index_params"]["metric_type"],
        "params": Config.MILVUS_CONFIG["index_params"]["params"]
    }
    collection.create_index(
        field_name=Config.MILVUS_CONFIG["vector_field"],
        index_params=index_params
    )

    logger.info(f"Milvus 集合 {schema_config['collection_name']} 初始化完成！")

if __name__ == "__main__":
    init_milvus() 