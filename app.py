"""主应用入口

FastAPI应用实例和路由配置
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api import chat, document
from src.api.base import request_handler
from config.settings import Config

# 创建FastAPI应用实例
app = FastAPI(
    title="RAG Demo API",
    description="RAG系统API文档",
    version="1.0.0",
    docs_url=f"{Config.API_PREFIX}/docs",
    redoc_url=f"{Config.API_PREFIX}/redoc",
    openapi_url=f"{Config.API_PREFIX}/openapi.json"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加请求处理中间件
app.middleware("http")(request_handler)

# 注册路由
app.include_router(chat.router)
app.include_router(document.router)

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