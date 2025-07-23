"""数据库操作"""

import json
from datetime import datetime
from typing import Any

from config.global_config import GlobalConfig
from databases.mysql.base import BaseDBOperation
from utils.log_utils import logger
from utils.table_linearized import unescape_html_table


def normalize_records(records: list[dict]) -> list[dict]:
    """
    规范化多条字典记录，确保每条记录字段一致，不存在字段缺失。
    对缺失字段使用 None 补齐，方便批量数据库插入时字段对齐。

    Args:
        records (list[dict]): 输入的多条字典记录，字段可能不一致。

    Returns:
        list[dict]: 规范化后的记录列表，每条记录字段完全一致。
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
        super().__init__(GlobalConfig.MYSQL_CONFIG["file_info_table"])

    def get_file_by_doc_id(self, doc_id: str) -> dict | None:
        """根据文档ID获取文件信息

        Args:
            doc_id (str): 文档ID

        Returns:
            dict | None: 查询到的文件信息字典，如果未找到则返回 None
        """
        try:
            return self.select_by_id(doc_id)
        except Exception as e:
            logger.error(f"[MySQL查询失败] table={self.table_name}, error_msg={str(e)}")
            raise e

    def get_non_pdf_files(self) -> list[dict] | None:
        """获取所有非PDF文件

        Returns:
            list[dict] | None: 非PDF文件的数据库记录列表
        """
        try:
            sql = f"SELECT * FROM {self.table_name} WHERE doc_pdf_path IS NULL"
            return self._execute_query(sql)
        except Exception as e:
            logger.error(f"[查询非PDF文件失败] table={self.table_name}, error={str(e)}")
            raise e

    def get_pdf_files(self) -> list[dict] | None:
        """获取所有PDF文件

        Returns:
            list[dict] | None: PDF文件的数据库记录列表
        """
        try:
            sql = f"SELECT * FROM {self.table_name} WHERE doc_pdf_path IS NOT NULL"
            return self._execute_query(sql)
        except Exception as e:
            logger.error(f"[查询PDF文件失败] table={self.table_name}, error={str(e)}")

            raise e

    def insert_data(self, args: dict):
        """插入文件信息

        Args:
            args: 文件信息字典，包含文档ID和其他相关信息

        Returns:
            bool: 插入是否成功
        """
        try:
            return self.insert(args)
        except Exception as e:
            raise e

    def update_data(self, doc_id: str, args: dict) -> bool | None:
        """更新文件信息

        Args:
            doc_id: 文档ID
            args: 文件信息字典，包含除了文档ID外的其他相关信息

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
        super().__init__(GlobalConfig.MYSQL_CONFIG["segment_info_table"])

    def get_chunk_by_doc_id(self, doc_id: str) -> list[dict] | None:
        """获取文档的所有分块

        Args:
            doc_id (str): 文档ID

        Returns:
            list[dict]: 文档分块的数据库记录列表
        """
        try:
            return self.select_record(conditions={"doc_id": doc_id})
        except Exception as e:
            logger.error(f"获取文档分块失败: {str(e)}")
            raise e

    def insert_chunks(self, chunks: list[dict]) -> int | None:
        """插入分块信息

        Args:
            chunks: 分块信息列表，每个分块是一个字典, 列表中每个元素字段需一致

        Returns:
            bool: 插入是否成功
        """
        try:
            # 统一字段
            chunks = normalize_records(chunks)
            return self.insert(chunks)
        except Exception as e:
            raise e

    def delete_chunk_by_seg_id(self, seg_id: str) -> dict | None:
        """根据分段ID删除分块

        Args:
            seg_id (str): 分段ID

        Returns:
            dict | None: 删除操作的结果，如果成功则返回删除的记录数，否则返回 None
        """
        try:
            sql = "DELETE FROM %s WHERE seg_id = %s"
            result = self._execute_update(sql, (self.table_name, seg_id))
            return {"affected_rows": result}
        except Exception as e:
            logger.error(f"删除分块失败: {str(e)}")
            raise e

    def get_segment_contents(
        self, seg_id_list: list[str] = None, doc_id_list: list[str] = None
    ) -> list[dict[str, Any]]:
        """从 MySQL 获取片段信息，包括关联的文档和权限信息

        Args:
            seg_id_list: 片段 ID 列表
            doc_id_list: 文档 ID 列表

        Returns:
            list[dict[str, Any]]: 片段信息列表，包含所有字段, 列表中每个元素字段需一致
        """
        try:
            # 确保至少有一个查询条件
            if not seg_id_list and not doc_id_list:
                logger.error("必须提供 seg_ids 或 doc_ids 参数")
                return []

            sql = """
                  SELECT s.doc_id,
                         s.seg_id,
                         s.seg_content,
                         s.seg_page_idx,
                         s.seg_type,
                         f.doc_name,
                         f.doc_http_url,
                         d.page_png_path
                  FROM segment_info s
                           LEFT JOIN doc_info f ON s.doc_id = f.doc_id
                           LEFT JOIN doc_page_info d ON s.doc_id = d.doc_id AND s.seg_page_idx = d.page_idx
                  WHERE 1 = 1 """

            # 添加查询条件
            params = []

            # 列表,使用 IN, sql 不能直接传列表
            if seg_id_list and len(seg_id_list) > 0:
                placeholders = ", ".join(["%s"] * len(seg_id_list))
                sql += f" AND s.seg_id IN ({placeholders}) "
                params.extend(seg_id_list)

            if doc_id_list and len(doc_id_list) > 0:
                placeholders = ", ".join(["%s"] * len(doc_id_list))
                sql += f" AND s.doc_id IN ({placeholders}) "
                params.extend(doc_id_list)

            # 添加 GROUP BY 子句, 过滤重复内容
            sql += """
            GROUP BY s.doc_id, s.seg_id, s.seg_content, s.seg_page_idx, s.seg_type,
                     f.doc_name, f.doc_http_url, d.page_png_path
            """

            # logger.info(f"最终的查询 SQL 为: {sql}")
            # logger.info(f"最终的查询 参数 为: {params}")

            # 执行查询
            segment_info: list[dict[str, Any]] = self._execute_query(sql, tuple(params))

            # 处理查询结果
            if not segment_info:
                return []

            # 转换结果格式
            results = []
            for record in segment_info:
                # 增加: 表格原文反编码
                if record.get("seg_type") == "table":
                    seg_content = unescape_html_table(record.get("seg_content"))
                else:
                    seg_content = record.get("seg_content")

                result = {
                    # 片段信息
                    "doc_id": record.get("doc_id"),
                    "seg_id": record.get("seg_id"),
                    "seg_content": seg_content,
                    "seg_page_idx": record.get("seg_page_idx"),
                    # 文档信息
                    "doc_name": record.get("doc_name"),
                    "doc_http_url": record.get("doc_http_url", ""),
                    "created_at": record.get("created_at"),
                    "updated_at": record.get("updated_at"),
                    # 权限信息
                    "all_permission_ids": record.get("all_permission_ids", ""),
                    # 分页信息
                    "page_png_path": record.get("page_png_path", ""),
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
            chunk_info = self.select_record(conditions={"seg_id": seg_id})
            return chunk_info[0] if chunk_info else ""
        except Exception as error:
            logger.error(f"获取 segment 原文失败: {str(error)}")
            return ""


class PermissionOperation(BaseDBOperation):
    """权限表(permission_info)操作类"""

    def __init__(self, conn=None):
        super().__init__(GlobalConfig.MYSQL_CONFIG["permission_info_table"], conn=conn)

    def insert_datas(self, args: dict[str, Any] | list[dict[str, Any]]) -> int | None:
        """插入权限信息

        Args:
            args: 权限信息字典，包含部门ID、文档ID等信息

        Returns:
            bool: 插入是否成功
        """
        res = self.insert(args)
        if not res:
            raise ValueError("[Mysql] 插入数据失败")
        else:
            return res

    def get_ids_by_permission(self, permission_type: str, subject_ids: list[str]):
        """
        根据权限 ID 返回对应的 doc_id

        Args:
            permission_type: 权限类型,目前只有: department
            subject_ids: 处理后的权限 ID 列表

        Returns:
            list[str]: 检索到的 doc_id 列表
        """

        if not permission_type.strip():
            raise ValueError("权限类型不能为空")

        if not subject_ids:
            subject_ids = []

        # 构建 IN 子句的占位符
        placeholders = ", ".join(["%s"] * len(subject_ids))
        sql = f"""
        select doc_id from {self.table_name}
        where permission_type = %s 
        and (
            subject_id IN ({placeholders})
            OR subject_id IS NULL 
        )
        """

        # 构建参数: permission_type + subject_ids 列表
        params = [permission_type] + subject_ids

        mysql_result: list[dict] = self._execute_query(sql, tuple(params))

        doc_ids = [row["doc_id"] for row in mysql_result if row.get("doc_id")]

        return doc_ids


class PageOperation(BaseDBOperation):
    """页面表(page_info)操作类"""

    def __init__(self):
        super().__init__(GlobalConfig.MYSQL_CONFIG["doc_page_info_table"])


class ChatSessionOperation(BaseDBOperation):
    """会话表(chat_sessions)操作类"""

    def __init__(self):
        super().__init__(GlobalConfig.MYSQL_CONFIG["chat_sessions_table"])

    def create_or_update_session(self, session_id: str):
        """创建或更新会话

        Args:
            session_id: 会话ID（必需）
        """
        try:
            # 先尝试更新
            existing = self.select_record(conditions={"session_id": session_id})
            if existing:
                # 更新会话
                data = {"updated_at": datetime.now()}
                self.update_by_field("session_id", session_id, data)
            else:
                # 创建新会话
                session_data = {"session_id": session_id, "created_at": datetime.now(), "updated_at": datetime.now()}
                self.insert(session_data)
        except Exception as e:
            logger.error(f"创建或更新会话失败: {str(e)}")
            raise e

    def get_session(self, session_id: str) -> dict | None:
        """根据会话ID获取会话

        Args:
            session_id: 会话ID

        Returns:
            dict | None: 会话信息字典，如果未找到则返回 None
        """
        try:
            result = self.select_record(conditions={"session_id": session_id})
            return result[0] if result else None
        except Exception as e:
            logger.error(f"获取会话失败: {str(e)}")
            raise e


class ChatMessageOperation(BaseDBOperation):
    """消息表(chat_messages)操作类"""

    def __init__(self):
        super().__init__(GlobalConfig.MYSQL_CONFIG["chat_messages_table"])

    def save_message(self, session_id: str, message_type: str, content: str, metadata: dict | None = None):
        """保存消息

        Args:
            session_id: 会话ID
            message_type: 消息类型('human', 'ai')
            content: 消息内容
            metadata: 消息元数据(可选)
        """
        try:
            message_data = {
                "session_id": session_id,
                "message_type": message_type,
                "content": content,
                "metadata": json.dumps(metadata) if metadata else None,
                "created_at": datetime.now(),
            }
            self.insert(message_data)

        except Exception as e:
            logger.error(f"保存消息失败: {str(e)}")
            raise e

    def get_message_by_session_id(self, session_id: str, limit: int = 100) -> list[dict]:
        """根据会话ID获取消息列表, 按时间正序排列, 默认获取100条

        Args:
            session_id: 会话ID
            limit: 获取消息数量(默认100)

        Returns:
            list[dict]: 消息列表
        """
        try:
            sql = f"SELECT * FROM {self.table_name} WHERE session_id = %s ORDER BY created_at ASC LIMIT %s"
            return self._execute_query(sql, (session_id, limit))
        except Exception as e:
            logger.error(f"[消息查询] 失败, session_id={session_id}, limit={limit}, error={str(e)}")
            raise e

    def delete_message_by_session_id(self, session_id: str):
        """根据会话ID删除消息

        Args:
            session_id: 会话ID
        """
        try:
            sql = f"DELETE FROM {self.table_name} WHERE session_id = %s"
            self._execute_update(sql, (session_id,))
        except Exception as e:
            logger.error(f"删除消息失败: {str(e)}")
            raise e


if __name__ == "__main__":
    # 使用上下文管理器
    with FileInfoOperation() as file_op:
        # 查询文件
        file_info = file_op.get_file_by_doc_id("215f2f8cfce518061941a70ff6c9ec0a3bb92ae6230e84f3d5777b7f9a1fac83")

        # 更新文件
        file_op.update_by_doc_id(
            "215f2f8cfce518061941a70ff6c9ec0a3bb92ae6230e84f3d5777b7f9a1fac83", {"source_document_type": ".p"}
        )

        # 删除文件
        file_op.delete_by_doc_id("f10e704816fda7c6cbf1d7f4aebc98a6ac1bfbe0602e0951af81277876adbcbc")
