# import sys
# from pathlib import Path

# sys.path.append(str(Path(__file__).parent.parent))

# from typing import Any

# from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

# from core.rag.retriever import HybridRetriever
# from databases.db_ops import select_by_seg_id, select_ids_by_permission
# from databases.mysql.operations import ChatMessageOperation, ChatSessionOperation
# from utils.converters import local_path_to_url, normalize_permission_ids
# from utils.llm_utils import EmbeddingManager, get_messages_for_rag, llm_manager, render_prompt
# from utils.log_utils import log_exception, logger
# from utils.validators import validate_permission_ids


# class RAGGenerator:
#     """RAG 生成器，处理用户查询并生成回答"""

#     # def __init__(self, retriever: BaseRetriever):
#     def __init__(self):
#         """初始化 RAG 生成器

#         Args:
#             retriever: 混合检索器实例
#         """
#         # self.retriever = retriever
#         # 初始化会话操作类
#         self.session_op = ChatSessionOperation()
#         self.message_op = ChatMessageOperation()
#         # 会话历史缓存(提高性能)
#         self._cache = {}

#         # 初始化 embedding 模型
#         self._embedding_manager = EmbeddingManager()
#         # 初始化混合检索对象
#         self._hybrid_search = HybridRetriever()

#     def _get_history(self, session_id: str) -> list[BaseMessage]:
#         """获取历史对话

#         Args:
#             session_id: 会话ID

#         Returns:
#             List[BaseMessage]: 历史对话列表，按时间正序
#         """

#         try:
#             # 先检查缓存，如果缓存存在，则直接返回
#             if session_id in self._cache:
#                 logger.debug(f"[缓存命中] session_id={session_id}")
#                 return self._cache[session_id]

#             # 从数据库获取消息, 限制最大 10 条
#             messages_data = self.message_op.get_message_by_session_id(session_id, limit=10)
#             logger.debug(f"[历史消息] session_id={session_id}, 消息数量={len(messages_data)}")

#             # 转换为 BaseMessage 对象
#             messages = []
#             for msg_data in messages_data:
#                 if msg_data["message_type"] == "human":
#                     messages.append(HumanMessage(content=msg_data["content"]))
#                 elif msg_data["message_type"] == "ai":
#                     messages.append(AIMessage(content=msg_data["content"]))

#             # 更新缓存
#             self._cache[session_id] = messages
#             logger.debug(f"[缓存更新] session_id={session_id}, 消息数量={len(messages)}")
#             return messages

#         except Exception as e:
#             logger.error(f"[历史消息失败] session_id={session_id}, error_msg={str(e)}")
#             return []

#     def _save_to_history(
#         self,
#         session_id: str,
#         query: str,
#         answer: str | None,
#         metadata: dict[str, Any] | None = None,
#         rewrite_query: str = None,
#     ) -> None:
#         """保存用户与助手的每一轮对话到数据库

#         Args:
#             session_id: 会话ID
#             query: 用户查询
#             answer: AI回答
#             metadata: 元数据列表（seg_ids）
#             rewrite_query: 改写后的查询(可选)
#         """
#         try:
#             # 确保会话存在
#             self.session_op.create_or_update_session(session_id=session_id)

#             # 构建用户消息元数据
#             user_metadata = None
#             if rewrite_query and rewrite_query != query:
#                 user_metadata = {"rewrite_query": rewrite_query}

#             # 保存用户消息
#             self.message_op.save_message(
#                 session_id=session_id, message_type="human", content=query, metadata=user_metadata
#             )

#             # 保存 AI 回答
#             self.message_op.save_message(session_id=session_id, message_type="ai", content=answer, metadata=metadata)
#             logger.info(f"[会话历史] 保存成功, session_id={session_id}, 消息类型=human+ai")

#             # 更新缓存
#             if session_id in self._cache:
#                 self._cache[session_id].extend([HumanMessage(content=query), AIMessage(content=answer)])
#                 logger.debug(f"[缓存更新] session_id={session_id}, 消息数量={len(self._cache[session_id])}")

#         except Exception as e:
#             logger.error(f"保存会话历史失败: {str(e)}")
#             raise e

#     # @staticmethod
#     # def _build_metadata(docs: list[Document]) -> dict[str, Any]:
#     #     """构建元数据信息
#     #
#     #     Args:
#     #         docs: 检索到的文档列表
#     #
#     #     Returns:
#     #         List[Dict]: 元数据列表
#     #     """
#     #     metadata_storage: dict[str, Any] = dict()
#     #     metadata_storage["doc_info"] = []
#     #     metadata = []
#     #
#     #     for doc in docs:
#     #         # 存储使用, 只保存 seg_id 和 rerank_score
#     #         metadata_storage["doc_info"].append(
#     #             {"seg_id": doc.metadata.get("seg_id"), "rerank_score": doc.metadata.get("rerank_score", 0.0)}
#     #         )
#     #
#     #         # 用于前端展示时, 包含所有字段
#     #         # 本地路径静态映射
#     #         raw_path = doc.metadata.get("page_png_path")
#     #         doc.metadata["page_png_path"] = local_path_to_url(raw_path) if raw_path else None
#     #         # 处理元数据中的非 JSON 序列化对象,如: datetime 等
#     #         clean_metadata = {}
#     #         for key, value in doc.metadata.items():
#     #             # 可序列化字段直接使用
#     #             if isinstance(value, (str, int, float, bool, list, dict)) or value is None:
#     #                 clean_metadata[key] = value
#     #             else:
#     #                 # 将其他类型转换为字符串
#     #                 clean_metadata[key] = str(value)
#     #         metadata.append(clean_metadata)
#     #
#     #     return {"metadata": metadata, "metadata_storage": metadata_storage}

#     @staticmethod
#     def _build_metadata_from_reranked_results(
#         reranked_docs: list[dict[str, Any]], request_id: str = None
#     ) -> dict[str, Any]:
#         """根据 rerank 排序后的结果, 从 MySQL 中获取完整元数据并构建最终数据结构

#         Args:
#             reranked_docs: 重排序后的文档列表
#             request_id: 请求 ID

#         Returns:
#             List[Dict]:  包含完整元数据和存储格式的字典
#         """

#         try:
#             if not reranked_docs:
#                 logger.info(f"[元数据构建] request_id={request_id}, 重排序结果为空, 返回空数据.")
#                 return {
#                     "metadata": [],
#                     "metadata_"
#                 }


#         metadata_storage: dict[str, Any] = dict()
#         metadata_storage["doc_info"] = []
#         metadata = []

#         for hit in docs:
#             # 存储使用, 只保存 seg_id 和 rerank_score
#             metadata_storage["doc_info"].append(
#                 {"seg_id": hit["entity"].get("seg_id"), "rerank_score": hit.get("rerank_score")}
#             )

#             # 用于前端展示时, 包含所有字段
#             # 本地路径静态映射
#             raw_path = doc.metadata.get("page_png_path")
#             doc.metadata["page_png_path"] = local_path_to_url(raw_path) if raw_path else None
#             # 处理元数据中的非 JSON 序列化对象,如: datetime 等
#             clean_metadata = {}
#             for key, value in doc.metadata.items():
#                 # 可序列化字段直接使用
#                 if isinstance(value, (str, int, float, bool, list, dict)) or value is None:
#                     clean_metadata[key] = value
#                 else:
#                     # 将其他类型转换为字符串
#                     clean_metadata[key] = str(value)
#             metadata.append(clean_metadata)

#         return {"metadata": metadata, "metadata_storage": metadata_storage}

#     def generate_response(
#         self,
#         query: str,
#         session_id: str,
#         permission_ids: str | list[str] = None,
#         request_id: str | None = None,
#     ) -> dict:
#         """生成回答

#         Args:
#             query: 用户问题
#             session_id: 会话ID
#             permission_ids: 权限ID
#             request_id: 请求ID

#         Returns:
#             Dict: 包含回答、元数据等的字典
#         """
#         try:
#             # 检查输入合法性
#             if not query or not query.strip():
#                 raise ValueError("问题不能为空")

#             # 部门格式验证和转换
#             validate_permission_ids(permission_ids)
#             cleaned_dep_ids: list[str] = normalize_permission_ids(permission_ids)

#             # 获取对应权限的文档 ID
#             permission_type = "department"
#             doc_ids = select_ids_by_permission(
#                 table_name="permission_info_table", permission_type=permission_type, cleaned_dep_ids=cleaned_dep_ids
#             )

#             # 获取当前 session 的历史对话
#             raw_history: list[BaseMessage] = self._get_history(session_id)

#             # 查询重写(根据历史对话)
#             rewrite_query = self._rewrite_query_with_history(history=raw_history, question=query, session_id=session_id)

#             # 生成查询向量
#             rewrite_query_vector = self._embedding_manager.embed_text(rewrite_query)

#             # 执行混合检索
#             docs = self._hybrid_search.search_documents(
#                 query_text=rewrite_query,
#                 query_vector=rewrite_query_vector,
#                 doc_ids=doc_ids,
#                 top_k=5,
#                 request_id=request_id,
#             )

#             # 调试: 打印知识库信息
#             for doc in docs:
#                 logger.debug(
#                     f"[检索结果] request_id={request_id}, doc_id={doc['metadata'].get('doc_id', 'unknown')}, seg_id={doc['metadata'].get('seg_id', 'unknown')}"
#                 )

#             # 初始化元数据变量
#             metadata = []
#             metadata_storage = {"doc_info": []}
#             if docs:
#                 # 查询 mysql 数据库原文
#                 seg_ids = []
#                 doc_ids = []
#                 for doc in docs:
#                     seg_ids.append(doc.metadata.get("seg_id"))
#                     doc_ids.append(doc.metadata.get("doc_id"))

#                 logger.debug(f"[混合检索] request_id={request_id}, Mysql 原文提取, 片段数量: {len(seg_ids)}")
#                 mysql_records: list[dict] = select_by_seg_id(
#                     table_name="segment_info_table", seg_ids=seg_ids, doc_ids=doc_ids
#                 )
#                 logger.debug(f"[混合检索] 原文提取完成, 权限过滤后返回={len(mysql_records)}条结果")

#                 # 构建两种格式的 metadata
#                 metadata_info = self._build_metadata(docs=docs)
#                 metadata, metadata_storage = metadata_info["metadata"], metadata_info["metadata_storage"]
#             else:
#                 docs = []

#             # 构造 rag 上下文
#             messages = get_messages_for_rag(
#                 history=raw_history,
#                 docs=docs,
#                 question=query,
#             )

#             # 模型调用生成回答
#             response_text = llm_manager.invoke(messages=messages, temperature=0.1, invoke_type="RAG生成")

#             # 兜底手段: 若模型仍回答超出控制的内容,则强制处理
#             if not docs and "抱歉，知识库中没有找到相关信息" not in response_text:
#                 logger.warning(f"[模型修正] 知识库为空但模型回答了内容, 进行修正, 模型回答={response_text[:200]}...")
#                 response_text = "抱歉，知识库中没有找到相关信息"

#             # 保存历史对话到数据库
#             self._save_to_history(
#                 session_id=session_id,
#                 query=query,
#                 answer=response_text,
#                 metadata=metadata_storage,
#                 rewrite_query=rewrite_query,
#             )

#             # 构建返回结果
#             result = {
#                 "query": query,
#                 "rewrite_query": rewrite_query,
#                 "answer": response_text.strip(),
#                 "session_id": session_id,
#                 "metadata": metadata,
#             }
#             return result

#         except Exception as e:
#             logger.error(f"[RAG生成失败] request_id={request_id}, session_id={session_id}, error_msg={str(e)}")
#             log_exception("RAG生成异常", exc=e)
#             raise ValueError(f"生成回答失败: {str(e)}")

#     @staticmethod
#     def _rewrite_query_with_history(history: list[BaseMessage], question: str, session_id: str) -> str:
#         """使用LLM根据历史上下文重写用户 query，  生成检索用 query

#         Args:
#             history (List[BaseMessage]): 当前会话的历史对话
#             question (str): 用户的最新问题
#             session_id (str): 用户会话 ID

#         Returns:
#             str: 改写后的问题
#         """
#         try:
#             if not history:
#                 logger.info(f"会话 {session_id} 无历史对话, 直接返回原问题")
#                 return question

#             # 构建历史对话内容字符串
#             history_content = ""
#             # 只提取最近的 5 轮对话, 避免上下文过长
#             recent_history = history[-10:]  # 最多取 10 条消息(5 轮对话)

#             for msg in recent_history:
#                 # 空内容
#                 if not msg.content or not msg.content.strip():
#                     continue

#                 if isinstance(msg, HumanMessage):
#                     history_content += f"用户: {msg.content}\n"
#                 elif isinstance(msg, AIMessage):
#                     history_content += f"助手: {msg.content}\n"

#             # 如果历史内容为空,直接返回源问题
#             if not history_content.strip():
#                 logger.info(f"会话 {session_id} 无历史对话, 直接返回原问题")
#                 return question

#             # 渲染查询重写提示词
#             prompt, config = render_prompt(
#                 "query_rewrite",
#                 {
#                     "history_content": history_content.strip(),
#                     "current_question": question,
#                 },
#             )

#             # 调用 LLM 进行查询重写
#             rewrite_query = llm_manager.invoke(
#                 prompt=prompt,
#                 temperature=config["temperature"],
#                 max_tokens=config["max_tokens"],
#                 invoke_type="查询重写",
#             )

#             # 清理和验证结果
#             rewrite_query = rewrite_query.strip()
#             # 改写后为空或超长,则返回源问题
#             if not rewrite_query or len(rewrite_query) > config["max_tokens"]:
#                 logger.warning(f"查询重写结果异常, 使用原问题, 重写结果:{rewrite_query}")
#                 return question
#             logger.info(f"查询重写完成- 原问题:{question}, 重写后:{rewrite_query}")
#             return rewrite_query

#         except Exception as e:
#             logger.error(f"查询重写失败: {str(e)}")
#             # 发生异常时返回原问题,确保系统正常运行
#             return question

#     def clear_cache(self, session_id: str = None) -> None:
#         """清除缓存

#         Args:
#             session_id: 指定会话ID，如果为None则清除所有缓存
#         """
#         try:
#             if session_id:
#                 if session_id in self._cache:
#                     del self._cache[session_id]
#                     logger.info(f"清除会话缓存成功, session_id: {session_id}")
#                 else:
#                     logger.warning(f"会话缓存不存在, session_id: {session_id}")
#             else:
#                 cache_count = len(self._cache)
#                 self._cache.clear()
#                 logger.info(f"清除所有缓存成功, 共清除 {cache_count} 个会话")
#         except Exception as e:
#             logger.error(f"清除缓存失败: {str(e)}")

#     # 在会话结束时调用
#     def end_session(self, session_id: str) -> None:
#         """结束会话，清理相关资源"""
#         self.clear_cache(session_id)
#         logger.info(f"会话结束，已清理缓存, session_id: {session_id}")


# if __name__ == "__main__":
#     pass
