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
    """从 MySQL 获取片段信息，包括关联的文档和权限信息
    
    Args:
        seg_ids: 片段 ID 列表
        doc_ids: 文档 ID 列表
        permission_ids: 权限 ID
        chunk_op: 复用的 ChunkOperation 实例
        
    Returns:
        List[Dict[str, Any]]: 片段信息列表，包含所有字段
    """
    try:
        # 确保至少有一个查询条件
        if not seg_ids and not doc_ids:
            logger.error("必须提供 seg_ids 或 doc_ids 参数")
            return []
            
        # 构建关联查询SQL
        sql = """
        SELECT 
            s.*,  -- 片段信息表的所有字段
            f.doc_http_url,  -- 文档信息表的字段
            f.created_at as doc_created_at,
            f.updated_at as doc_updated_at,
            p.permission_ids  -- 权限信息表的字段
        FROM segment_info s
        LEFT JOIN doc_info f ON s.doc_id = f.doc_id
        LEFT JOIN permission_info p ON s.doc_id = p.doc_id
        WHERE 1=1
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
                
        # 执行查询
        segment_info = []
        if chunk_op is not None:
            segment_info = chunk_op._execute_query(sql, tuple(params))
        else:
            with ChunkOperation() as temp_op:
                segment_info = temp_op._execute_query(sql, tuple(params))
        
        # 处理查询结果
        if not segment_info:
            return []
        
        # 转换结果格式
        results = []
        for record in segment_info:
            # 如果指定了权限ID，则进行过滤
            if permission_ids and record.get("permission_ids") != permission_ids:
                logger.debug(f"权限过滤: 跳过文档 {record.get('seg_id')}, 权限不匹配 (需要: {permission_ids}, 实际: {record.get('permission_ids')})")
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
