import os
from urllib.parse import quote
from typing import Dict, Optional, List, Union
from langchain_core.documents import Document

from langchain.chains import ConversationalRetrievalChain
from langchain.schema import BaseRetriever
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from config.global_config import GlobalConfig
from utils.log_utils import logger
from utils.llm_utils import llm_manager, render_prompt, get_messages_for_rag
from databases.mysql.operations import ChatSessionOperation, ChatMessageOperation


class RAGGenerator:
    """RAG 生成器，处理用户查询并生成回答"""

    def __init__(self, retriever: BaseRetriever):
        """初始化 RAG 生成器
        
        Args:
            retriever: 混合检索器实例
        """
        self.retriever = retriever
        # 初始化会话操作类
        self.session_op = ChatSessionOperation()
        self.message_op = ChatMessageOperation()
        # 会话历史缓存(提高性能)
        self._cache = {}

    def _get_history(self, session_id: str) -> List[BaseMessage]:
        """获取历史对话
    
        Args:
            session_id: 会话ID
            
        Returns:
            List[BaseMessage]: 历史对话列表，按时间正序
        """

        try:
            # 先检查缓存，如果缓存存在，则直接返回
            if session_id in self._cache:
                logger.info(f"从缓存获取消息历史, session_id: {session_id}")
                return self._cache[session_id]

            # 从数据库获取消息
            messages_data = self.message_op.get_message_by_session_id(session_id)
            logger.info(f"从数据库获取消息历史, session_id: {session_id}, 消息数量: {len(messages_data)}")

            # 转换为 BaseMessage 对象
            messages = []
            for msg_data in messages_data:
                if msg_data['message_type'] == 'human':
                    messages.append(HumanMessage(content=msg_data['content']))
                elif msg_data['message_type'] == 'ai':
                    messages.append(AIMessage(content=msg_data['content']))

            # 更新缓存
            self._cache[session_id] = messages
            logger.info(f"更新缓存, session_id: {session_id}, 消息数量: {len(messages)}")
            return messages

        except Exception as e:
            logger.error(f"获取会话历史失败: {str(e)}")
            return []

    def _save_to_history(self, session_id: str, query: str, answer: Union[str, None],
                         metadata: Optional[List[Dict]] = None) -> None:
        """保存用户与助手的每一轮对话到数据库
    
        Args:
            session_id: 会话ID
            query: 用户查询
            answer: AI回答
            metadata: 元数据列表（用于存储的简化格式）
        """
        try:
            # 确保会话存在
            self.session_op.create_or_update_session(session_id=session_id)

            # 保存用户消息
            self.message_op.save_message(
                session_id=session_id,
                message_type='human',
                content=query,
                metadata=None
            )

            # 保存助手消息
            self.message_op.save_message(
                session_id=session_id,
                message_type='ai',
                content=answer,
                metadata=metadata
            )
            logger.info(f"保存会话历史成功, session_id: {session_id}, 消息数量: {len(self._cache[session_id])}")

            # 更新缓存
            if session_id in self._cache:
                self._cache[session_id].extend([
                    HumanMessage(content=query),
                    AIMessage(content=answer)
                ])
                logger.info(f"更新缓存, session_id: {session_id}, 消息数量: {len(self._cache[session_id])}")

        except Exception as e:
            logger.error(f"保存会话历史失败: {str(e)}")
            raise e

    def _build_metadata(self, docs: List[Document], for_storage: bool = False) -> List[Dict]:
        """构建元数据信息
        
        Args:
            docs: 检索到的文档列表
            for_storage: 是否用于存储（True=简化格式，False=完整格式）
            
        Returns:
            List[Dict]: 元数据列表
        """
        metadata = []

        if docs:
            for doc in docs:
                if for_storage:
                    # 用于存储时, 只包含 seg_id 和 rerank_score
                    clean_metadata = {
                        "seg_id": doc.metadata.get("seg_id"),
                        "rerank_score": doc.metadata.get("rerank_score", 0.0)
                    }
                else:
                    # 用于前端展示时, 包含所有字段
                    raw_path = doc.metadata.get("page_pdf_path")
                    # 本地路径静态映射
                    doc.metadata["page_pdf_path"] = self._local_path_to_url(raw_path) if raw_path else None

                    # 处理元数据中的非 JSON 序列化对象,如: datetime 等
                    clean_metadata = {}
                    for key, value in doc.metadata.items():
                        # 可序列化字段直接使用
                        if isinstance(value, (str, int, float, bool, list, dict)) or value is None:
                            clean_metadata[key] = value
                        else:
                            # 将其他类型转换为字符串
                            clean_metadata[key] = str(value)

                metadata.append(clean_metadata)
        return metadata

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

            # 初始化元数据变量
            metadata: List[Dict] = []  # 用于前端展示
            metadata_storage: List[Dict] = []  # 用于存储

            if docs:
                # 构建两种格式的 metadata
                metadata_storage = self._build_metadata(docs=docs, for_storage=True)
                metadata = self._build_metadata(docs=docs, for_storage=False)

            # 渲染提示词
            system_prompt, config = render_prompt("rag_system_prompt", {})

            # 构造 rag 上下文
            messages = get_messages_for_rag(
                system_prompt=system_prompt,
                history=complete_history,
                docs=docs,
                question=query,
            )

            # 模型调用生成回答
            response_text = llm_manager.invoke(
                messages=messages,
                temperature=config["temperature"],
                invoke_type="RAG生成"
            )

            # 保存历史对话到数据库
            self._save_to_history(session_id, query, response_text, metadata_storage)

            # 构建返回结果
            result = {
                "answer": response_text.strip(),
                "session_id": session_id,
                "metadata": metadata,
                "chat_history": [
                    {"role": "user" if isinstance(msg, HumanMessage) else "ai", "content": msg.content}
                    for msg in self._get_history(session_id)
                ]
            }
            return result

        except Exception as e:
            logger.error(f"生成回答失败: {str(e)}")
            raise ValueError(f"生成回答失败: {str(e)}")

    @staticmethod
    def _local_path_to_url(local_path: str) -> str:
        """将本路路径转换为 http url 地址"""
        # 转换源文档地址
        if GlobalConfig.PATHS["origin_data"] in local_path:
            rel_path = os.path.relpath(local_path, GlobalConfig.PATHS["origin_data"])
            # return f"http://192.168.5.199:8000/static/raw/{quote(rel_path)}"
            return f"/static/raw/{quote(rel_path)}"
        # 转换输出文档地址
        elif GlobalConfig.PATHS["processed_data"] in local_path:
            rel_path = os.path.relpath(local_path, GlobalConfig.PATHS["processed_data"])
            # return f"http://192.168.5.199:8000/static/processed/{quote(rel_path)}"
            return f"/static/processed/{quote(rel_path)}"
        else:
            raise ValueError("不支持的路径, 未注册的路径地址")

    def clear_cache(self, session_id: str = None) -> None:
        """清除缓存
        
        Args:
            session_id: 指定会话ID，如果为None则清除所有缓存
        """
        try:
            if session_id:
                if session_id in self._cache:
                    del self._cache[session_id]
                    logger.info(f"清除会话缓存成功, session_id: {session_id}")
                else:
                    logger.warning(f"会话缓存不存在, session_id: {session_id}")
            else:
                cache_count = len(self._cache)
                self._cache.clear()
                logger.info(f"清除所有缓存成功, 共清除 {cache_count} 个会话")
        except Exception as e:
            logger.error(f"清除缓存失败: {str(e)}")

    # 在会话结束时调用
    def end_session(self, session_id: str) -> None:
        """结束会话，清理相关资源"""
        self.clear_cache(session_id)
        logger.info(f"会话结束，已清理缓存, session_id: {session_id}")
