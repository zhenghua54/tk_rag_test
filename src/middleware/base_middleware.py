"""请求处理中间件"""
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from api.response import ResponseBuilder
from api.error_codes import ErrorCode
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
        # 先从请求头中获取
        request_id = request.headers.get('X-Request-ID')
        if not request_id:
            # 如果请求头中没有，则生成一个
            request_id = str(uuid.uuid4())
        
        request.state.request_id = request_id

        # 调试输出请求ID和请求内容
        # print("headers:", dict(request.headers))  # 请求头
        # print("query_params:", dict(request.query_params))  # 查询参数
        # print("path_params:", request.path_params)  # 路径参数
        # # print("form_data:", await request.form())  # 表单数据,需要安装 `python-multipart`
        # print("json_data:", await request.json())  # JSON数据
        # print("method:", request.method)  # 请求方法
        # print("path:", request.url.path)  # 请求路径
        # print("url:", str(request.url))  # 请求URL

        # 2. 处理请求
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            error_code = ErrorCode.INTERNAL_ERROR
            error_msg = f"{ErrorCode.get_message(error_code)} {str(e)}"
            # 记录错误日志
            logger.error(f"[请求错误] error_code={error_code}, error_msg={str(e)}, request_id={request_id}")

            # 返回统一格式的错误响应
            return JSONResponse(
                content=ResponseBuilder.error(
                    error_code=ErrorCode.INTERNAL_ERROR.value,
                    error_message=error_msg,
                    data={
                        "request_id": request_id,
                        "error": str(e),
                        "suggestion": "请稍后重试或联系管理员"
                    }).model_dump()
            )
