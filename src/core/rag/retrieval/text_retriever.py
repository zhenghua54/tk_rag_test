"""原文检索模块"""
from typing import Optional
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
            return chunk_info[0]["seg_content"] if chunk_info else ""
        else:
            with ChunkOperation() as temp_op:
                chunk_info = temp_op.select_record(
                    conditions={"seg_id": seg_id}
                )
                return chunk_info[0]["seg_content"] if chunk_info else ""
    except Exception as error:
        logger.error(f"获取 segment 原文失败: {str(error)}")
        return "" 