from typing import Dict, Optional, List

from langchain_core.documents import Document
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import BaseRetriever

from utils.log_utils import logger
from utils.llm_utils import llm_manager, render_prompt


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
        # self.llm, self.chat_prompt, self.system_prompt = self._create_llm_chain()
        self.memory = None
        # self.chain = None

    #     def _create_llm_chain(self) -> Tuple[ChatOpenAI, PromptTemplate, str]:
    #         """初始化 LLM 和提示模板"""
    #         logger.info("初始化 LLM 模型...")
    #
    #         # 获取LLM管理器实例
    #         # llm_manager = LLMManager.get_instance()
    #
    #         # 初始化 LLM
    #         llm = ChatOpenAI(
    #             temperature=0,
    #             model=GlobalConfig.LLM_NAME,
    #             openai_api_key=llm_manager.api_key,
    #             openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
    #         )
    #
    #         # 初始化提示模板
    #         system_prompt = """你是企业知识助手，请结合上下文详细展开，不要省略任何关键要点。"""
    #         chat_prompt = PromptTemplate(
    #             input_variables=["context", "chat_history", "question"],
    #             template="""你是一个专业且严谨的企业知识问答助手，你的名字叫“天宽认知助手”。
    #
    # 你的任务是：基于以下提供的“知识库信息”和“历史对话”，准确、详尽地回答用户的问题。
    #
    # 请遵循以下规则：
    #
    # 1. 不得编造信息，仅基于提供的知识内容作答；
    # 2. 回答应遵循固定结构（见下），并尽量详细；
    # 3. 如信息不足，请直接说明「抱歉，知识库中没有找到相关信息」。
    #
    # ---
    #
    # 【知识库信息】
    # {context}
    #
    # 【历史对话】
    # {chat_history}
    #
    # 【用户问题】
    # {question}
    #
    # ---
    #
    # 请严格使用以下结构用 **Markdown** 格式回答：
    #
    # ### 1. 问题背景
    # 简要说明用户提问涉及的内容和背景。
    #
    # ### 2. 核心回答
    # 直接列出问题的要点答案，推荐使用项目符号（•）或编号。
    #
    # ### 3. 补充说明
    # 提供与本问题相关的限制条件、注意事项或上下文扩展信息（如有）。
    #             """
    #         )
    #
    #         return llm, chat_prompt, system_prompt

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

    # def _create_chain(self, session_id: str) -> ConversationalRetrievalChain:
    #     """创建对话链
    #
    #     Args:
    #         session_id: 会话ID
    #
    #     Returns:
    #         ConversationalRetrievalChain: 对话链实例
    #     """
    #     # 获取会话对应的记忆实例
    #     self.memory = self._get_memory(session_id)
    #
    #     # 创建对话链
    #     chain = ConversationalRetrievalChain.from_llm(
    #         llm=self.llm,
    #         retriever=self.retriever,
    #         memory=self.memory,
    #         combine_docs_chain_kwargs={
    #             "prompt": self.chat_prompt,
    #         },
    #         return_source_documents=True,
    #         verbose=True,
    #     )
    #
    #     return chain

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
                raise ValueError("问题不能为空")

            # # 创建/获取该会话的对话链
            # self.chain = self._create_chain(session_id)

            # 使用权限ID进行检索
            docs: List[Document] = self.retriever.get_relevant_documents(query, permission_ids=permission_ids)

            # 手动构建上下文
            context = "\n\n".join([doc.page_content for doc in docs])

            # 获取历史对话
            if self.memory is None:
                self.memory = self._get_memory(session_id)
            chat_history = self.memory.load_memory_variables({}).get("chat_history", [])

            # 渲染提示词
            prompt, config = render_prompt("rag_generate",
                                           {"context": context, "chat_history": chat_history, "question": query})
            system_prompt = "你是企业知识助手，请结合上下文详细展开，不要省略任何关键要点。"

            # 生成回答
            response_text = llm_manager.invoke(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=config["temperature"],
            )

            # # 使用LLM直接生成回答
            # response_text = self.llm.invoke(
            #     self.chat_prompt.format(
            #         context=context,
            #         chat_history=chat_history,
            #         question=query
            #     )
            # ).content

            # 更新对话记忆
            self.memory.save_context({"question": query}, {"answer": response_text})

            # 提取源文档元数据
            metadata = []
            # for doc in docs:
            #     metadata.append({
            #         "seg_id": doc.metadata.get("seg_id"),
            #         "doc_id": doc.metadata.get("doc_id"),
            #         "doc_http_url": doc.metadata.get("doc_http_url"),
            #         "doc_images_path": doc.metadata.get("doc_images_path", ""),
            #         "doc_created_at": doc.metadata.get("doc_created_at"),
            #         "doc_updated_at": doc.metadata.get("doc_updated_at"),
            #         "seg_page_idx": doc.metadata.get("seg_page_idx", 0),
            #         "score": doc.metadata.get("score", 0.0)
            #     })
            #
            # # 构建返回结果
            # result = {
            #     "answer": response_text.strip(),
            #     "session_id": session_id,
            #     "metadata": metadata,
            #     "chat_history": [
            #         {
            #             "role": msg.type,
            #             "content": msg.content
            #         }
            #         for msg in self.memory.chat_memory.messages
            #     ]
            # }
            logger.info(f"LLM 输出: {len(response_text.strip().split())} 个词；输入: {len(context.strip())} 字")
            return result

        except Exception as e:
            logger.error(f"生成回答失败: {str(e)}")
            raise ValueError(f"生成回答失败, 错误原因: {str(e)}")
