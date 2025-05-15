"""MySQL 数据库的初始化和连接配置文件"""
import sys
from contextlib import contextmanager
from typing import Dict, Any

sys.path.append("/")

import pymysql
from config import Config, logger


class MySQLConnect:
    """定义 mysql 连接类"""

    def __init__(self, host, user, password, charset, database):
        self.host = host
        self.user = user
        self.password = password
        self.charset = charset
        self.database = database
        # 初始化时不指定数据库
        self.connection = pymysql.connect(
            host=self.host,
            user=self.user,
            password=self.password,
            charset=self.charset
        )

    @contextmanager
    def get_connection(self):
        """上下文管理器,用于获取数据库连接和游标"""
        try:
            # 使用字典游标
            cursor = self.connection.cursor(pymysql.cursors.DictCursor)
            try:
                yield cursor
            except Exception as e:
                # 回滚事务
                logger.error(f"mysql 执行失败,回滚事务: {e}")
                self.connection.rollback()
                raise e
            else:
                # 提交事务
                logger.info(f"mysql 执行成功,提交事务")
                self.connection.commit()
            finally:
                # 关闭游标
                cursor.close()
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise e

    def create_db(self, db_name='tk_db'):
        """创建数据库
        Args:
            db_name: 数据库名
        """
        with self.get_connection() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        logger.info(f"数据库 {db_name} 创建成功!")

    def use_db(self):
        """切换数据库,如果不存在则创建后切换"""
        try:
            # 尝试切换数据库
            self.connection.select_db(self.database)
            logger.info(f"切换数据库 {self.database} 成功!")
        except pymysql.err.OperationalError:
            # 如果数据库不存在,则创建后切换
            logger.info(f"数据库 {self.database} 不存在,开始创建...")
            self.create_db(self.database)
            self.connection.select_db(self.database)
            logger.info(f"创建并切换数据库 {self.database} 成功!")

    def create_table(self, table_name='tk_table'):
        """创建表
        Args:
            table_name: 表名
        """
        with self.get_connection() as cursor:
            cursor.execute(
                f"""CREATE TABLE IF NOT EXISTS {table_name} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                doc_id VARCHAR(64) NOT NULL,
                source_document_name VARCHAR(255),
                source_document_type VARCHAR(100),
                source_document_path VARCHAR(512),
                source_document_json_path VARCHAR(512),
                source_document_markdown_path VARCHAR(512),
                source_document_images_path VARCHAR(512),
                UNIQUE(doc_id)
                )""")
        logger.info(f"表 {table_name} 创建成功!")

    def insert_data(self, data: Dict[str, Any], table_name: str = 'tk_table'):
        """插入数据
        Args:
            data: 数据(字典格式)
            table_name: 表名
        """
        with self.get_connection() as cursor:
            try:
                # 使用参数化查询防止 SQL 注入
                columns = ', '.join(data.keys())
                placeholders = ', '.join(['%s'] * len(data))
                query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
                cursor.execute(query, list(data.values()))
                logger.info(f"数据插入成功!")
            except Exception as e:
                if "Duplicate entry" in str(e):
                    logger.error(f"数据已存在: {e}")
                else:
                    logger.error(f"数据插入失败: {e}")
                raise e

    def delete_data(self, data: Dict[str, Any], table_name: str = 'tk_table'):
        """删除数据
        Args:
            data: 数据(字典格式)
            table_name: 表名
        """
        with self.get_connection() as cursor:
            # 构建 WHERE 子句
            where_clause = ' AND '.join([f"{k} = %s" for k in data.keys()])
            query = f"DELETE FROM {table_name} WHERE {where_clause}"
            cursor.execute(query, list(data.values()))
        logger.info(f"数据删除成功!")

    def update_data(self, data: Dict[str, Any], condition: Dict[str, Any], table_name: str = 'tk_table'):
        """更新数据
        Args:
            data: 要更新的数据(字典格式)
            condition: 更新条件(字典格式)
            table_name: 表名
        """
        with self.get_connection() as cursor:
            # 构建 SET 子句
            set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
            # 构建 WHERE 子句
            where_clause = ' AND '.join([f"{k} = %s" for k in condition.keys()])
            query = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"
            cursor.execute(query, list(data.values()) + list(condition.values()))
        logger.info(f"数据更新成功!")
        
    def select_data(self, table_name: str, condition: Dict[str, Any]):
        """查询数据
        Args:
            table_name: 表名
            condition: 查询条件(字典格式)
        """
        with self.get_connection() as cursor:
            # 构建 WHERE 子句
            where_clause = ' AND '.join([f"{k} = %s" for k in condition.keys()])
            query = f"SELECT * FROM {table_name} WHERE {where_clause}"
            cursor.execute(query, list(condition.values()))
            return cursor.fetchall()

    def close(self):
        """关闭数据库连接"""
        if hasattr(self, 'connection'):
            self.connection.close()
            logger.info("数据库连接已关闭")


def connect_mysql():
    """创建数据库连接实例"""
    mysql = MySQLConnect(
        host=Config.MYSQL_CONFIG['host'],
        user=Config.MYSQL_CONFIG['user'],
        password=Config.MYSQL_CONFIG['password'],
        charset=Config.MYSQL_CONFIG['charset'],
        database=Config.MYSQL_CONFIG['database']
    )
    return mysql


def test_connect_mysql():
    """测试数据库连接"""
    mysql = connect_mysql()
    try:
        # 测试连接
        with mysql.get_connection() as cursor:
            cursor.execute("SELECT 1")
            logger.info('数据库连接成功!')
        return mysql
    except Exception as e:
        logger.error(f"数据库连接测试失败: {e}")
        raise e


if __name__ == '__main__':
    # 测试数据
    test_data = {
        'doc_id': 'c96f45c0bfb92a5071d02a6e0bc287d53ffba4b3b77294a28cf70e459b859a08',
        'source_document_name': 'doc1.pdf',
        'source_document_type': 'pdf',
        'source_document_path': '/path/to/doc1.pdf',
        'source_document_json_path': '/path/to/doc1.json',
        'source_document_markdown_path': '/path/to/doc1.md',
        'source_document_images_path': '/path/to/doc1/images/'
    }

    try:
        # 运行测试
        mysql = connect_mysql()
        mysql.use_db()
        mysql.create_table()
        mysql.insert_data(test_data)
    except Exception as e:
        logger.error(f"测试执行失败: {e}")
    finally:
        if 'mysql' in locals():
            mysql.close()
