"""参数校验工具类"""
import json
import os.path
from typing import Any, List, Union


class ArgsValidator:
    @staticmethod
    def validity_not_empty(value: Any, param_name: str) -> None:
        """验证参数非空
        
        Args:
            value: 要验证的值
            param_name: 参数名称
            
        Raises:
            ValueError: 当参数为空时抛出
        """
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError(f"{param_name} 不能为空")

    @staticmethod
    def validity_type(value: Any, expected_type: Union[type, tuple], param_name: str) -> None:
        """验证参数类型
        
        Args:
            value: 要验证的值
            expected_type: 期望的类型
            param_name: 参数名称
            
        Raises:
            TypeError: 当参数类型不匹配时抛出
        """
        if not isinstance(value, expected_type):
            raise TypeError(f"{param_name} 必须是 {expected_type} 类型")

    @staticmethod
    def validity_list_not_empty(value: List, param_name: str) -> None:
        """验证列表非空
        
        Args:
            value: 要验证的列表
            param_name: 参数名称
            
        Raises:
            ValueError: 当列表为空时抛出
        """
        if not isinstance(value, list):
            raise TypeError(f"{param_name} 必须是列表类型")
        if len(value) == 0:
            raise ValueError(f"{param_name} 列表不能为空")

    @staticmethod
    def validity_doc_id(doc_id: str) -> None:
        """验证文档ID格式
        
        Args:
            doc_id: 文档ID
            
        Raises:
            ValueError: 当文档ID格式不正确时抛出
        """
        ArgsValidator.validity_not_empty(doc_id, "doc_id")
        ArgsValidator.validity_type(doc_id, str, "doc_id")
        if len(doc_id) != 64:
            raise ValueError("doc_id 必须是64位哈希值字符串")

    @staticmethod
    def validity_segment_id(segment_id: str) -> None:
        """验证分段ID格式
        
        Args:
            segment_id: 分段ID
            
        Raises:
            ValueError: 当分段ID格式不正确时抛出
        """
        ArgsValidator.validity_not_empty(segment_id, "segment_id")
        ArgsValidator.validity_type(segment_id, str, "segment_id")
        if len(segment_id) != 64:
            raise ValueError("segment_id 必须是64位哈希值字符串")

    @staticmethod
    def validity_department_id(department_id: str) -> None:
        """验证部门ID格式
        
        Args:
            department_id: 部门ID
            
        Raises:
            ValueError: 当部门ID格式不正确时抛出
        """
        ArgsValidator.validity_not_empty(department_id, "department_id")
        ArgsValidator.validity_type(department_id, str, "department_id")

    
