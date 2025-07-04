"""MySQL 数据库初始化脚本"""
import os

import pymysql

from config.global_config import GlobalConfig
from utils.log_utils import logger
from databases.mysql.base import MySQLUtils


def init_mysql():
    """初始化 MySQL 数据库"""
    logger.debug("开始初始化 MySQL 数据库...")

    # 读取初始化 SQL 文件
    init_sql_path = GlobalConfig.PATHS.get("mysql_schema_path")
    with open(init_sql_path, 'r') as f:
        init_sql = f.read()

    # 替换占位符为配置中的数据库名称
    db_name = GlobalConfig.MYSQL_CONFIG['database']
    init_sql = init_sql.replace('{{DB_NAME}}', db_name)

    # 连接 MySQL（不指定数据库）
    conn = pymysql.connect(
        host=GlobalConfig.MYSQL_CONFIG['host'],
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        charset=GlobalConfig.MYSQL_CONFIG['charset']
    )

    # 设置时区为东八区(北京时间)
    with conn.cursor() as cursor:
        cursor.execute("SET time_zone = '+08:00'")
        conn.commit()

    try:
        with conn.cursor() as cursor:
            # 执行初始化 SQL
            for sql in init_sql.split(';'):
                if sql.strip():
                    cursor.execute(sql)
            conn.commit()
        logger.debug("MySQL 数据库初始化完成！")
        
        # 测试连接
        if MySQLUtils.test_connection():
            logger.info("数据库连接测试成功")
        else:
            logger.error("数据库连接测试失败")
            
    except Exception as e:
        logger.error(f"MySQL 数据库初始化失败: {str(e)}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    init_mysql()
