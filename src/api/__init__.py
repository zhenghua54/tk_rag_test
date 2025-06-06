from fastapi import FastAPI
from .chat import router as chat_router
from .document_api import router as document_router

def create_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(
        title="RAG Demo API",
        description="RAG聊天演示系统API",
        version="1.0.0"
    )

    # 注册路由
    app.include_router(chat_router)
    app.include_router(document_router)

    return app



