#!/usr/bin/env python3
"""
简化的聊天API服务器，仅用于RAGAS评估测试
"""

import time
import os
from typing import Any

from fastapi import FastAPI, Request
from pydantic import BaseModel

# 确保环境变量已加载
if not os.getenv("MYSQL_HOST"):
    from dotenv import load_dotenv
    load_dotenv()

from core.rag.llm_generator import RAGGenerator
from utils.log_utils import logger

# 创建FastAPI应用
app = FastAPI(title="TK-RAG Chat API (Simplified)", version="1.0.0")

class ChatRequest(BaseModel):
    """聊天请求模型"""
    query: str
    session_id: str
    permission_ids: list[str] = []
    timeout: int = 30

class APIResponse(BaseModel):
    """API响应模型"""
    success: bool
    data: Any = None
    message: str = ""
    request_id: str = None

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy", "service": "tk-rag-chat"}

@app.post("/chat/rag_chat")
async def rag_chat(request: ChatRequest, fastapi_request: Request):
    """RAG对话接口（简化版）"""
    
    # 生成请求ID
    request_id = f"req_{int(time.time() * 1000)}"
    
    start_time = time.time()
    logger.info(
        f"[RAG对话] 开始, request_id={request_id}, query:{request.query[:100]}..., permission_ids:{request.permission_ids}, session_id:{request.session_id}"
    )

    try:
        # 初始化 RAG 生成器
        rag_generator = RAGGenerator()
        
        # 使用无权限版本的方法进行检索
        result = rag_generator.generate_response_without_permission(
            query=request.query,
            session_id=request.session_id,
            request_id=request_id,
        )

        duration = int((time.time() - start_time) * 1000)
        logger.info(
            f"[RAG对话] request_id={request_id}, 对话完成, session_id={request.session_id}, duration={duration}ms, answer_length={len(result.get('answer', ''))}"
        )

        return APIResponse(
            success=True,
            data=result,
            message="对话完成",
            request_id=request_id
        ).model_dump()

    except ValueError as e:
        logger.error(f"[RAG对话] request_id={request_id}, 参数错误: {str(e)}")
        return APIResponse(
            success=False,
            data=None,
            message=f"参数错误: {str(e)}",
            request_id=request_id
        ).model_dump()
        
    except Exception as e:
        logger.error(f"[RAG对话] request_id={request_id}, 内部错误: {str(e)}")
        return APIResponse(
            success=False,
            data=None,
            message=f"内部错误: {str(e)}",
            request_id=request_id
        ).model_dump()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)