"""Milvus 数据库初始化脚本"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from databases.milvus.connection import MilvusDB
from utils.common.logger import logger


def init_milvus():
    """初始化 Milvus 数据库"""
    try:
        # 创建 Milvus 连接
        milvus_conn = MilvusDB()

        # 初始化 Milvus 数据库和集合
        milvus_conn.init_database()

        logger.debug("Milvus 数据库初始化成功")

    except Exception as e:
        logger.error(f"Milvus 数据库初始化失败: {str(e)}")
        raise


if __name__ == "__main__":
    init_milvus()
