# src/database/mysql/response.py
"""数据库操作基类"""

from typing import List, Dict, Any, Optional, Tuple
from config.settings import Config
from src.utils.common.logger import logger
from src.database.mysql.connection import MySQLConnect
from src.utils.common.args_validator import ArgsValidator


class BaseDBOperation:
    """数据库操作基类"""

    def __init__(self, table_name: str):
        """初始化数据库操作类

        Args:
            table_name (str): 表名
        """
        ArgsValidator.validity_not_empty(table_name, "table_name")
        ArgsValidator.validity_type(table_name, str, "table_name")
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

    def _execute_query(self, sql: str, args: Optional[Tuple] = None) -> List[Dict]:
        """执行查询语句
        
        Args:
            sql: SQL 查询语句
            args: SQL 参数
            
        Returns:
            List[Dict]: 查询结果列表
        """
        if not self.mysql:
            raise Exception("数据库连接未初始化")
        with self.mysql.get_connection() as cursor:
            cursor.execute(sql, args)
            result = cursor.fetchall()
            return list(result) if result else []

    def _execute_update(self, sql: str, args: Optional[Tuple] = None) -> int:
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
        ArgsValidator.validity_doc_id(doc_id)
        try:
            sql = f'SELECT * FROM {self.table_name} WHERE doc_id = %s'
            data = self._execute_query(sql, (doc_id,))
            return data[0] if data else None
        except Exception as e:
            logger.error(f"查询记录失败: {e}")
            return None

    def select_record(self, fields: Optional[List[str]] = None, conditions: Optional[Dict] = None) -> List[Dict]:
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
                ArgsValidator.validity_type(conditions, dict, "conditions")
                where_clause = ' AND '.join([f"{k} = %s" for k in conditions.keys()])
                args = tuple(conditions.values())
                sql = f'SELECT {select_clause} FROM {self.table_name} WHERE {where_clause}'
            else:
                sql = f'SELECT {select_clause} FROM {self.table_name}'

            return self._execute_query(sql, args)
        except Exception as e:
            logger.error(f"查询记录失败: {e}")
            return []

    def select_doc_ids(self, conditions: Dict = None) -> List[str]:
        """查询所有文档 ID

        Args:
            conditions (Dict, optional): 查询条件，默认为 None

        Returns:
            List[str]: 查询到的文档 ID 列表
        """
        try:
            if conditions:
                where_clause = ' AND '.join([f"{k} = %s" for k in conditions.keys()])
                sql = f'SELECT doc_id FROM {self.table_name} WHERE {where_clause}'
                data = self._execute_query(sql, tuple(conditions.values()))
            else:
                sql = f'SELECT doc_id FROM {self.table_name}'
                data = self._execute_query(sql)
            return [row['doc_id'] for row in data] if data else []
        except Exception as e:
            logger.error(f"查询文档 ID 失败: {e}")
            return []

    def insert(self, data: Dict[str, Any]) -> bool:
        """插入单条记录

        Args:
            data (Dict[str, Any]): 要插入的数据

        Returns:
            bool: 是否插入成功
        """
        ArgsValidator.validity_not_empty(data, "data")
        ArgsValidator.validity_type(data, dict, "data")

        try:
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['%s'] * len(data))
            sql = f'INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})'
            return self._execute_update(sql, tuple(data.values())) > 0
        except Exception as e:
            logger.error(f"MySQL 数据插入失败，表 {self.table_name}: {e}")
            return False

    def update_by_doc_id(self, doc_id: str, data: Dict[str, Any]) -> bool:
        """根据 doc_id 更新记录

        Args:
            doc_id (str): 文档ID
            data (Dict[str, Any]): 要更新的数据

        Returns:
            bool: 是否更新成功
        """
        ArgsValidator.validity_doc_id(doc_id)
        ArgsValidator.validity_not_empty(data, "data")
        ArgsValidator.validity_type(data, dict, "data")

        try:
            set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
            sql = f'UPDATE {self.table_name} SET {set_clause} WHERE doc_id = %s'
            values = list(data.values())
            values.append(doc_id)
            return self._execute_update(sql, tuple(values)) > 0
        except Exception as e:
            logger.error(f"更新记录失败: {e}")
            return False

    def delete_by_doc_id(self, doc_id: str) -> bool:
        """根据 doc_id 删除记录

        Args:
            doc_id (str): 文档ID

        Returns:
            bool: 是否删除成功
        """
        ArgsValidator.validity_doc_id(doc_id)

        try:
            sql = f'DELETE FROM {self.table_name} WHERE doc_id = %s'
            return self._execute_update(sql, (doc_id,)) > 0
        except Exception as e:
            logger.error(f"删除记录失败: {e}")
            return False
