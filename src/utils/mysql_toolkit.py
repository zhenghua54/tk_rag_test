"""MySQL 数据库工具"""

import datetime
from typing import Dict, Any, List

from src.utils.validator.args_validator import ArgsValidator


def normalize_segment_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """补充segment_info表记录的缺失字段，确保字段完整统一
    
    Args:
        record (Dict[str, Any]): 原始segment记录数据
        
    Returns:
        Dict[str, Any]: 补充完整的segment记录数据
    """
    ArgsValidator.validate_type(record, dict, "record")
    
    # 复制原始记录
    normalized_record = record.copy()
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # segment_info表默认值定义
    default_values = {
        "seg_parent_id": None,
        "seg_image_path": "",
        "seg_caption": "",
        "seg_footnote": "",
        "seg_len": "0",
        "seg_type": "text",
        "seg_page_idx": "0",
        "is_soft_deleted": False,
        "created_at": current_time,
        "updated_at": current_time
    }
    
    # 将默认值合并到记录中，但不覆盖已有值
    for key, value in default_values.items():
        if key not in normalized_record or normalized_record[key] is None:
            normalized_record[key] = value
            
    return normalized_record


def normalize_segment_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """批量补充segment_info表记录的缺失字段，确保字段完整统一
    
    Args:
        records (List[Dict[str, Any]]): 原始segment记录数据列表
        
    Returns:
        List[Dict[str, Any]]: 补充完整的segment记录数据列表
    """
    ArgsValidator.validate_type(records, list, "records")
    
    return [normalize_segment_record(record) for record in records]