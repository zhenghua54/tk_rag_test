"""MySQL 数据库初始化脚本"""

import pymysql

from config.settings import Config
from src.utils.common.logger import logger


def init_mysql():
    """初始化 MySQL 数据库"""
    logger.info("开始初始化 MySQL 数据库...")

    # 读取初始化 SQL 文件
    init_sql_path = Config.MYSQL_CONFIG['schema_path']
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


if __name__ == "__main__":
    init_mysql()
