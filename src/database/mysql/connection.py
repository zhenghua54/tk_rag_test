"""MySQL 数据库的初始化和连接配置文件"""
from contextlib import contextmanager
from typing import  Optional, Tuple, List

import pymysql
from pymysql.cursors import DictCursor

from config.settings import Config
from src.utils.common.logger import logger
from dbutils.pooled_db import PooledDB
import pymysql

class MySQLConnectionPool:
    _instance = None
    _pool = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._pool is None:
            self._pool = PooledDB(
                creator=pymysql,
                maxconnections=6,  # 连接池最大连接数
                mincached=2,       # 初始化时创建的连接数
                maxcached=5,       # 连接池最大空闲连接数
                maxshared=3,       # 共享连接的最大数量
                blocking=True,     # 连接池中如果没有可用连接后是否阻塞等待
                maxusage=None,     # 一个连接最多被重复使用的次数
                setsession=[],     # 开始会话前执行的命令列表
                ping=0,           # ping MySQL服务端确保连接有效
                host=Config.MYSQL_CONFIG['host'],
                user=Config.MYSQL_CONFIG['user'],
                password=Config.MYSQL_CONFIG['password'],
                database=Config.MYSQL_CONFIG['database'],
                charset=Config.MYSQL_CONFIG['charset']
            )
            logger.info("MySQL 连接池初始化成功")

    def get_connection(self):
        return self._pool.connection()

    def close(self):
        if self._pool:
            self._pool.close()
            logger.info("MySQL 连接池已关闭")

class MySQLConnect:
    """MySQL 数据库连接类"""

    def __init__(self, host: str, user: str, password: str, charset: str, database: str):
        """初始化数据库连接
        
        Args:
            host: 数据库主机地址
            user: 数据库用户名
            password: 数据库密码
            charset: 字符集
            database: 数据库名
        """
        self.host = host
        self.user = user
        self.password = password
        self.charset = charset
        self.database = database
        self.connection = pymysql.connect(
            host=self.host,
            user=self.user,
            password=self.password,
            charset=self.charset,
            database=self.database
        )

    @contextmanager
    def get_connection(self):
        """上下文管理器,用于获取数据库连接和游标"""
        try:
            # 使用字典游标
            cursor = self.connection.cursor(DictCursor)
            try:
                yield cursor
            except Exception as e:
                logger.error(f"mysql 执行失败,回滚事务: {e}")
                self.connection.rollback()
                raise e
            else:
                # 提交事务
                self.connection.commit()
            finally:
                cursor.close()
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise e

    def use_db(self):
        """切换数据库,如果不存在则创建后切换"""
        try:
            self.connection.select_db(self.database)
            logger.info(f"切换数据库 {self.database} 成功!")
        except pymysql.err.OperationalError:
            raise pymysql.err.OperationalError(f"数据库 {self.database} 不存在,请执行 init_all.py 初始化数据库...")

    def execute(self, sql: str, args: Optional[Tuple] = None) -> int:
        """执行 SQL 语句
        
        Args:
            sql: SQL 语句
            args: SQL 参数
            
        Returns:
            int: 影响的行数
        """
        # 输出完整的SQL和参数，用于调试
        logger.debug(f"执行SQL: {sql}")
        logger.debug(f"参数: {args}")
        
        with self.get_connection() as cursor:
            try:
                cursor.execute(sql, args)
                return cursor.rowcount
            except Exception as e:
                # 详细记录错误
                logger.error(f"SQL执行错误: {e}")
                logger.error(f"完整SQL: {sql}")
                logger.error(f"参数: {args}")
                raise

    def close(self):
        """关闭数据库连接"""
        if hasattr(self, 'connection'):
            self.connection.close()
            logger.info("数据库连接已关闭")


def check_table_exists(mysql: MySQLConnect, table_name: str) -> bool:
    """检查数据库中指定的表是否存在
    
    Args:
        mysql: 数据库连接实例
        table_name: 表名
        
    Returns:
        bool: 表是否存在
    """
    query = f"SHOW TABLES LIKE '{table_name}'"
    result = mysql.execute(query)
    return result > 0


def test_connect_mysql():
    """测试数据库连接"""
    mysql = MySQLConnect(
        host=Config.MYSQL_CONFIG['host'],
        user=Config.MYSQL_CONFIG['user'],
        password=Config.MYSQL_CONFIG['password'],
        charset=Config.MYSQL_CONFIG['charset'],
        database=Config.MYSQL_CONFIG['database']
    )
    try:
        # 测试连接
        with mysql.get_connection() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"数据库连接测试失败: {e}")
        return False


if __name__ == '__main__':
    test_connect_mysql()
