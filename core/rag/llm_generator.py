import os
from urllib.parse import quote
from collections import defaultdict
from typing import Dict, Optional, List, Union

from langchain.chains import ConversationalRetrievalChain
from langchain.schema import BaseRetriever
from langchain_core.messages import trim_messages, HumanMessage, AIMessage, BaseMessage

from config.global_config import GlobalConfig
from utils.log_utils import logger
from utils.llm_utils import llm_manager, llm_count_tokens, render_prompt, get_messages_for_rag


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

    def _save_to_history(self, session_id: str, query: str, answer: Union[str, None]) -> None:
        """保存用户与助手的每一轮对话"""
        # 根据 session_id 获取用户对话
        messages = self._history_store.get(session_id, [])
        # 追加更新
        messages.append(HumanMessage(content=query))
        messages.append(AIMessage(content=answer))
        # 将更新后的列表重新存储到 _history_store 中
        self._history_store[session_id] = messages

    @staticmethod
    def _local_path_to_url(local_path: str) -> str:
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
                          permission_ids: Union[str, list[str]] = None,
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
            # 检查输入合法性
            if not query or not query.strip():
                raise ValueError("问题不能为空")

            # 获取当前 session 的历史对话
            raw_history: List[BaseMessage] = self._get_history(session_id)
            complete_history = raw_history + [HumanMessage(content=query)]

            # 检索知识库
            docs = self.retriever.invoke(query, permission_ids=permission_ids)
            context = ""  # 初始化知识库信息
            metadata = []  # 初始化源数据信息
            # max_context_tokens = 10000
            if docs:
                # 构建 metadata
                for doc, score in docs:
                    raw_path = doc.metadata.get("page_pdf_path")
                    # 本地路径静态映射
                    doc.metadata["page_pdf_path"] = self._local_path_to_url(raw_path) if raw_path else None
                    metadata.append({**doc.metadata, "rerank_score": score})
            # print(f"重构后的检索结果(前端用): \n {metadata} \n 手动构建的检索结果(模型用): \n {context} \n")

            # 渲染提示词
            system_prompt, config = render_prompt("rag_system_prompt", {})

            # 构造 rag 上下文
            messages = get_messages_for_rag(
                system_prompt=system_prompt,
                history=complete_history,
                docs=docs,
                question=query,
            )
            print("构建好的 messages: \n", messages, "\n")

            # 模型调用生成回答
            response_text = llm_manager.invoke(
                messages=messages,
                temperature=config["temperature"],
                invoke_type="RAG生成"
            )

            # 保存历史对话
            self._save_to_history(session_id, query, response_text)
            raw_history = self._get_history(session_id)
            print(f"\n 已保存的历史会话: {raw_history} \n")


            # 构建返回结果
            result = {
                "answer": response_text.strip(),
                "session_id": session_id,
                "metadata": metadata,
                "chat_history": [
                    {"role": "user" if isinstance(msg, HumanMessage) else "assistant", "content": msg.content}
                    for msg in self._history_store[session_id]
                ]
            }
            return result

        except Exception as e:
            logger.error(f"生成回答失败: {str(e)}")
            raise ValueError(f"生成回答失败: {str(e)}")
