# src/database/mysql/response.py
"""数据库操作基类"""
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Union

import pymysql
from pymysql.cursors import DictCursor

from config.settings import Config
from src.api.error_codes import ErrorCode
from src.api.response import APIException
from src.utils.common.logger import logger
from src.database.mysql.connection import MySQLConnect, MySQLConnectionPool
from src.utils.validator.args_validator import ArgsValidator


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
    # def _execute_query(self, sql: str, args: Optional[Tuple] = None) -> List[Dict] | None:
    #     """执行查询语句
        
    #     Args:
    #         sql: SQL 查询语句
    #         args: SQL 参数
            
    #     Returns:
    #         List[Dict]: 查询结果列表
    #     """
    #     try:
    #         if not self.mysql:
    #             raise Exception("数据库连接未初始化")
    #         with self.mysql.get_connection() as cursor:
    #             cursor.execute(sql, args)
    #             result = cursor.fetchall()
    #             return list(result) if result else []
    #     except pymysql.MySQLError as e:
    #         # 捕获 MySQL 错误并分类
    #         if e.args[0] == 1049:  # 数据库不存在错误
    #             logger.error(f"[数据库错误] 数据库不存在，sql={sql}, error={str(e)}")
    #         elif e.args[0] == 1062:  # 唯一约束错误
    #             logger.error(f"[数据库错误] 唯一约束冲突，sql={sql}, error={str(e)}")
    #         else:
    #             logger.error(f"[数据库错误] sql={sql}, error={str(e)}")
    #         raise
    #     except Exception as e:
    #         logger.error(f"[未知错误] sql={sql}, error={str(e)}")
    #         raise RuntimeError(f"数据库操作失败: {str(e)}") from e

    # def _execute_update(self, sql: str, args: Optional[Tuple] = None) -> int | None:
    #     """执行更新语句
        
    #     Args:
    #         sql: SQL 更新语句
    #         args: SQL 参数
            
    #     Returns:
    #         int: 影响的行数
    #     """
    #     if not self.mysql:
    #         raise Exception("数据库连接未初始化")
    #     return self.mysql.execute(sql, args)

    def select_by_id(self, doc_id: str) -> Optional[Dict]:
        """根据ID查询单条记录

        Args:
            doc_id (str): 文档ID

        Returns:
            Optional[Dict]: 查询结果，如果未找到则返回 None
        """
        ArgsValidator.validate_doc_id(doc_id)
        try:
            sql = f'SELECT * FROM {self.table_name} WHERE doc_id = %s'
            data = self._execute_query(sql, (doc_id,))
            return data[0] if data else None
        except Exception as e:
            logger.error(f"查询记录失败: {e}")
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
                ArgsValidator.validate_type(conditions, dict, "conditions")
                where_clause = ' AND '.join([f"{k} = %s" for k in conditions.keys()])
                args = tuple(conditions.values())
                sql = f'SELECT {select_clause} FROM {self.table_name} WHERE {where_clause}'
            else:
                sql = f'SELECT {select_clause} FROM {self.table_name}'

            return self._execute_query(sql, args)
        except Exception as e:
            logger.error(f"查询记录失败: {e}")
            raise e

    def insert(self, data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> int:
        """插入记录(单条或多条)

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
                logger.error(f"MySQL 数据插入失败，表 {self.table_name}: {e}")
                raise APIException(ErrorCode.DB_INSERT_ERROR, f"数据插入失败: {str(e)}")
        # 多条数据
        elif isinstance(data, list) and len(data) > 0:
            try:
                # 获取所有字段
                all_fields = set()
                for record in data:
                    all_fields.update(record.keys())
                
                fields = sorted(all_fields)
                placeholders = ', '.join(['%s'] * len(fields))
                columns = ', '.join(fields)
                
                # 构建批量插入的 SQL
                sql = f'INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})'
                
                # 准备所有记录的值
                all_values = []
                for record in data:
                    # 对所有字段进行补齐，使用 None 代替空字符串
                    values = [record.get(field) for field in fields]
                    all_values.append(tuple(values))
                
                # 执行批量插入
                with self._pool.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.executemany(sql, all_values)
                        conn.commit()
                        affected_rows = cursor.rowcount

                logger.info(f"Mysql 数据插入成功, 共 {affected_rows} 条")
            except Exception as e:
                logger.error(f"MySQL 数据插入失败，表 {self.table_name}: {e}, 共 {len(data)} 条记录")
                raise APIException(ErrorCode.DB_INSERT_ERROR, f"批量数据插入失败: {str(e)}")
        return affected_rows


    def update_by_doc_id(self, doc_id: str, data: Dict[str, Any]) -> bool | None:
        """根据 doc_id 更新记录

        Args:
            doc_id (str): 文档ID
            data (Dict[str, Any]): 要更新的数据

        Returns:
            bool: 是否更新成功
        """
        ArgsValidator.validate_doc_id(doc_id)
        ArgsValidator.validate_not_empty(data, "data")
        ArgsValidator.validate_type(data, dict, "data")

        try:
            set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
            sql = f'UPDATE {self.table_name} SET {set_clause} WHERE doc_id = %s'
            values = list(data.values())
            values.append(doc_id)
            return self._execute_update(sql, tuple(values)) > 0
        except Exception as e:
            logger.error(f"更新记录失败: {e}")
            raise e

    def _soft_delete_by_id(self, doc_id: str) -> int:
        """基础软删除实现"""
        sql = f"UPDATE {self.table_name} SET is_soft_deleted = TRUE, updated_at = %s WHERE doc_id = %s"
        return self._execute_update(sql, (datetime.now(), doc_id))

    def _hard_delete_by_id(self, doc_id: str) -> int:
        """基础硬删除实现"""
        sql = f"DELETE FROM {self.table_name} WHERE doc_id = %s"
        return self._execute_update(sql, (doc_id,))

    def delete_by_doc_id(self, doc_id: str, is_soft_deleted: bool = False) -> int:
        """通用删除接口，支持软/硬删除"""
        try:
            if is_soft_deleted:
                return self._soft_delete_by_id(doc_id)
            else:
                return self._hard_delete_by_id(doc_id)
        except pymysql.MySQLError as e:
            logger.error(f"[删除记录失败] doc_id={doc_id}, is_soft_deleted={is_soft_deleted}, error={str(e)}")
            raise RuntimeError(f"数据库删除失败: {str(e)}") from e
        except Exception as e:
            logger.error(f"[未知错误] 删除记录失败, doc_id={doc_id}, is_soft_deleted={is_soft_deleted}, error={str(e)}")
            raise e
