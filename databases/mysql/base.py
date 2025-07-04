"""数据库操作基类"""
import os
import pymysql

from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Union
from pymysql.cursors import DictCursor
from dbutils.pooled_db import PooledDB

from config.global_config import GlobalConfig
from utils.log_utils import logger
from utils.validators import validate_doc_id, validate_param_type, validate_empty_param


class MySQLConnectionPool:
    """数据库连接池"""
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
                mincached=2,  # 初始化时创建的连接数
                maxcached=5,  # 连接池最大空闲连接数
                maxshared=3,  # 共享连接的最大数量
                blocking=True,  # 连接池中如果没有可用连接后是否阻塞等待
                maxusage=None,  # 一个连接最多被重复使用的次数
                setsession=['SET time_zone = "+08:00"'],  # 设置时区为东八区(北京时间)
                ping=0,  # ping MySQL服务端确保连接有效
                host=GlobalConfig.MYSQL_CONFIG['host'],
                user=os.getenv("MYSQL_USER"),
                password=os.getenv("MYSQL_PASSWORD"),
                database=GlobalConfig.MYSQL_CONFIG['database'],
                charset=GlobalConfig.MYSQL_CONFIG['charset']
            )
            logger.info(f"[MySQL连接池] 连接池初始化成功")

    def get_connection(self):
        return self._pool.connection()

    def close(self):
        if self._pool:
            self._pool.close()
            logger.info("MySQL 连接池已关闭")


class MySQLUtils:
    """MySQL 工具类，提供数据库相关的通用功能"""

    @staticmethod
    def test_connection() -> bool:
        """使用连接池测试数据库连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 使用连接池获取连接进行测试
            pool = MySQLConnectionPool()
            with pool.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
            logger.info(f"[MySQL连接测试] 数据库连接测试成功")
            return True
        except Exception as e:
            logger.error(f"[MySQL连接测试失败] error_msg={str(e)}")
            return False


class BaseDBOperation:
    """数据库操作基类"""

    def __init__(self, table_name: str):
        self.table_name = table_name
        self._pool = MySQLConnectionPool()
        self._connection_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass  # 连接池会自动管理连接，这里不需要额外操作

    def _execute_query(self, sql: str, args: Optional[Tuple] = None) -> List[Dict]:
        with self._pool.get_connection() as conn:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute(sql, args)
                return list(cursor.fetchall()) if cursor.rowcount > 0 else []

    def _execute_update(self, sql: str, args: Optional[Tuple] = None) -> int:
        with self._pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, args)
                conn.commit()
                return cursor.rowcount

    def select_by_id(self, doc_id: str) -> Optional[Dict]:
        """根据ID查询单条记录

        Args:
            doc_id (str): 文档ID

        Returns:
            Optional[Dict]: 查询结果，如果未找到则返回 None
        """
        validate_doc_id(doc_id)
        try:
            sql = f'SELECT * FROM {self.table_name} WHERE doc_id = %s'
            data = self._execute_query(sql, (doc_id,))
            return data[0] if data else None
        except Exception as e:
            logger.error(f"查询记录失败: {str(e)}")
            raise e

    def select_by_id_many(self, doc_id: str) -> List[Dict]:
        """根据 doc_id 查询记录

        Args:
            doc_id (List[str]): 文档 ID,支持一个或多个

        Returns:
            List[Dict]: 查询到的结果
        """
        validate_doc_id(doc_id)

        try:
            sql = f'SELECT * FROM {self.table_name} WHERE doc_id = %s'
            return self._execute_query(sql, (doc_id,))
        except Exception as e:
            logger.error(f"查询记录失败: {str(e)}")
            raise e


    def select_record(self, fields: Optional[List[str]] = None, conditions: Optional[Dict] = None) -> List[Dict] | None:
        """查询记录

        Args:
            fields (List[str], optional): 查询的字段列表，如果为 None 则查询所有字段
            conditions (Dict, optional): 查询条件，默认为 None

        Returns:
            List[Dict]: 查询到的记录列表
        """
        try:
            # 构建 SELECT 子句
            select_clause = ', '.join(fields) if fields else '*'

            # 构建 WHERE 子句
            args = None
            if conditions:
                validate_param_type(conditions, dict, "conditions")
                where_clause = ' AND '.join([f"{k} = %s" for k in conditions.keys()])
                args = tuple(conditions.values())
                sql = f'SELECT {select_clause} FROM {self.table_name} WHERE {where_clause}'
            else:
                sql = f'SELECT {select_clause} FROM {self.table_name}'

            return self._execute_query(sql, args)
        except Exception as e:
            logger.error(f"查询记录失败: {str(e)}")
            raise e

    def insert(self, data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> int:
        """插入记录(单条或多条),请确保所有数据的字段一致

        Args:
            data (Union[Dict[str, Any], List[Dict[str, Any]]]): 要插入的数据,单条=dict,多条=list[dict]

        Returns:
            int: 影响的行数

        Raises:
            APIException: 数据插入失败时抛出
        """
        affected_rows = 0

        # 单条数据
        if isinstance(data, dict):
            try:
                columns = ', '.join(data.keys())
                placeholders = ', '.join(['%s'] * len(data))
                sql = f'INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})'
                affected_rows = self._execute_update(sql, tuple(data.values()))
                logger.info(f"Mysql 数据插入成功, 共 {affected_rows} 条")
            except Exception as e:
                logger.error(f"MySQL 数据插入失败，表 {self.table_name}: {str(e)}, 数据: {data}")
                raise ValueError(f"数据插入失败: {str(e)}")
        # 多条数据
        elif isinstance(data, list) and len(data) > 0:
            try:
                # 获取字段列表
                fields = list(data[0].keys())
                columns = ', '.join(fields)
                placeholders = ', '.join(['%s'] * len(fields))

                # 构建SQL语句
                sql = f'INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})'

                # 准备批量插入的数据
                values = [tuple(record[field] for field in fields) for record in data]

                # 执行批量插入
                with self._pool.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.executemany(sql, values)
                        conn.commit()
                        affected_rows = cursor.rowcount

                logger.info(f"Mysql 数据插入成功, 共 {affected_rows} 条")
            except Exception as e:
                logger.error(f"MySQL 数据插入失败，表 {self.table_name}: {str(e)}, 共 {len(data)} 条记录")
                raise ValueError(f"批量数据插入失败: {str(e)}, 数据情况: {data}")
        return affected_rows

    def update_by_doc_id(self, doc_id: str, data: Dict[str, Any]) -> bool | None:
        """根据 doc_id 更新记录

        Args:
            doc_id (str): 文档ID
            data (Dict[str, Any]): 要更新的数据

        Returns:
            bool: 是否更新成功
        """
        validate_doc_id(doc_id)
        validate_empty_param(data, "data")
        validate_param_type(data, dict, "data")

        try:
            set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
            sql = f'UPDATE {self.table_name} SET {set_clause} WHERE doc_id = %s'
            values = list(data.values())
            values.append(doc_id)
            logger.info(f"MySQL 记录更新成功 ")
            return self._execute_update(sql, tuple(values)) > 0
        except Exception as e:
            logger.error(f"MySQL 记录更新失败: {str(e)}")
            raise e

    def delete_by_doc_id(self, doc_id: str) -> int:
        """通用删除接口，支持软/硬删除"""
        try:
            sql = f"DELETE FROM {self.table_name} WHERE doc_id = %s"
            return self._execute_update(sql, (doc_id,))
        except Exception as e:
            logger.error(f"MySQL 数据删除失败, 失败原因: {str(e)}")
            raise e from e

    def update_by_field(self, field_name: str, field_value: str, data: Dict[str, Any]) -> bool:
        """根据指定字段更新记录
        
        Args:
            field_name: 字段名
            field_value: 字段值
            data: 要更新的数据
            
        Returns:
            bool: 是否更新成功
        """
        try:
            set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
            sql = f'UPDATE {self.table_name} SET {set_clause} WHERE {field_name} = %s'
            values = list(data.values())
            values.append(field_value)
            logger.info(f"MySQL 记录更新成功, 表={self.table_name}, 字段={field_name}")
            return self._execute_update(sql, tuple(values)) > 0
        except Exception as e:
            logger.error(f"MySQL 记录更新失败: {str(e)}")
            raise e