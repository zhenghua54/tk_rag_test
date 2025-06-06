"""聊天API实现
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel, Field, validator
from src.api.response import ResponseBuilder, ErrorCode
from src.server.chat import ChatService

router = APIRouter(prefix="/api/v1")

class ChatRequest(BaseModel):
    """聊天请求模型
    
    Attributes:
        query: 用户问题
        department_id: 部门ID
        session_id: 会话ID(可选)
        timeout: 超时时间(可选,默认30秒)
    """
    query: str = Field(..., max_length=2000, description="用户输入问题")
    department_id: str = Field(..., description="部门UUID")
    session_id: Optional[str] = Field(None, description="会话ID(保持上下文)")
    timeout: Optional[int] = Field(30, ge=1, le=120, description="超时时间(秒)")
    
    @validator("query")
    def validate_query(cls, v):
        if len(v.strip()) == 0:
            raise ValueError("问题不能为空")
        return v.strip()

@router.post("/rag_chat")
async def rag_chat(request: ChatRequest):
    """RAG聊天接口
    
    根据用户问题和指定部门ID，过滤数据并返回模型回答及其对应来源文档信息
    
    Args:
        request: 聊天请求参数
        
    Returns:
        Dict: 包含模型回答和来源文档信息的响应
        
    Raises:
        HTTPException: 当发生错误时抛出相应的错误码和信息
    """
    try:
        # 获取服务实例
        chat_service = ChatService.get_instance()
        
        # 调用聊天服务
        result = await chat_service.chat(
            query=request.query,
            department_id=request.department_id,
            session_id=request.session_id,
            timeout=request.timeout
        )
        
        return ResponseBuilder.success(data=result)
        
    except ValueError as e:
        return ResponseBuilder.error(
            code=ErrorCode.PARAM_ERROR,
            message=str(e)
        )
    except TimeoutError:
        return ResponseBuilder.error(
            code=ErrorCode.MODEL_TIMEOUT,
            message="模型响应超时",
            data={
                "timeout": request.timeout,
                "session_id": request.session_id,
                "suggestion": "请简化问题或分多次询问"
            }
        )
    except Exception as e:
        # 记录未预期的错误
        import logging
        logging.exception("Chat error")
        return ResponseBuilder.error(
            code=ErrorCode.KB_MATCH_FAILED,
            message="知识库匹配失败",
            data={"error": str(e)}
        ) 