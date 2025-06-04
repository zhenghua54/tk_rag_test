"""Elasticsearch 初始化脚本"""

import json

from src.database.elasticsearch.operations import ElasticsearchOperation
from src.utils.common.logger import logger
from config.settings import Config


def load_schema():
    """加载 ES schema 配置"""
    schema_path = Config.ES_CONFIG['schema_path']
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def init_es():
    """初始化 Elasticsearch 环境"""
    try:
        # 1. 创建 ES 操作实例
        es_op = ElasticsearchOperation()

        # 2. 加载 schema 配置
        schema_config = load_schema()
        index_name = Config.ES_CONFIG["index_name"]

        # 3. 创建索引
        return es_op.create_index(index_name, schema_config)

    except Exception as e:
        logger.error(f"初始化 ES 失败: {str(e)}")
        return False


if __name__ == "__main__":
    init_es()
