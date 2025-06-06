"""请求处理中间件"""
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from src.api.response import ResponseBuilder, ErrorCode
from src.utils.common.logger import logger

class RequestMiddleware(BaseHTTPMiddleware):
    """请求处理中间件
    
    实现以下功能：
    1. 请求ID注入
    2. 请求处理
    """
    
    async def dispatch(self, request: Request, call_next):
        """中间件分发处理
        
        Args:
            request: FastAPI请求对象
            call_next: 下一个中间件或路由处理函数
            
        Returns:
            Response: FastAPI响应对象
        """
        # 1. 注入请求ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # 2. 处理请求
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            # 记录错误日志
            logger.error(f"Request processing error: {str(e)}")
            
            # 返回统一格式的错误响应
            return JSONResponse(
                content=ResponseBuilder.error(
                    code=ErrorCode.INTERNAL_ERROR,
                    message="服务器内部错误",
                    data={
                        "request_id": request_id,
                        "error": str(e),
                        "suggestion": "请稍后重试或联系管理员"
                    }
                )
            )
        