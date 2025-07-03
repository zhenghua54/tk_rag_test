"""聊天API实现
"""
import time
from fastapi import APIRouter, Request

from api.request.chat_request import ChatRequest
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
    
    Args:operation=
        request: 聊天请求参数
        fastapi_request: FastAPI请求对象，用于获取请求ID等信息
        
    Returns:
        Dict: 包含模型回答和来源文档信息的响应
        
    Raises:
        HTTPException: 当发生错误时抛出相应的错误码和信息
    """
    # 获取请求ID
    request_id = fastapi_request.state.request_id if hasattr(fastapi_request.state, 'request_id') else None

    start_time = time.time()
    logger.info(
        f"[RAG聊天] 开始, request_id={request_id}, session_id={request.session_id}, query_length={len(request.query)}, permission_ids={request.permission_ids}")

    try:
        # 获取服务实例
        # chat_service = ChatService.get_instance()

        # 初始化 RAG 生成器
        rag_generator = RAGGenerator(retriever=hybrid_retriever)
        result = rag_generator.generate_response(
            query=request.query,
            session_id=request.session_id,
            permission_ids=request.permission_ids,
            request_id=request_id
        )

        duration = int((time.time() - start_time) * 1000)
        logger.info(
            f"[RAG聊天] 成功, request_id={request_id}, session_id={request.session_id}, duration={duration}ms, answer_length={len(result.get('answer', ''))}")

        return ResponseBuilder.success(data=result, request_id=request_id)

    except ValueError as e:
        logger.error(
            f"[RAG聊天失败] request_id={request_id}, session_id={request.session_id}, error_code=PARAM_ERROR, error_msg={str(e)}")
        return APIException(error_code=ErrorCode.PARAM_ERROR, message=str(e))
    except TimeoutError:
        logger.error(
            f"[RAG聊天失败] request_id={request_id}, session_id={request.session_id}, error_code=MODEL_TIMEOUT, error_msg=模型响应超时, timeout={request.timeout}")
        return ResponseBuilder.error(error_code=ErrorCode.MODEL_TIMEOUT.value, data={
            "timeout": request.timeout,
            "session_id": request.session_id,
        })
    except Exception as e:
        # 记录未预期的错误
        logger.error(
            f"[RAG聊天失败] request_id={request_id}, session_id={request.session_id}, error_code=CHAT_EXCEPTION, error_msg={str(e)}")
        log_exception("聊天异常错误", exc=e)
        return ResponseBuilder.error(error_code=ErrorCode.CHAT_EXCEPTION.value, error_message=str(e))
