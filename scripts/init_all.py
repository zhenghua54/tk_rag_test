"""项目初始化脚本

该脚本用于初始化整个项目环境，包括：
1. 创建必要的目录结构
2. 初始化 MySQL 数据库
3. 初始化 Milvus 数据库
4. 初始化 Elasticsearch
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

# 加载环境变量
load_dotenv()

from pymilvus import connections, Collection
from databases.elasticsearch.operations import ElasticsearchOperation

from config.global_config import GlobalConfig
from utils.log_utils import logger
from databases.mysql.base import MySQLUtils
from scripts.subscript.init_mysql import init_mysql
from scripts.subscript.init_milvus import init_milvus
from scripts.subscript.init_es import init_es


def ensure_directories():
    """确保所有必要的目录存在"""
    logger.debug("创建必要的目录结构...")

    # 创建数据目录
    data_path = [GlobalConfig.PATHS.get("origin_data"), GlobalConfig.PATHS.get("processed_data"), GlobalConfig.PATHS.get("log_dir")]
    for path in data_path:
        if os.path.isfile(path) or os.path.exists(path):
            logger.warning(f"跳过已存在文件路径: {path}")
            continue
        os.makedirs(path, exist_ok=True)
        logger.debug(f"创建目录: {path}")

    # 创建模型目录
    if os.makedirs(GlobalConfig.PATHS.get('model_base'), exist_ok=True):
        logger.info(f"创建目录: {GlobalConfig.PATHS.get('model_base')}")
    else:
        logger.info(f"目录: {GlobalConfig.PATHS.get('model_base')} 已存在")



def test_connections():
    """测试所有数据库连接"""
    # 测试 MySQL 连接
    if not MySQLUtils.test_connection():
        raise Exception("MySQL 数据库连接失败！") 

    # 测试 Milvus 连接
    try:
        connections.connect(
            alias="default",
            host=GlobalConfig.MILVUS_CONFIG["host"],
            port=GlobalConfig.MILVUS_CONFIG["port"],
            token=GlobalConfig.MILVUS_CONFIG["token"],
            db_name=GlobalConfig.MILVUS_CONFIG["db_name"]
        )
        collection = Collection(GlobalConfig.MILVUS_CONFIG["collection_name"])
        if not collection:
            raise Exception("Milvus 集合加载失败！")
    except Exception as e:
        logger.error(f"Milvus 连接测试失败: {str(e)}")
        raise Exception(f"Milvus 连接失败: {str(e)}")

    # 测试 ES 连接
    try:
        es_client = ElasticsearchOperation()
        if not es_client.ping():
            raise Exception("ES 连接失败！")
    except Exception as e:
        logger.error(f"ES 连接测试失败: {str(e)}")
        raise Exception(f"ES 连接失败: {str(e)}")


def init_all():
    """初始化所有组件"""
    try:
        logger.info("开始初始化项目环境...")

        # 1. 创建目录结构
        ensure_directories()

        # 2. 初始化各个服务
        init_mysql()
        init_milvus()
        init_es()

        # 3. 测试所有连接
        test_connections()

        logger.info("项目环境初始化完成！")
    except Exception as e:
        logger.error(f"项目初始化失败: {str(e)}")
        raise RuntimeError(f"项目初始化失败: {str(e)}") from e


if __name__ == "__main__":
    # 确保在项目根目录下执行
    os.chdir(root_path)
    init_all()
