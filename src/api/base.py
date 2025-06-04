"""API基础模块

包含API响应、错误码等基础组件
"""
from typing import Dict, Any, Optional
from fastapi import HTTPException, Request
from pydantic import BaseModel
from enum import Enum
import uuid

class APIResponse(BaseModel):
    """API响应基类"""
    success: bool = True
    message: str = "success"
    data: Optional[Dict[str, Any]] = None

class APIException(HTTPException):
    """API异常基类"""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(
            status_code=status_code,
            detail={
                "success": False,
                "message": message,
                "data": None
            }
        )

class ErrorCode(Enum):
    """错误码枚举类
    
    Attributes:
        SUCCESS (0): 成功
        PARAM_ERROR (1001): 参数错误
        PARAM_EXCEED_LIMIT (1002): 参数超出限制
        DUPLICATE_OPERATION (1003): 重复操作
        
        QUESTION_TOO_LONG (2001): 问题长度超出限制
        INVALID_SESSION (2002): 会话ID无效
        MODEL_TIMEOUT (2003): 模型响应超时
        KB_MATCH_FAILED (2004): 知识库匹配失败
        CONTEXT_TOO_LONG (2005): 上下文长度超限
        
        FILE_NOT_FOUND (3001): 文件不存在
        UNSUPPORTED_FORMAT (3002): 不支持的文件格式
        FILE_TOO_LARGE (3003): 文件过大
        INVALID_FILENAME (3004): 文件名无效
        FILE_PARSE_ERROR (3005): 文件解析失败
        FILE_EXISTS (3006): 文件已存在
        STORAGE_FULL (3007): 存储空间不足
    """
    SUCCESS = 0
    
    # 通用错误 1000-1999
    PARAM_ERROR = 1001
    PARAM_EXCEED_LIMIT = 1002  
    DUPLICATE_OPERATION = 1003
    
    # 聊天相关 2000-2999
    QUESTION_TOO_LONG = 2001
    INVALID_SESSION = 2002
    MODEL_TIMEOUT = 2003
    KB_MATCH_FAILED = 2004
    CONTEXT_TOO_LONG = 2005
    
    # 文件相关 3000-3999
    FILE_NOT_FOUND = 3001
    UNSUPPORTED_FORMAT = 3002
    FILE_TOO_LARGE = 3003
    INVALID_FILENAME = 3004
    FILE_PARSE_ERROR = 3005
    FILE_EXISTS = 3006
    STORAGE_FULL = 3007

class APIResponse:
    """统一的API响应处理类
    
    用于生成统一格式的API响应
    
    Attributes:
        code (int): 响应码
        message (str): 响应消息
        data (Optional[Dict]): 响应数据
    """
    
    @staticmethod
    def success(data: Optional[Dict] = None, message: str = "success") -> Dict[str, Any]:
        """生成成功响应
        
        Args:
            data: 响应数据
            message: 响应消息
            
        Returns:
            Dict[str, Any]: 统一格式的成功响应
        """
        return {
            "code": ErrorCode.SUCCESS.value,
            "message": message,
            "data": data or {}
        }
    
    @staticmethod
    def error(code: ErrorCode, message: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """生成错误响应
        
        Args:
            code: 错误码
            message: 错误消息
            data: 错误详细信息
            
        Returns:
            Dict[str, Any]: 统一格式的错误响应
        """
        return {
            "code": code.value,
            "message": message,
            "data": data or {}
        }

def generate_request_id() -> str:
    """生成请求ID
    
    Returns:
        str: UUID格式的请求ID
    """
    return str(uuid.uuid4())

async def request_handler(request: Request, call_next):
    """请求处理中间件
    
    为每个请求添加请求ID，统一处理异常
    
    Args:
        request: 请求对象
        call_next: 下一个处理器
        
    Returns:
        Response: 响应对象
    """
    request_id = generate_request_id()
    # 将request_id注入到请求对象中
    request.state.request_id = request_id
    
    try:
        response = await call_next(request)
        return response
    except APIException as e:
        return e.detail
    except Exception as e:
        # 处理未预期的异常
        return {
            "code": ErrorCode.DUPLICATE_OPERATION.value,
            "message": "系统内部错误",
            "data": {
                "request_id": request_id,
                "error": str(e)
            }
        } 