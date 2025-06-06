"""FastAPI 应用入口"""
from fastapi import FastAPI
from config.settings import Config
from src.api.base import router as base_router
from src.api import document_api
from src.middleware.base_middleware import RequestMiddleware

# 创建FastAPI应用实例
app = FastAPI(
    title=Config.API_TITLE,
    description=Config.API_DESCRIPTION,
    version=Config.API_VERSION,
    health_url=f"{Config.API_PREFIX}/health",
    docs_url=f"{Config.API_PREFIX}/docs",
    redoc_url=f"{Config.API_PREFIX}/redoc",
    openapi_url=f"{Config.API_PREFIX}/openapi.json"
)

# 注册中间件
app.add_middleware(RequestMiddleware)

# 注册路由
app.include_router(base_router)
app.include_router(document_api.router)


# 健康检查接口
@app.get(f"{Config.API_PREFIX}/health")
async def health_check():
    """健康检查接口"""
    return {
        "code": 0,
        "message": "success",
        "data": {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": "2025-06-04T10:00:00Z"
        }
    }
