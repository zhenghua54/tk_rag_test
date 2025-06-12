from typing import Dict, List, Optional, Tuple
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts import PromptTemplate
from langchain.schema import BaseRetriever, Document
from langchain_openai import ChatOpenAI

from src.api.response import ResponseBuilder, ErrorCode
from src.utils.common.logger import logger
from src.core.rag.llm import DASHSCOPE_API_KEY


class RAGGenerator:
    """RAG 生成器，处理用户查询并生成回答"""

    # 类级别的会话记忆存储
    _memory_store = {}

    def __init__(self, retriever: BaseRetriever):
        """初始化 RAG 生成器
        
        Args:
            retriever: 混合检索器实例
        """
        self.retriever = retriever
        self.llm, self.chat_prompt, self.system_prompt = self._create_llm_chain()
        self.memory = None
        self.chain = None

    def _create_llm_chain(self) -> Tuple[ChatOpenAI, PromptTemplate, str]:
        """初始化 LLM 和提示模板"""
        logger.info("初始化 LLM 模型...")

        # 初始化 LLM
        llm = ChatOpenAI(
            temperature=0,
            model='qwen-turbo',
            openai_api_key=DASHSCOPE_API_KEY,
            openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        # 初始化提示模板
        system_prompt = """你的任务是基于企业知识库中的信息，准确并清晰地回答用户提出的问题。"""
        chat_prompt = PromptTemplate(
            input_variables=["context", "chat_history", "question"],
            template="""你是一个专业且严谨的企业知识问答助手。

请遵循以下规则：

1. 只依据提供的知识内容 {context} 作答，不要编造信息。
2. 如果 {context} 中没有足够信息，请直接回答：「抱歉，知识库中没有找到相关信息」。
3. 结合上下文历史对话 {chat_history}，理解用户当前问题 {question}，保持回答简洁明了。
4. 回答中如涉及多个要点，可使用项目符号 (•) 或编号分点表达。

---  
【知识库信息】  
{context}

---  
【历史对话】  
{chat_history}

---  
【用户问题】  
{question}

请给出你的专业回答："""
        )

        return llm, chat_prompt, system_prompt

    def _get_memory(self, session_id: str) -> ConversationBufferWindowMemory:
        """根据会话ID获取或创建记忆实例
        
        Args:
            session_id: 会话ID
            
        Returns:
            ConversationBufferWindowMemory: 会话记忆实例
        """
        # 如果该会话ID已有记忆实例，直接返回
        if session_id in self._memory_store:
            return self._memory_store[session_id]
        
        # 否则创建新的记忆实例
        memory = ConversationBufferWindowMemory(
            memory_key="chat_history",
            return_messages=True,
            input_key="question",
            output_key="answer",
            k=5,
            human_prefix="用户",
            ai_prefix="助手",
        )
        
        # 存储到类级别的记忆存储中
        self._memory_store[session_id] = memory
        
        return memory

    def _create_chain(self, session_id: str) -> ConversationalRetrievalChain:
        """创建对话链
        
        Args:
            session_id: 会话ID
            
        Returns:
            ConversationalRetrievalChain: 对话链实例
        """
        # 获取会话对应的记忆实例
        self.memory = self._get_memory(session_id)
        
        # 创建对话链
        chain = ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=self.retriever,
            memory=self.memory,
            combine_docs_chain_kwargs={
                "prompt": self.chat_prompt,
            },
            return_source_documents=True,
            verbose=True,
        )
        
        return chain

    def generate_response(self,
                          query: str,
                          session_id: str,
                          permission_ids: Optional[str] = None,
                          request_id: Optional[str] = None) -> Dict:
        """生成回答
        
        Args:
            query: 用户问题
            session_id: 会话ID
            permission_ids: 权限ID
            request_id: 请求ID
            
        Returns:
            Dict: 包含回答、元数据等的字典
        """
        try:
            # 检查输入
            if not query or not query.strip():
                return ResponseBuilder.error(
                    error_code=ErrorCode.PARAM_ERROR.value,
                    message="问题不能为空",
                    request_id=request_id
                )

            # 创建/获取该会话的对话链
            self.chain = self._create_chain(session_id)

            # 使用权限ID进行检索
            docs = self.retriever._get_relevant_documents(query, permission_ids=permission_ids)
            
            # 如果没有找到相关文档，直接返回提示信息
            if not docs:
                return ResponseBuilder.success(
                    data={
                        "answer": "抱歉，知识库中没有找到相关信息",
                        "session_id": session_id,
                        "metadata": [],
                        "chat_history": [
                            {
                                "role": "human",
                                "content": query
                            },
                            {
                                "role": "ai",
                                "content": "抱歉，知识库中没有找到相关信息"
                            }
                        ]
                    },
                    request_id=request_id
                )

            # 手动构建上下文
            context = "\n\n".join([doc.page_content for doc in docs])
            
            # 获取历史对话
            chat_history = self.memory.load_memory_variables({}).get("chat_history", [])
            
            # 使用LLM直接生成回答
            response_text = self.llm.invoke(
                self.chat_prompt.format(
                    context=context,
                    chat_history=chat_history,
                    question=query
                )
            ).content
            
            # 更新对话记忆
            self.memory.save_context({"question": query}, {"answer": response_text})
            
            # 提取源文档元数据
            metadata = []
            for doc in docs:
                metadata.append({
                    "seg_id": doc.metadata.get("seg_id"),
                    "doc_id": doc.metadata.get("doc_id"),
                    "doc_http_url": doc.metadata.get("doc_http_url"),
                    "doc_images_path": doc.metadata.get("doc_images_path", ""),
                    "doc_created_at": doc.metadata.get("doc_created_at"),
                    "doc_updated_at": doc.metadata.get("doc_updated_at"),
                    "seg_page_idx": doc.metadata.get("seg_page_idx", 0),
                    "score": doc.metadata.get("score", 0.0)
                })

            # 构建返回结果
            return ResponseBuilder.success(
                data={
                    "answer": response_text.strip(),
                    "session_id": session_id,
                    "metadata": metadata,
                    "chat_history": [
                        {
                            "role": msg.type,
                            "content": msg.content
                        }
                        for msg in self.memory.chat_memory.messages
                    ]
                },
                request_id=request_id
            )

        except Exception as e:
            logger.error(f"生成回答失败: {str(e)}")
            return ResponseBuilder.error(
                error_code=ErrorCode.CHAT_EXCEPTION.value,
                message=f"生成回答失败: {str(e)}",
                request_id=request_id
            )
