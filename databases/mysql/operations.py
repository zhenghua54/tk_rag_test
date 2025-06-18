"""数据库操作"""
from typing import List, Dict, Optional, Any
from config.global_config import GlobalConfig
from error_codes import ErrorCode
from api.response import APIException
from databases.mysql.base import BaseDBOperation
from utils.log_utils import logger


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
        super().__init__(GlobalConfig.MYSQL_CONFIG['file_info_table'])

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
        super().__init__(GlobalConfig.MYSQL_CONFIG['segment_info_table'])

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

    def get_segment_contents(self, seg_ids: List[str] = None, doc_ids: List[str] = None, permission_ids: str = None) -> \
            List[Dict[str, Any]]:
        """从 MySQL 获取片段信息，包括关联的文档和权限信息

        Args:
            seg_ids: 片段 ID 列表
            doc_ids: 文档 ID 列表
            permission_ids: 权限 ID

        Returns:
            List[Dict[str, Any]]: 片段信息列表，包含所有字段
        """
        try:
            # 确保至少有一个查询条件
            if not seg_ids and not doc_ids:
                logger.error("必须提供 seg_ids 或 doc_ids 参数")
                return []

            # 构建关联查询SQL - 使用二进制比较避免字符集冲突
            sql = """
                  SELECT s.*,             -- 片段信息表的所有字段  
                         f.doc_http_url,  -- 文档信息表的字段  
                         f.created_at as doc_created_at,
                         f.updated_at as doc_updated_at,
                         p.permission_ids -- 权限信息表的字段
                  FROM segment_info s
                           LEFT JOIN doc_info f ON s.doc_id = f.doc_id
                           LEFT JOIN permission_info p ON s.doc_id = p.doc_id
                  WHERE 1 = 1 \
                  """

            # 添加查询条件
            params = []
            if seg_ids:
                if len(seg_ids) == 1:
                    sql += " AND s.seg_id = %s"
                    params.append(seg_ids[0])
                else:
                    placeholders = ', '.join(['%s'] * len(seg_ids))
                    sql += f" AND s.seg_id IN ({placeholders})"
                    params.extend(seg_ids)

            if doc_ids:
                if len(doc_ids) == 1:
                    sql += " AND s.doc_id = %s"
                    params.append(doc_ids[0])
                else:
                    placeholders = ', '.join(['%s'] * len(doc_ids))
                    sql += f" AND s.doc_id IN ({placeholders})"
                    params.extend(doc_ids)

            # 如果提供了权限ID，直接在SQL中添加权限过滤
            if permission_ids:
                sql += " AND (p.permission_ids = %s OR p.permission_ids IS NULL)"
                params.append(permission_ids)

            # 执行查询
            segment_info = self._execute_query(sql, tuple(params))

            # 处理查询结果
            if not segment_info:
                return []

            logger.info(f"mysql 查询到 {len(segment_info)} 条记录")

            # 转换结果格式
            results = []
            for record in segment_info:
                # 记录权限信息用于调试
                record_permission = record.get("permission_ids")
                logger.debug(f"记录权限信息: {record_permission}, 用户权限: {permission_ids}")

                # 如果指定了权限ID，则进行过滤 (这里作为双重保险，实际上SQL已经过滤过了)
                if permission_ids and record_permission and record_permission != permission_ids:
                    logger.debug(
                        f"权限过滤: 跳过文档 {record.get('seg_id')}, 权限不匹配 (需要: {permission_ids}, 实际: {record_permission})")
                    continue

                result = {
                    # 片段信息
                    "seg_id": record.get("seg_id"),
                    "seg_content": record.get("seg_content"),
                    "seg_type": record.get("seg_type"),
                    "seg_image_path": record.get("seg_image_path", ""),
                    "seg_caption": record.get("seg_caption", ""),
                    "seg_footnote": record.get("seg_footnote", ""),
                    "seg_page_idx": record.get("seg_page_idx", 0),

                    # 文档信息
                    "doc_id": record.get("doc_id"),
                    "doc_http_url": record.get("doc_http_url", ""),
                    "doc_created_at": record.get("doc_created_at", ""),
                    "doc_updated_at": record.get("doc_updated_at", ""),

                    # 权限信息
                    "permission_ids": record.get("permission_ids", "")
                }
                results.append(result)

            return results

        except Exception as error:
            logger.error(f"获取片段信息失败: {str(error)}")
            return []

    def get_seg_content(self, seg_id: str) -> str:
        """从 MySQL 获取 segment 原文内容

        Args:
            seg_id: segment ID

        Returns:
            str: segment 原文内容
        """
        try:
            chunk_info = self.select_record(
                conditions={"seg_id": seg_id}
            )
            return chunk_info[0] if chunk_info else ""
        except Exception as error:
            logger.error(f"获取 segment 原文失败: {str(error)}")
            return ""


class PermissionOperation(BaseDBOperation):
    """权限表(permission_info)操作类"""

    def __init__(self):
        super().__init__(GlobalConfig.MYSQL_CONFIG['permission_info_table'])

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


def check_duplicate_doc(doc_id: str):
    """验证文件是否已上传

    Args:
        doc_id: 文档Id

    Returns:
        dict: 如果文件存在，返回文件信息， 如果文件处理失败，返回 "failed"，否则返回 doc_id
    """
    # 校验状态结果
    result = {
        "process_status": None,
        "doc_info": dict()
    }
    try:
        with FileInfoOperation() as file_op:
            doc_info = file_op.get_file_by_doc_id(doc_id)
        if not doc_info:
            return result

        process_status = doc_info.get("process_status")
        if not process_status:
            logger.warning(f"文档状态为空: doc_id={doc_id}")
            return result

        # 文件状态异常,重新上传
        if process_status in GlobalConfig.FILE_STATUS.get("error"):
            result["process_status"] = process_status
            result["doc_info"] = doc_info
        # 文件状态正常,限制重复上传
        elif process_status in GlobalConfig.FILE_STATUS.get("normal"):
            raise APIException(ErrorCode.FILE_EXISTS_PROCESSED)

        return result

    except APIException:
        raise
    except Exception as e:
        logger.error(f"[文档查重失败] doc_id={doc_id}, error={str(e)}")
        raise APIException(ErrorCode.MYSQL_QUERY_FAIL, f"文档查重失败: {str(e)}")


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
