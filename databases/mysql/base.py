"""数据库操作基类"""

import os
from typing import Any

import pymysql
from dbutils.pooled_db import PooledDB
from pymysql.cursors import DictCursor

from config.global_config import GlobalConfig
from utils.log_utils import logger


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
                maxconnections=20,  # 最大连接数：100的20%，留80%给其他应用
                mincached=5,  # 最小缓存连接：保证基本响应速度
                maxcached=15,  # 最大缓存连接：适应并发峰值
                maxshared=10,  # 最大共享连接：减少连接创建开销
                blocking=True,  # 阻塞等待：确保连接可用
                maxusage=1000,  # 连接复用次数：避免连接老化
                setsession=['SET time_zone = "+08:00"'],  # 设置时区为东八区(北京时间)
                ping=0,  # ping MySQL服务端确保连接有效
                host=GlobalConfig.MYSQL_CONFIG["host"],
                user=os.getenv("MYSQL_USER"),
                password=os.getenv("MYSQL_PASSWORD"),
                database=GlobalConfig.MYSQL_CONFIG["database"],
                charset=GlobalConfig.MYSQL_CONFIG["charset"],
            )
            logger.info("[MySQL连接池] 连接池初始化成功")

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
            with pool.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute("SELECT 1")
            logger.info("[MySQL连接测试] 数据库连接测试成功")
            return True
        except Exception as e:
            logger.error(f"[MySQL连接测试失败] error_msg={str(e)}")
            return False


class BaseDBOperation:
    """数据库操作基类"""

    def __init__(self, table_name: str, conn=None):
        self.table_name = table_name
        self._pool = MySQLConnectionPool()
        self._connection_count = 0
        self._external_conn = conn  # 支持传入事务连接

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass  # 连接池会自动管理连接，这里不需要额外操作

    def _execute_query(self, sql: str, args: tuple | None = None) -> list[dict]:
        # 使用外部事务或连接池获取连接
        conn = self._external_conn or self._pool.get_connection()

        with conn.cursor(DictCursor) as cursor:
            cursor.execute(sql, args)
            return list(cursor.fetchall()) if cursor.rowcount > 0 else []

    def _execute_update(self, sql: str, args: tuple | None = None) -> int:
        conn = self._external_conn or self._pool.get_connection()

        with conn.cursor() as cursor:
            cursor.execute(sql, args)
            # 如果外部连接不为空，则不提交事务
            if not self._external_conn:
                conn.commit()
            return cursor.rowcount

    def select_by_id(self, doc_id: str) -> list[dict] | None:
        """根据ID查询单条记录

        Args:
            doc_id (str): 文档ID

        Returns:
            list[dict] | None: 查询结果，如果未找到则返回 None
        """
        try:
            sql = f"SELECT * FROM {self.table_name} WHERE doc_id = %s"
            data = self._execute_query(sql, (doc_id,))
            return data if data else None
        except Exception as e:
            logger.error(f"查询记录失败: {str(e)}")
            raise e

    def select_record(self, fields: list[str] | None = None, conditions: dict | None = None) -> list[dict] | None:
        """查询记录

        Args:
            fields: 查询的字段列表，如果为 None 则查询所有字段
            conditions : 查询条件，默认为 None

        Returns:
            list[dict] | None: 查询到的记录列表
        """
        try:
            # 构建 SELECT 子句
            select_clause = ", ".join(fields) if fields else "*"

            # 构建 WHERE 子句
            args = None
            if conditions:
                where_clause = " AND ".join([f"{k} = %s" for k in conditions])
                args = tuple(conditions.values())
                sql = f"SELECT {select_clause} FROM {self.table_name} WHERE {where_clause}"
            else:
                sql = f"SELECT {select_clause} FROM {self.table_name}"

            return self._execute_query(sql, args)
        except Exception as e:
            logger.error(f"查询记录失败: {str(e)}")
            raise e

    def insert(self, data: dict[str, Any] | list[dict[str, Any]]) -> int:
        """插入记录(单条或多条),请确保所有数据的字段一致

        Args:
            data (dict[str, Any] | list[dict[str, Any]]): 要插入的数据,单条=dict,多条=list[dict]

        Returns:
            int: 影响的行数

        Raises:
            APIException: 数据插入失败时抛出
        """
        affected_rows = 0

        # 单条数据
        if isinstance(data, dict):
            try:
                columns = ", ".join(data.keys())
                placeholders = ", ".join(["%s"] * len(data))
                sql = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
                affected_rows = self._execute_update(sql, tuple(data.values()))
                logger.debug(f"Mysql 数据插入成功, 共 {affected_rows} 条")
            except Exception as e:
                logger.error(f"MySQL 数据插入失败，表 {self.table_name}: {str(e)}, 数据: {data}")
                raise ValueError(f"数据插入失败: {str(e)}") from e
        # 多条数据
        elif isinstance(data, list) and len(data) > 0:
            try:
                # 获取字段列表
                fields = list(data[0].keys())
                columns = ", ".join(fields)
                placeholders = ", ".join(["%s"] * len(fields))

                # 构建SQL语句
                sql = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"

                # 准备批量插入的数据
                values = [tuple(record[field] for field in fields) for record in data]

                # 执行批量插入
                with self._pool.get_connection() as conn, conn.cursor() as cursor:
                    cursor.executemany(sql, values)
                    conn.commit()
                    affected_rows = cursor.rowcount

                logger.debug(f"Mysql 数据插入成功, 共 {affected_rows} 条")
            except Exception as e:
                logger.error(f"MySQL 数据插入失败，表 {self.table_name}: {str(e)}, 共 {len(data)} 条记录")
                raise ValueError(f"批量数据插入失败: {str(e)}, 数据情况: {data}") from e
        return affected_rows

    def update_by_doc_id(self, doc_id: str, data: dict[str, Any]) -> bool | None:
        """根据 doc_id 更新记录

        Args:
            doc_id (str): 文档ID
            data (dict[str, Any]): 要更新的数据

        Returns:
            bool: 是否更新成功
        """
        # 清洗输入
        if not doc_id or not data:
            raise ValueError("doc_id 和 data 均不能为空")

        # 清除 None 值可能导致的问题
        data: dict = {k: v for k, v in data.items() if v is not None}

        try:
            set_clause = ", ".join([f"{k} = %s" for k in data])
            sql = f"UPDATE {self.table_name} SET {set_clause} WHERE doc_id = %s"
            values = list(data.values())
            values.append(doc_id)
            logger.debug("MySQL 记录更新成功 ")
            return self._execute_update(sql, tuple(values)) > 0
        except Exception as e:
            logger.error(f"MySQL 记录更新失败: {str(e)}")
            raise e from e

    def delete_by_doc_id(self, doc_id: str) -> int:
        """根据 doc_id 删除指定数据库信息"""
        try:
            sql = f"DELETE FROM {self.table_name} WHERE doc_id = %s"
            return self._execute_update(sql, (doc_id,))
        except Exception as e:
            logger.error(f"MySQL 数据删除失败, 失败原因: {str(e)}")
            raise e from e

    def update_by_field(self, field_name: str, field_value: str, data: dict[str, Any]) -> bool:
        """根据指定字段更新记录

        Args:
            field_name: 字段名
            field_value: 字段值
            data: 要更新的数据

        Returns:
            bool: 是否更新成功
        """
        try:
            set_clause = ", ".join([f"{k} = %s" for k in data])
            sql = f"UPDATE {self.table_name} SET {set_clause} WHERE {field_name} = %s"
            values = list(data.values())
            values.append(field_value)
            logger.debug(f"MySQL 记录更新成功, 表={self.table_name}, 字段={field_name}")
            return self._execute_update(sql, tuple(values)) > 0
        except Exception as e:
            logger.error(f"MySQL 记录更新失败: {str(e)}")
            raise e from e
