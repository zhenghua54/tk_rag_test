"""数据库操作"""
from typing import List, Dict, Optional
from config.settings import Config
from src.api.response import ErrorCode, APIException
from src.database.mysql.base import BaseDBOperation
from src.utils.common.logger import logger


def normalize_records(records: List[Dict]) -> List[Dict]:
    """
    规范化多条字典记录，确保每条记录字段一致，不存在字段缺失。
    对缺失字段使用 None 补齐，方便批量数据库插入时字段对齐。

    Args:
        records (List[Dict]): 输入的多条字典记录，字段可能不一致。

    Returns:
        List[Dict]: 规范化后的记录列表，每条记录字段完全一致。
    """

    # 收集所有记录中出现的字段, 形成完整集合
    all_fields = set()
    for record in records:
        all_fields.update(record.keys())

    # 对字段排序,保证字段顺序一致(可选, 可修改)
    fields = sorted(all_fields)

    normalize = []
    for record in records:
        # 按照排序后的字段顺序, 遍历每条记录缺失的字段, 以 None 补齐
        normalize.append({field: record.get(field, None) for field in fields})

    return normalize


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
        try:
            return self.select_by_id(doc_id)
        except Exception as e:
            logger.error(f"[查询失败] table={self.table_name}, error={str(e)}")
            raise e

    def get_non_pdf_files(self) -> Optional[List[Dict]]:
        """获取所有非PDF文件

        Returns:
            List[Dict]: 非PDF文件的数据库记录列表
        """
        try:
            sql = f'SELECT * FROM %s WHERE source_document_pdf_path IS NULL'
            return self._execute_query(sql, (self.table_name,))
        except Exception as e:
            logger.error(f"[查询非PDF文件失败] table={self.table_name}, error={str(e)}")
            raise e

    def get_pdf_files(self) -> Optional[List[Dict]]:
        """获取所有PDF文件

        Returns:
            List[Dict]: PDF文件的数据库记录列表
        """
        try:
            sql = f'SELECT * FROM % WHERE source_document_pdf_path IS NOT NULL'
            return self._execute_query(sql, (self.table_name,))
        except Exception as e:
            logger.error(f"[查询PDF文件失败] table={self.table_name}, error={str(e)}")

            raise e

    def insert_data(self, args: Dict):
        """插入文件信息

        Args:
            args (Dict): 文件信息字典，包含文档ID和其他相关信息

        Returns:
            bool: 插入是否成功
        """
        try:
            return self.insert(args)
        except Exception as e:
            raise e

    def update_data(self, doc_id: str, args: Dict) -> Optional[bool]:
        """更新文件信息

        Args:
            doc_id (str): 文档ID
            args (Dict): 文件信息字典，包含除了文档ID外的其他相关信息

        Returns:
            bool: 更新是否成功
        """
        try:
            return self.update_by_doc_id(doc_id=doc_id, data=args)
        except Exception as e:
            raise e


class ChunkOperation(BaseDBOperation):
    """文档分块表(chunk_info)操作类"""

    def __init__(self):
        super().__init__(Config.MYSQL_CONFIG['segment_info_table'])

    def get_chunk_by_doc_id(self, doc_id: str) -> Optional[List[Dict]]:
        """获取文档的所有分块

        Args:
            doc_id (str): 文档ID

        Returns:
            List[Dict]: 文档分块的数据库记录列表
        """
        try:
            return self.select_record(conditions={'doc_id': doc_id})
        except Exception as e:
            logger.error(f"获取文档分块失败: {e}")
            raise e

    def insert_chunks(self, chunks: List[Dict]) -> Optional[int]:
        """插入分块信息

        Args:
            chunks (List[Dict]): 分块信息列表，每个分块是一个字典, 列表中每个元素字段需一致

        Returns:
            bool: 插入是否成功
        """
        try:
            # 统一字段
            chunks = normalize_records(chunks)
            return self.insert(chunks)
        except Exception as e:
            raise e

    def delete_chunk_by_seg_id(self, seg_id: str) -> Optional[Dict]:
        """根据分段ID删除分块

        Args:
            seg_id (str): 分段ID

        Returns:
            Optional[Dict]: 删除操作的结果，如果成功则返回删除的记录数，否则返回 None
        """
        try:
            sql = f'DELETE FROM %s WHERE seg_id = %s'
            result = self._execute_update(sql, (self.table_name, seg_id))
            return {'affected_rows': result}
        except Exception as e:
            logger.error(f"删除分块失败: {e}")
            raise e


class PermissionOperation(BaseDBOperation):
    """权限表(permission_info)操作类"""

    def __init__(self):
        super().__init__(Config.MYSQL_CONFIG['permission_info_table'])

    def insert_datas(self, args: Dict) -> Optional[bool]:
        """插入权限信息

        Args:
            args (Dict): 权限信息字典，包含部门ID、文档ID等信息

        Returns:
            bool: 插入是否成功
        """
        res = self.insert(args)
        if not res:
            raise APIException(ErrorCode.MYSQL_INSERT_FAIL)
        else:
            return res




if __name__ == '__main__':
    # 使用上下文管理器
    with FileInfoOperation() as file_op:
        # 查询文件
        file_info = file_op.get_file_by_doc_id("215f2f8cfce518061941a70ff6c9ec0a3bb92ae6230e84f3d5777b7f9a1fac83")

        # 更新文件
        file_op.update_by_doc_id("215f2f8cfce518061941a70ff6c9ec0a3bb92ae6230e84f3d5777b7f9a1fac83",
                                 {"source_document_type": ".p"})

        # 删除文件
        file_op.delete_by_doc_id("f10e704816fda7c6cbf1d7f4aebc98a6ac1bfbe0602e0951af81277876adbcbc")
