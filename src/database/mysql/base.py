# src/database/mysql/response.py
"""数据库操作基类"""
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import pymysql

from config.settings import Config
from src.utils.common.logger import logger
from src.database.mysql.connection import MySQLConnect
from src.utils.validator.args_validator import ArgsValidator


class BaseDBOperation:
    """数据库操作基类"""

    def __init__(self, table_name: str):
        """初始化数据库操作类

        Args:
            table_name (str): 表名
        """
        ArgsValidator.validate_not_empty(table_name, "table_name")
        ArgsValidator.validate_type(table_name, str, "table_name")
        self.table_name = table_name
        self.mysql = None

    def __enter__(self):
        """上下文管理器入口"""
        self.mysql = MySQLConnect(
            host=Config.MYSQL_CONFIG['host'],
            user=Config.MYSQL_CONFIG['user'],
            password=Config.MYSQL_CONFIG['password'],
            charset=Config.MYSQL_CONFIG['charset'],
            database=Config.MYSQL_CONFIG['database']
        )
        self.mysql.use_db()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        if self.mysql:
            self.mysql.close()

    def _execute_query(self, sql: str, args: Optional[Tuple] = None) -> List[Dict] | None:
        """执行查询语句
        
        Args:
            sql: SQL 查询语句
            args: SQL 参数
            
        Returns:
            List[Dict]: 查询结果列表
        """
        try:
            if not self.mysql:
                raise Exception("数据库连接未初始化")
            with self.mysql.get_connection() as cursor:
                cursor.execute(sql, args)
                result = cursor.fetchall()
                return list(result) if result else []
        except pymysql.MySQLError as e:
            # 捕获 MySQL 错误并分类
            if e.args[0] == 1049:  # 数据库不存在错误
                logger.error(f"[数据库错误] 数据库不存在，sql={sql}, error={str(e)}")
            elif e.args[0] == 1062:  # 唯一约束错误
                logger.error(f"[数据库错误] 唯一约束冲突，sql={sql}, error={str(e)}")
            else:
                logger.error(f"[数据库错误] sql={sql}, error={str(e)}")
            raise
        except Exception as e:
            logger.error(f"[未知错误] sql={sql}, error={str(e)}")
            raise RuntimeError(f"数据库操作失败: {str(e)}") from e

    def _execute_update(self, sql: str, args: Optional[Tuple] = None) -> int | None:
        """执行更新语句
        
        Args:
            sql: SQL 更新语句
            args: SQL 参数
            
        Returns:
            int: 影响的行数
        """
        if not self.mysql:
            raise Exception("数据库连接未初始化")
        return self.mysql.execute(sql, args)

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

    def insert(self, data: Dict[str, Any]) -> bool:
        """插入单条记录

        Args:
            data (Dict[str, Any]): 要插入的数据

        Returns:
            bool: 是否插入成功
        """
        ArgsValidator.validate_not_empty(data, "data")
        ArgsValidator.validate_type(data, dict, "data")

        try:
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['%s'] * len(data))
            sql = f'INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})'
            return self._execute_update(sql, tuple(data.values())) > 0
        except Exception as e:
            logger.error(f"MySQL 数据插入失败，表 {self.table_name}: {e}")
            raise e

    def insert_many(self, data_list: List[Dict[str, Any]]) -> int:
        """插入多条记录

        Args:
            data_list (List[Dict[str, Any]]): 要插入的数据列表，每个元素是一个字典

        Returns:
            int: 影响的行数
        """
        if not data_list:
            return 0
            
        try:
            # 确保所有记录有相同的字段
            keys = list(data_list[0].keys())
            
            # 使用反引号包裹字段名以避免关键字冲突
            columns = ', '.join(f'`{k}`' for k in keys)
            placeholders = ', '.join(['%s'] * len(keys))
            
            # 确保SQL语句格式正确
            sql = f'INSERT INTO `{self.table_name}` ({columns}) VALUES ({placeholders})'
            
            # 使用循环逐条插入而不是使用executemany
            affected_rows = 0
            for data in data_list:
                # 确保按照相同的顺序提取值
                values = []
                for k in keys:
                    val = data.get(k, "")
                    # 确保None值被转换为空字符串
                    if val is None:
                        val = ""
                    values.append(val)
                
                # 执行插入
                try:
                    affected_rows += self.mysql.execute(sql, tuple(values))
                except Exception as e:
                    # 输出详细错误信息以便调试
                    logger.error(f"执行SQL失败: {sql}")
                    logger.error(f"参数值: {values}")
                    raise
            
            return affected_rows
        except Exception as e:
            logger.error(f"MySQL 批量数据插入失败，表 {self.table_name}: {e}")
            raise e

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
