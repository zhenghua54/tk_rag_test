"""API基础模块

包含API响应、错误码等基础组件
"""
from typing import Any, Optional

from pydantic import BaseModel
from src.api.error_codes import ErrorCode


# 自定义异常类
class APIException(Exception):
    def __init__(self, error_code: ErrorCode, message: str = None):
        self.code = error_code
        # 获取定义信息
        self.message = message or ErrorCode.get_message(error_code)


# 响应构造工具类
class ResponseBuilder(BaseModel):
    """统一的API响应处理类"""
    code: int
    message: str
    data: Optional[Any] = None
    request_id: Optional[str] = None

    @classmethod
    def success(cls, error_code: int = 0, data: Optional[Any] = None,
                request_id: str = None):
        """生成成功响应"""
        return cls(
            code=error_code,
            message=ErrorCode.get_message(error_code),
            request_id=request_id,
            data=data
        )

    @classmethod
    def error(cls, error_code: int, error_message: str = None,
              data: Optional[Any] = None, request_id: str = None):
        """生成错误响应"""
        return cls(
            code=error_code,
            message=error_message or ErrorCode.get_message(error_code),
            request_id=request_id,
            data=data  # 预留字段
        )
