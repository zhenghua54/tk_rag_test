"""FastAPI 应用入口"""
from dotenv import load_dotenv

load_dotenv(verbose=True)

import sys
from pathlib import Path

# 更新环境变量
root_path = Path(__file__).resolve()
sys.path.append(str(root_path))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
import uuid

from api.response import ResponseBuilder
from error_codes import ErrorCode
from config.global_config import GlobalConfig

from core.infra.lifecycle import lifespan


# request_id 中间件
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 生成唯一的 request_id
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # 在响应头中也添加 request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# 创建FastAPI应用实例
app = FastAPI(
    title=GlobalConfig.API_TITLE,
    description=GlobalConfig.API_DESCRIPTION,
    version=GlobalConfig.API_VERSION,
    # root_path=GlobalConfig.API_PREFIX,  # 指定全局前缀，暂时不使用，会影响静态文件访问
    lifespan=lifespan  # 添加生命周期管理器
)


# 全局异常处理
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理验证错误"""
    return JSONResponse(
        status_code=422,
        content=ResponseBuilder.error(
            error_code=ErrorCode.PARAM_ERROR.value,
            error_message="参数错误, 请检查请求参数是否完整且格式正确",
            request_id=getattr(request.state, "request_id", None),
            data=exc.errors()
        ).model_dump()
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    request_id = getattr(request.state, "request_id", None)

    return JSONResponse(
        status_code=500,
        content=ResponseBuilder.error(
            error_code=ErrorCode.INTERNAL_ERROR.value,
            error_message="系统内部错误",
            request_id=request_id,
        ).model_dump()
    )

# 映射静态目录: /static/raw -> datas/raw, /static/processed -> datas/processed
app.mount("/static/raw", StaticFiles(directory="/home/wumingxing/tk_rag/datas/raw"), name="static-raw")
app.mount("/static/processed", StaticFiles(directory="/home/wumingxing/tk_rag/datas/processed"),
          name="static-processed")

# 添加 request_id 中间件
app.add_middleware(RequestIDMiddleware)

# 注册路由 - 为API路由添加前缀
from api.chat_api import router as chat_router
from api.base import router as base_router
from api.doc_api import router as doc_router

app.include_router(base_router, prefix=GlobalConfig.API_PREFIX)
app.include_router(doc_router, prefix=GlobalConfig.API_PREFIX)
app.include_router(chat_router, prefix=GlobalConfig.API_PREFIX)

# for route in app.routes:
#     print(f"路由: {route.path}  方法: {route.methods}")
