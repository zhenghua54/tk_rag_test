"""项目初始化脚本

该脚本用于初始化整个项目环境，包括：
1. 创建必要的目录结构
2. 初始化 MySQL 数据库
3. 初始化 Milvus 数据库
"""
import sys
import os
root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_path)

import pymysql
from pathlib import Path
from pymilvus import connections, Collection            


from config.settings import Config
from scripts.init.milvus_init import init_milvus
from src.utils.common.logger import logger
from src.database.mysql.connection import test_connect_mysql

def ensure_directories():
    """确保所有必要的目录存在"""
    logger.info("创建必要的目录结构...")
    
    # 创建数据目录
    for path in Config.PATHS.values():
        os.makedirs(path, exist_ok=True)
        logger.info(f"创建目录: {path}")
    
    # 创建模型目录
    for path in Config.MODEL_PATHS.values():
        os.makedirs(path, exist_ok=True)
        logger.info(f"创建目录: {path}")

def init_mysql():
    """初始化 MySQL 数据库"""
    logger.info("开始初始化 MySQL 数据库...")
    
    # 读取初始化 SQL 文件
    init_sql_path = Path(__file__).parent / "mysql_init.sql"
    with open(init_sql_path, 'r') as f:
        init_sql = f.read()
    
    # 连接 MySQL（不指定数据库）
    conn = pymysql.connect(
        host=Config.MYSQL_CONFIG['host'],
        user=Config.MYSQL_CONFIG['user'],
        password=Config.MYSQL_CONFIG['password'],
        charset=Config.MYSQL_CONFIG['charset']
    )
    
    try:
        with conn.cursor() as cursor:
            # 执行初始化 SQL
            for sql in init_sql.split(';'):
                if sql.strip():
                    cursor.execute(sql)
            conn.commit()
        logger.info("MySQL 数据库初始化完成！")
    except Exception as e:
        logger.error(f"MySQL 数据库初始化失败: {e}")
        raise
    finally:
        conn.close()

def init_all():
    """初始化所有组件"""
    try:
        logger.info("开始初始化项目环境...")
        
        # 创建目录结构
        ensure_directories()
        
        # 初始化 MySQL
        init_mysql()
        
        # 初始化 Milvus
        init_milvus()

        # 测试数据库连接
        if not test_connect_mysql():
            raise Exception("数据库连接失败！")
        
        # 测试 Milvus 连接
        try:
            connections.connect(
                alias="default",
                host=Config.MILVUS_CONFIG["host"],
                port=Config.MILVUS_CONFIG["port"],
                token=Config.MILVUS_CONFIG["token"],
                db_name=Config.MILVUS_CONFIG["db_name"]
            )
            collection = Collection(Config.MILVUS_CONFIG["collection_name"])
            if not collection:
                raise Exception("Milvus 集合加载失败！")
        except Exception as e:
            logger.error(f"Milvus 连接测试失败: {e}")
            raise Exception(f"Milvus 连接失败: {e}")
        
        logger.info("项目环境初始化完成！")
    except Exception as e:
        logger.error(f"项目初始化失败: {e}")
        raise

if __name__ == "__main__":
    init_all() 