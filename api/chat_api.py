"""聊天API实现
"""
from fastapi import APIRouter, Request

from api.request.chat_ragchat_request import ChatRequest
from api.response import APIException
from api.response import ResponseBuilder
from error_codes import ErrorCode
from utils.log_utils import log_exception, logger
from core.rag.llm_generator import RAGGenerator
from core.rag.hybrid_retriever import hybrid_retriever

router = APIRouter(
    prefix="/chat",
    tags=["聊天相关"],
)


@router.post("/rag_chat")
async def rag_chat(request: ChatRequest, fastapi_request=Request):
    """RAG聊天接口
    
    根据用户问题和指定部门ID，过滤数据并返回模型回答及其对应来源文档信息
    
    Args:
        request: 聊天请求参数
        fastapi_request: FastAPI请求对象，用于获取请求ID等信息
        
    Returns:
        Dict: 包含模型回答和来源文档信息的响应
        
    Raises:
        HTTPException: 当发生错误时抛出相应的错误码和信息
    """
    try:
        # 获取服务实例
        # chat_service = ChatService.get_instance()
        # 获取请求ID
        request_id = fastapi_request.state.request_id if hasattr(fastapi_request.state, 'request_id') else None

        logger.info(
            f"RAG 对话, request_id={request_id}, fastapi_request={fastapi_request}, session_id={request.session_id}, permission={request.permission_ids}")

        # 调用聊天服务
        # 初始化 RAG 生成器
        rag_generator = RAGGenerator(retriever=hybrid_retriever)
        result = rag_generator.generate_response(
            query=request.query,
            session_id=request.session_id,
            permission_ids=request.permission_ids,
            request_id=request_id
        )
        logger.info(f"RAG 对话完成, session_id={request.session_id}, permission={request.permission_ids}")

        return ResponseBuilder.success(data=result, request_id=request_id)

    except ValueError as e:
        return APIException(error_code=ErrorCode.PARAM_ERROR, message=str(e))
    except TimeoutError:
        return ResponseBuilder.error(error_code=ErrorCode.MODEL_TIMEOUT.value, data={
            "timeout": request.timeout,
            "session_id": request.session_id,
        })
    except Exception as e:
        # 记录未预期的错误
        log_exception("聊天异常错误", exc=e)
        return ResponseBuilder.error(error_code=ErrorCode.CHAT_EXCEPTION.value, error_message=str(e))
