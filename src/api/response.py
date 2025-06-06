"""API基础模块

包含API响应、错误码等基础组件
"""
from enum import Enum
from typing import Any, Optional, Dict
from pydantic import BaseModel
from src.utils.common.error_code import ErrorCode, ErrorInfo


# 自定义异常类
class APIException(Exception):
    def __init__(self, code: ErrorCode, message: str = None):
        self.code = code
        self.message = message or code.describe()


# 响应构造工具类
class ResponseBuilder(BaseModel):
    """统一的API响应处理类"""
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None

    @classmethod
    def success(cls, data: Optional[Dict[str, Any]] = None):
        """生成成功响应"""
        return cls(
            code=ErrorCode.SUCCESS.value,
            message="操作成功",
            data=data
        )

    @classmethod
    def error(cls, code: int, message: str = None, data: Optional[Dict[str, Any]] = None):
        """生成错误响应"""
        error_info = ErrorInfo()
        description, category, suggestion = error_info.get_error_info(code)
        
        error_data = {
            "category": category,
            "suggestion": suggestion
        }
        if data:
            error_data.update(data)
            
        return cls(
            code=code,
            message=str(message or description),  # 确保message是字符串类型
            data=error_data
        )
