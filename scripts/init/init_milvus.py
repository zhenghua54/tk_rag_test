"""Milvus 数据库初始化脚本"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from src.database.milvus.connection import MilvusDB
from src.utils.common.logger import logger


def init_milvus():
    """初始化 Milvus 数据库"""
    try:
        # 创建 Milvus 连接
        milvus_conn = MilvusDB()

        # 检查集合是否存在
        if milvus_conn.client.has_collection(milvus_conn.collection_name):
            logger.info(f"集合 {milvus_conn.collection_name} 已存在，跳过创建")
            return

        # 创建集合（使用 connection.py 中的代码）
        milvus_conn._create_collection()
        logger.info("Milvus 数据库初始化成功")

    except Exception as e:
        logger.error(f"Milvus 数据库初始化失败: {str(e)}")
        raise


if __name__ == "__main__":
    init_milvus()
