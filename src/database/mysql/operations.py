"""数据库操作"""
from typing import List, Dict, Optional
from config.settings import Config
from src.api.response import ErrorCode
from src.database.mysql.base import BaseDBOperation
from src.utils.common.logger import logger
from src.utils.common.args_validator import ArgsValidator


class FileInfoOperation(BaseDBOperation):
    """文件信息表(file_info)操作类"""

    def __init__(self):
        super().__init__(Config.MYSQL_CONFIG['file_info_table'])

    def get_file_by_doc_id(self, doc_id: str) -> Optional[Dict]:
        """根据文档ID获取文件信息

        Args:
            doc_id (str): 文档ID

        Returns:
            Optional[Dict]: 查询到的文件信息字典，如果未找到则返回 None
        """
        ArgsValidator.validity_doc_id(doc_id)
        return self.select_by_id(doc_id)

    def get_non_pdf_files(self) -> List[Dict]:
        """获取所有非PDF文件

        Returns:
            List[Dict]: 非PDF文件的数据库记录列表
        """
        try:
            sql = f'SELECT * FROM {self.table_name} WHERE source_document_pdf_path IS NULL'
            return self._execute_query(sql)
        except Exception as e:
            logger.error(f"获取非PDF文件失败: {e}")
            return []

    def get_pdf_files(self) -> List[Dict]:
        """获取所有PDF文件

        Returns:
            List[Dict]: PDF文件的数据库记录列表
        """
        try:
            sql = f'SELECT * FROM {self.table_name} WHERE source_document_pdf_path IS NOT NULL'
            return self._execute_query(sql)
        except Exception as e:
            logger.error(f"获取PDF文件失败: {e}")
            return []

    def insert_datas(self, args: Dict):
        """插入文件信息

        Args:
            args (Dict): 文件信息字典，包含文档ID和其他相关信息

        Returns:
            bool: 插入是否成功
        """
        ArgsValidator.validity_type(args, dict, "args")
        ArgsValidator.validity_doc_id(args.get('doc_id'))

        res = self.insert(args)
        if not res:
            raise ValueError(ErrorCode.MYSQL_INSERT_FAIL, ErrorCode.MYSQL_INSERT_FAIL)
        else:
            return res

    def insert_single(self,doc_id: str, args: Dict):
        """插入单条文件信息

        Args:
            doc_id (str): 文档ID
            args (Dict): 文件信息字典，包含除了文档ID外的其他相关信息

        Returns:
            bool: 插入是否成功
        """
        ArgsValidator.validity_doc_id(doc_id)
        ArgsValidator.validity_type(args, dict, "args")
        try:
            return self.update_by_doc_id(doc_id=doc_id, data=args)
        except Exception as e:
            raise  ValueError(f"插入文件信息失败: {e}")
            return False

class ChunkOperation(BaseDBOperation):
    """文档分块表(chunk_info)操作类"""

    def __init__(self):
        super().__init__(Config.MYSQL_CONFIG['segment_info_table'])

    def get_chunk_by_doc_id(self, doc_id: str) -> List[Dict]:
        """获取文档的所有分块

        Args:
            doc_id (str): 文档ID

        Returns:
            List[Dict]: 文档分块的数据库记录列表
        """
        ArgsValidator.validate_doc_id(doc_id)
        return self.select_record(conditions={'doc_id': doc_id})

    def insert_chunks(self, chunks: List[Dict]) -> tuple[int, int]:
        """批量插入分块

        Args:
            chunks (List[Dict]): 分块信息列表，每个分块是一个字典

        Returns:
            tuple[int, int]: (成功插入的分块数量, 失败的分块数量)
        """
        ArgsValidator.validity_list_not_empty(chunks, "chunks")
        ArgsValidator.validity_type(chunks, list, "chunks")
        
        success_count = 0
        fail_count = 0

        for chunk in chunks:
            if self.insert(chunk):
                success_count += 1
            else:
                fail_count += 1

        return success_count, fail_count

    def delete_chunk_by_doc_id(self, doc_id: str) -> Optional[Dict]:
        """根据文档 ID 删除所有分块

        Args:
            doc_id (str): 文档ID

        Returns:
            Optional[Dict]: 删除操作的结果，如果成功则返回删除的记录数，否则返回 None
        """
        ArgsValidator.validate_doc_id(doc_id)
        
        try:
            sql = f'DELETE FROM {self.table_name} WHERE doc_id = %s'
            result = self._execute_update(sql, (doc_id,))
            return {'affected_rows': result}
        except Exception as e:
            logger.error(f"删除分块失败: {e}")
            return None

    def delete_chunk_by_segment_id(self, segment_id: str) -> Optional[Dict]:
        """根据分段ID删除分块

        Args:
            segment_id (str): 分段ID

        Returns:
            Optional[Dict]: 删除操作的结果，如果成功则返回删除的记录数，否则返回 None
        """
        ArgsValidator.validate_segment_id(segment_id)
        
        try:
            sql = f'DELETE FROM {self.table_name} WHERE segment_id = %s'
            result = self._execute_update(sql, (segment_id,))
            return {'affected_rows': result}
        except Exception as e:
            logger.error(f"删除分块失败: {e}")
            return None


class PermissionOperation(BaseDBOperation):
    """权限表(permission_info)操作类"""

    def __init__(self):
        super().__init__(Config.MYSQL_CONFIG['permission_info_table'])

    def get_doc_id_by_department(self, department_id: str) -> List[Dict]:
        """根据部门 ID 获取文档列表

        Args:
            department_id (str): 部门 ID

        Returns:
            List[Dict]: 部门下的文档信息列表
        """
        ArgsValidator.validity_department_id(department_id)
        return self.select_record(conditions={'department_id': department_id})

    def insert_datas(self, args: Dict) -> bool:
        """插入权限信息

        Args:
            args (Dict): 权限信息字典，包含部门ID、文档ID等信息

        Returns:
            bool: 插入是否成功
        """
        ArgsValidator.validity_type(args, dict, "args")
        ArgsValidator.validity_doc_id(args.get('doc_id'))
        ArgsValidator.validity_department_id(args.get('department_id'))


        res = self.insert(args)
        if not res:
            raise ValueError(ErrorCode.MYSQL_INSERT_FAIL, ErrorCode.MYSQL_INSERT_FAIL)
        else:
            return res

    def update_permission_by_doc_id(self, doc_id: str, departments_id: list[str]) -> Optional[Dict]:
        """根据文档 ID 批量更新对应的部门权限

        Args:
            doc_id (str): 文档 ID
            departments_id (list[str]): 部门 ID 列表

        Returns:
            Optional[Dict]: 更新操作的结果，如果成功则返回更新的记录数，否则返回 None
        """
        # 参数校验
        ArgsValidator.validate_doc_id(doc_id)
        ArgsValidator.validity_list_not_empty(departments_id, "department_id")

        try:
            # 删除原有权限数据记录
            delete_sql = f'DELETE FROM {self.table_name} WHERE doc_id = %s'
            self._execute_update(delete_sql, (doc_id,))

            # 插入新的权限数据
            values = [(doc_id, department_id) for department_id in departments_id]
            insert_sql = f'INSERT INTO {self.table_name} (doc_id, department_id) VALUES (%s, %s)'
            result = self._execute_update(insert_sql, tuple(values))
            return {'affected_rows': result}
        except Exception as e:
            logger.error(f"更新权限失败: {e}")
            return None


if __name__ == '__main__':
    # 使用上下文管理器
    with FileInfoOperation() as file_op:
        # 查询文件
        file_info = file_op.get_file_by_doc_id("215f2f8cfce518061941a70ff6c9ec0a3bb92ae6230e84f3d5777b7f9a1fac83")
        
        # 更新文件
        file_op.update_by_doc_id("215f2f8cfce518061941a70ff6c9ec0a3bb92ae6230e84f3d5777b7f9a1fac83", {"source_document_type": ".p"})
        
        # 删除文件
        file_op.delete_by_doc_id("f10e704816fda7c6cbf1d7f4aebc98a6ac1bfbe0602e0951af81277876adbcbc")