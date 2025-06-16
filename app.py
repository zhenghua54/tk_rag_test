"""FastAPI 应用入口"""
from dotenv import load_dotenv

load_dotenv(verbose=True)

import sys, os
from pathlib import Path
from openai import OpenAI

# 更新环境变量
root_path = Path(__file__).resolve()
sys.path.append(str(root_path))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import RequestValidationError

from src.api import chat_api
from src.api.response import ResponseBuilder, ErrorCode
from config.settings import Config
from src.api.base import router as base_router
from src.api import document_api
from src.middleware.base_middleware import RequestMiddleware
from src.core.lifecycle import lifespan



# 创建FastAPI应用实例
app = FastAPI(
    title=Config.API_TITLE,
    description=Config.API_DESCRIPTION,
    version=Config.API_VERSION,
    root_path=Config.API_PREFIX,  # 指定全局前缀
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


# 注册中间件
app.add_middleware(RequestMiddleware)

# 注册路由
app.include_router(base_router)
app.include_router(document_api.router)
app.include_router(chat_api.router)

# for route in app.routes:
#     print(f"路由: {route.path}  方法: {route.methods}")
