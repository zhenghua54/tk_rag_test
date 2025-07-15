"""Elasticsearch 初始化脚本"""

import json

from config.global_config import GlobalConfig
from tmp.elasticsearch.operations import ElasticsearchOperation
from utils.log_utils import logger


def load_schema():
    """加载 ES schema 配置"""
    schema_path = GlobalConfig.PATHS.get("es_schema_path")
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)


def init_es():
    """初始化 Elasticsearch 环境"""
    try:
        # 1. 创建 ES 操作实例
        es_op = ElasticsearchOperation()

        # 2. 加载 schema 配置
        schema_config = load_schema()
        index_name = GlobalConfig.ES_CONFIG["index_name"]

        # 3. 创建索引
        return es_op.create_index(index_name, schema_config)

    except Exception as e:
        logger.error(f"初始化 ES 失败: {str(e)}")
        return False


if __name__ == "__main__":
    init_es()
