"""聊天API实现
"""
from fastapi import APIRouter, Request

from src.api.request.chat_ragchat_request import ChatRequest
from src.api.response import ResponseBuilder, ErrorCode, APIException
from src.services.chat_server import ChatService
from src.utils.common.logger import log_exception, log_operation_start, log_business_info, log_operation_success
from src.core.rag.llm_generator import RAGGenerator
from src.core.rag.hybrid_retriever import HybridRetriever, init_retrievers

router = APIRouter(
    prefix="/chat",
    tags=["聊天相关"],
)

# 全局初始化混合检索器，避免每次请求都重新初始化
vector_retriever, bm25_retriever = init_retrievers()
hybrid_retriever = HybridRetriever(vector_retriever, bm25_retriever)


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
        chat_service = ChatService.get_instance()
        # 获取请求ID
        request_id = fastapi_request.state.request_id if hasattr(fastapi_request.state, 'request_id') else None

        log_business_info("rag 对话",
                          endpoint="/chat/rag_chat",
                          request_id=request_id,
                          permission_ids=request.permission_ids,
                          session_id=request.session_id,
                          )

        chat_start_time = log_operation_start("对话",
                                              request_id=request_id,
                                              permission_ids=request.permission_ids,
                                              session_id=request.session_id,
                                              )
        # 调用聊天服务
        # 初始化 RAG 生成器
        rag_generator = RAGGenerator(retriever=hybrid_retriever)
        result = rag_generator.generate_response(
            query=request.query,
            session_id=request.session_id,
            permission_ids=request.permission_ids,
            request_id=request_id
        )
        log_operation_success("rag 对话", start_time=chat_start_time, session_id=request.session_id)
        
        return result

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
