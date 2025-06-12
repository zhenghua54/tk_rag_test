"""原文检索模块"""
from typing import Optional, Dict, Any, List
from src.utils.common.logger import logger
from src.database.mysql.operations import ChunkOperation


def get_seg_content(seg_id: str, chunk_op: Optional[ChunkOperation] = None) -> str:
    """从 MySQL 获取 segment 原文内容
    
    Args:
        seg_id: segment ID
        chunk_op: 复用的 ChunkOperation 实例
        
    Returns:
        str: segment 原文内容
    """
    try:
        if chunk_op is not None:
            chunk_info = chunk_op.select_record(
                conditions={"seg_id": seg_id}
            )
            return chunk_info[0] if chunk_info else ""
        else:
            with ChunkOperation() as temp_op:
                chunk_info = temp_op.select_record(
                    conditions={"seg_id": seg_id}
                )
                return chunk_info[0] if chunk_info else ""
    except Exception as error:
        logger.error(f"获取 segment 原文失败: {str(error)}")
        return ""


def get_segment_contents(seg_ids: List[str] = None, doc_ids: List[str] = None, permission_ids: str = None,
                         chunk_op: Optional[ChunkOperation] = None) -> List[Dict[str, Any]]:
    """从 MySQL 获取片段信息
    
    Args:
        seg_ids: 片段 ID 列表
        doc_ids: 文档 ID 列表
        permission_ids: 权限 ID
        chunk_op: 复用的 ChunkOperation 实例
        
    Returns:
        List[Dict[str, Any]]: 片段信息列表，包含所有字段
    """
    try:
        conditions = {}
        if seg_ids:
            conditions["seg_id"] = seg_ids
        if doc_ids:
            conditions["doc_id"] = doc_ids
        if permission_ids:
            conditions["permission_ids"] = permission_ids
        if not conditions:
            logger.error("必须提供 seg_ids 或 doc_ids 参数")
            return []
        
        # 构建关联查询SQL
        sql = """
        SELECT 
            s.seg_id,
            s.seg_content,
            s.seg_type,
            s.seg_image_path,
            s.seg_caption,
            s.seg_footnote,
            s.seg_page_idx,
            s.doc_id,
            p.permission_ids,
            d.doc_http_url,
            d.created_at,
            d.updated_at
        FROM segment_info s
        LEFT JOIN permission_info p ON s.doc_id = p.doc_id
        LEFT JOIN doc_info d ON s.doc_id = d.doc_id
        WHERE 1=1
        """
        
        # 添加条件
        if seg_ids:
            sql += " AND s.seg_id IN %S"
        if doc_ids:
            sql += " AND s.doc_id IN %S"
        if permission_ids:
            sql += " AND p.permission_ids IN %S"

        segment_info = None
        if chunk_op is not None:
            segment_info = chunk_op.execute_query(
                sql=sql,
                params=(
                    tuple(seg_ids) if seg_ids else None,
                    tuple(doc_ids) if doc_ids else None,
                    tuple(permission_ids) if permission_ids else None,
                )
            )
        else:
            with ChunkOperation() as temp_op:
                segment_info = temp_op.execute_query(
                    sql=sql,
                    params=(
                        tuple(seg_ids) if seg_ids else None,
                        tuple(doc_ids) if doc_ids else None,
                        tuple(permission_ids) if permission_ids else None,
                    )
                )
        
        # 处理查询结果
        if not segment_info:
            return []

        # 转换结果格式
        results = []
        for record in segment_info:
            result={
                # 片段信息
                "seg_id": record.get("s.seg_id"),
                "seg_content": record.get("s.seg_content"),
                "seg_type": record.get("s.seg_type"),
                "seg_image_path": record.get("s.seg_image_path"),
                "seg_caption": record.get("s.seg_caption"),
                "seg_footnote": record.get("s.seg_footnote"),
                "seg_page_idx": record.get("s.seg_page_idx"),
                
                # 文档信息
                "doc_id": record.get("s.doc_id"),
                "doc_http_url": record.get("d.doc_http_url"),
                "doc_created_at": record.get("d.created_at"),
                "doc_updated_at": record.get("d.updated_at"),
                
                # 权限信息
                "permission_ids": record.get("p.permission_ids")
            }
            results.append(result)
        
        return results

    except Exception as error:
        logger.error(f"获取片段信息失败: {str(error)}")
        return []
