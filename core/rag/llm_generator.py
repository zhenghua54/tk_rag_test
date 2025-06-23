import os
from urllib.parse import quote
from collections import defaultdict
from typing import Dict, Optional, List, Union

from langchain_core.documents import Document
from langchain.chains import ConversationalRetrievalChain
from langchain.schema import BaseRetriever
from langchain_core.messages import trim_messages, BaseMessage, HumanMessage, AIMessage

from config.global_config import GlobalConfig
from utils.log_utils import logger
from utils.llm_utils import llm_manager, llm_count_tokens, render_prompt


class RAGGenerator:
    """RAG 生成器，处理用户查询并生成回答"""

    # 类级别的会话记忆存储(简化为 message 列表)
    _history_store = defaultdict(list)

    def __init__(self, retriever: BaseRetriever):
        """初始化 RAG 生成器
        
        Args:
            retriever: 混合检索器实例
        """
        self.retriever = retriever
        self.memory = None

    def _get_history(self, session_id: str) -> List[BaseMessage]:
        """获取当前 session 的消息列表"""
        return self._history_store.get(session_id, [])

    def _save_to_history(self, session_id: str, query: str, answer: str) -> None:
        """保存用户与助手的每一轮对话"""
        # 根据 session_id 获取用户对话
        messages = self._history_store.get(session_id, [])
        # 追加更新
        messages.append(HumanMessage(content=query))
        messages.append(AIMessage(content=answer))

    @staticmethod
    def _messages_to_str(msgs: List[BaseMessage]) -> str:
        """将历史会话从对象转换为字符串, 供 Prompt 渲染"""
        return "\n".join([
            f"用户：{m.content}" if isinstance(m, HumanMessage) else f"助手：{m.content}"
            for m in msgs if isinstance(m, (HumanMessage, AIMessage))
        ])

    @staticmethod
    def _local_path_to_url(local_path:str) -> str:
        """将本路路径转换为 http url 地址"""
        # 转换源文档地址
        """将本地路径转换为 HTTP URL 地址"""
        if GlobalConfig.PATHS["origin_data"] in local_path:
            rel_path = os.path.relpath(local_path, GlobalConfig.PATHS["origin_data"])
            return f"http://192.168.5.199:8000/static/raw/{quote(rel_path)}"
        # 转换输出文档地址
        elif GlobalConfig.PATHS["processed_data"] in local_path:
            rel_path = os.path.relpath(local_path, GlobalConfig.PATHS["processed_data"])
            return f"http://192.168.5.199:8000/static/processed/{quote(rel_path)}"
        else:
            raise ValueError("不支持的路径, 未注册的路径地址")

    def generate_response(self,
                          query: str,
                          session_id: str,
                          permission_ids: Optional[str] = None,
                          request_id: Optional[str] = None,
                          ) -> Dict:
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

            # 使用权限ID进行检索
            # docs: List[Document] = self.retriever.get_relevant_documents(query, permission_ids=permission_ids)
            docs: Union[List[tuple[Document, float]],None] = self.retriever.get_relevant_documents(query,
                                                                                       permission_ids=permission_ids)




            if isinstance(docs, list):
                # 提取源文档元数据
                metadata: List = list()

                for doc, score in docs:
                    # 本地路径静态映射
                    doc.metadata["page_pdf_path"] = self._local_path_to_url(doc.metadata["page_pdf_path"])
                    metadata.append({
                        **doc.metadata,
                        "rerank_score": score
                    })
                # 手动构建检索到的上下文
                context = "\n\n".join([doc.page_content for doc, _ in docs])
                # print("上下文-->", docs[0])
            else:
                metadata = []
                context = ""

            # 获取当前 session 的历史对话
            raw_history: List[BaseMessage] = self._get_history(session_id)
            # 剪裁历史消息, 控制最大 token 长度
            trimmed_history: List[BaseMessage] = trim_messages(
                messages=raw_history,
                token_counter=llm_count_tokens,  # 实际 tokenizer,返回 token 数
                max_tokens=10000,
                strategy="last",
                start_on="human",
                include_system=True,
                allow_partial=False
            )
            # 转换为字符串
            chat_history = self._messages_to_str(trimmed_history)

            # 渲染提示词
            prompt, config = render_prompt("rag_generate",
                                           {"context": context, "chat_history": chat_history, "question": query})
            system_prompt = "你是企业知识助手，请结合上下文详细展开，不要省略任何关键要点。"

            # 生成回答
            response_text = llm_manager.invoke(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=config["temperature"],
                invoke_type="RAG生成"
            )

            # 保存历史对话
            self._save_to_history(session_id, query, response_text)

            # 构建返回结果
            result = {
                "answer": response_text.strip(),
                "session_id": session_id,
                "metadata": metadata,
                "chat_history": [
                    {
                        "role": msg.type,
                        "content": msg.content
                    }
                    for msg in self._history_store[session_id]
                ]
            }
            return result

        except Exception as e:
            logger.error(f"生成回答失败: {str(e)}")
            raise ValueError(f"生成回答失败, 错误原因: {str(e)}")
