import sys
from pathlib import Path

from langchain_core.documents import Document

from utils.table_linearized import unescape_html_table

sys.path.append(str(Path(__file__).parent.parent))

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from core.rag.retriever import HybridRetriever
from databases.db_ops import select_by_id, select_ids_by_permission
from databases.mysql.operations import ChatMessageOperation, ChatSessionOperation
from utils.converters import local_path_to_url, normalize_permission_ids
from utils.llm_utils import EmbeddingManager, get_messages_for_rag, llm_manager, render_prompt
from utils.log_utils import log_exception, logger
from utils.validators import validate_permission_ids


class RAGGenerator:
    """RAG 生成器，处理用户查询并生成回答"""

    # def __init__(self):
    def __init__(self):
        """初始化 RAG 生成器"""
        # 初始化会话操作类
        self.session_op = ChatSessionOperation()
        self.message_op = ChatMessageOperation()
        # 会话历史缓存(提高性能)
        self._cache = {}

        # 初始化 embedding 模型
        self._embedding_manager = EmbeddingManager()
        # 初始化混合检索对象
        self._hybrid_search = HybridRetriever()

    def _get_history(self, session_id: str) -> list[BaseMessage]:
        """获取历史对话

        Args:
            session_id: 会话ID

        Returns:
            list[BaseMessage]: 历史对话列表，按时间正序
        """

        try:
            # 先检查缓存，如果缓存存在，则直接返回
            if session_id in self._cache:
                logger.debug(f"[缓存命中] session_id={session_id}")
                return self._cache[session_id]

            # 从数据库获取消息, 限制最大 10 条
            messages_data = self.message_op.get_message_by_session_id(session_id, limit=10)
            logger.debug(f"[历史消息] session_id={session_id}, 消息数量={len(messages_data)}")

            # 转换为 BaseMessage 对象
            messages = []
            for msg_data in messages_data:
                if msg_data["message_type"] == "human":
                    messages.append(HumanMessage(content=msg_data["content"]))
                elif msg_data["message_type"] == "ai":
                    messages.append(AIMessage(content=msg_data["content"]))

            # 更新缓存
            self._cache[session_id] = messages
            logger.debug(f"[缓存更新] session_id={session_id}, 消息数量={len(messages)}")
            return messages

        except Exception as e:
            logger.error(f"[历史消息失败] session_id={session_id}, error_msg={str(e)}")
            return []

    def _save_to_history(
        self,
        session_id: str,
        query: str,
        answer: str | None,
        metadata: dict[str, Any] | None = None,
        rewrite_query: str | None = None,
    ) -> None:
        """保存用户与助手的每一轮对话到数据库

        Args:
            session_id: 会话ID
            query: 用户查询
            answer: AI回答
            metadata: 元数据列表（seg_ids）
            rewrite_query: 改写后的查询(可选)
        """
        try:
            # 确保会话存在
            self.session_op.create_or_update_session(session_id=session_id)

            # 构建用户消息元数据
            user_metadata = None
            if rewrite_query and rewrite_query != query:
                user_metadata = {"rewrite_query": rewrite_query}

            # 保存用户消息
            self.message_op.save_message(
                session_id=session_id, message_type="human", content=query, metadata=user_metadata
            )

            # 保存 AI 回答
            self.message_op.save_message(
                session_id=session_id, message_type="ai", content=answer if answer else "", metadata=metadata
            )
            logger.info(f"[会话历史] 保存成功, session_id={session_id}, 消息类型=human+ai")

            # 更新缓存
            if session_id in self._cache:
                self._cache[session_id].extend(
                    [HumanMessage(content=query), AIMessage(content=answer if answer else "")]
                )
                logger.debug(f"[缓存更新] session_id={session_id}, 消息数量={len(self._cache[session_id])}")

        except Exception as e:
            logger.error(f"保存会话历史失败: {str(e)}")
            raise e

    def _build_metadata_from_reranked_results(
        self, reranked_results: list[dict[str, Any]], request_id: str | None = None
    ) -> dict[str, Any]:
        """根据 rerank 排序后的结果, 从 MySQL 中获取完整元数据并构建最终数据结构

        Args:
            reranked_results: rerank 排序后的实体记录列表
            request_id: 请求 ID

        Returns:
            dict[str, Any]:  包含完整元数据和存储格式的字典
        """

        try:
            if not reranked_results:
                logger.info(f"[元数据构建] request_id={request_id}, 重排序结果为空")
                return {"metadata": [], "metadata_storage": {"doc_info": []}}

            # 提取(doc_id, seg_id) 组合
            doc_seg_pairs = []
            rerank_scores = []

            for result in reranked_results:
                entity = result.get("entity", {})
                doc_id = entity.get("doc_id")
                seg_id = entity.get("seg_id")
                rerank_score = result.get("rerank_score", 0.0)

                if doc_id and seg_id:
                    doc_seg_pairs.append((doc_id, seg_id))
                    rerank_scores.append(rerank_score)

            # 调试：记录从 Milvus 获取的原始数据
            logger.info(f"[元数据构建] request_id={request_id}, Milvus 返回的原始数据:")
            for i, result in enumerate(reranked_results):
                entity = result.get("entity", {})
                logger.info(
                    f"  结果 {i + 1}: doc_id={entity.get('doc_id')}, seg_id={entity.get('seg_id')}, content={entity.get('seg_content', '')[:100]}..."
                )
            logger.debug(f"[元数据构建] request_id={request_id}, 提取到 {len(doc_seg_pairs)} 个唯一记录")

            # 从 mysql 获取完整记录
            mysql_records = select_by_id(
                table_name="segment_info",
                seg_id_list=[seg_id for _, seg_id in doc_seg_pairs],
                doc_id_list=[doc_id for doc_id, _ in doc_seg_pairs],
            )

            # 调试
            logger.info(f"数据库查询时用到的seg_id_list: {[seg_id for _, seg_id in doc_seg_pairs]}")
            logger.info(f"数据库查询时用到的doc_id_list: {[doc_id for doc_id, _ in doc_seg_pairs]}")
            # 检查数据一致性
            milvus_seg_ids = set(seg_id for _, seg_id in doc_seg_pairs)
            mysql_seg_ids = set(record.get("seg_id") for record in mysql_records if record.get("seg_id"))

            missing_in_mysql = milvus_seg_ids - mysql_seg_ids
            if missing_in_mysql:
                logger.warning(
                    f"[数据一致性检查] request_id={request_id}, 以下 seg_id 在 Milvus 中存在但在 MySQL 中缺失: {missing_in_mysql}"
                )
                logger.warning(f"[数据一致性检查] request_id={request_id}, 这可能是数据同步问题，建议检查文档处理日志")

            logger.info(f"[元数据构建] request_id={request_id}, 从 mysql 获取到 {len(mysql_records)} 条记录")
            logger.info(f"数据库查询到的记录为: {mysql_records}")

            # 构建 (doc_id, seg_id) 到 mysql 记录的映射
            mysql_record_map = {}
            for record in mysql_records:
                doc_id = record.get("doc_id")
                seg_id = record.get("seg_id")
                if doc_id and seg_id:
                    mysql_record_map[(doc_id, seg_id)] = record

            # 调试
            logger.info(f"从mysql 记录中提取后的结果: \n{mysql_record_map}")

            # 构建最终数据结构
            metadata = []  # 前端展示格式
            metadata_storage = {"doc_info": []}  # 存储格式

            for result in reranked_results:
                entity = result.get("entity", {})
                doc_id = entity.get("doc_id")
                seg_id = entity.get("seg_id")
                rerank_score = result.get("rerank_score", 0.0)

                if not doc_id or not seg_id:
                    logger.warning(
                        f"[元数据构建] request_id={request_id}, 记录缺少 doc_id 或 seg_id, 跳过: doc_id={doc_id}, seg_id={seg_id}"
                    )
                    continue

                # 获取对应的 mysql 记录
                mysql_record = mysql_record_map.get((doc_id, seg_id), {})

                # 调试
                logger.info(f"从重排序的结果中提取到的信息为: doc_id: {doc_id}, seg_id: {seg_id} ")
                logger.info(f"获取到的 mysql 记录为: \n{mysql_record}")

                # 构建存储格式
                storage_info = {
                    "doc_id": doc_id,
                    "seg_id": seg_id,
                    "rerank_score": rerank_score,
                    "seg_page_idx": entity.get("seg_page_idx", 0),
                    "seg_type": entity.get("seg_type", ""),
                }
                metadata_storage["doc_info"].append(storage_info)

                # 构建前端展示格式
                display_metadata = {
                    # 基础信息
                    "doc_id": doc_id,
                    "seg_id": seg_id,
                    "seg_page_idx": entity.get("seg_page_idx", 0),
                    "seg_type": entity.get("seg_type", ""),
                    "seg_content": mysql_record.get("seg_content", ""),
                    # 分数信息
                    "rerank_score": rerank_score,
                    "distance": result.get("distance", 0.0),
                    "score": result.get("score", 0.0),
                    # 从 mysql 获取的完整信息
                    "doc_name": mysql_record.get("doc_name", ""),
                    "doc_http_url": mysql_record.get("doc_http_url", ""),
                    # 处理路径转换
                    "page_png_path": local_path_to_url(mysql_record.get("page_png_path")),
                }

                # 处理表格内容的反编码
                if display_metadata.get("seg_type") == "table":
                    display_metadata["seg_content"] = unescape_html_table(display_metadata["seg_content"])

                # 添加到最终结果
                metadata.append(display_metadata)

            logger.info(
                f"[元数据构建] request_id={request_id}, 构建完成, 展示数据 {len(metadata)} 条, 存储数据 {len(metadata_storage['doc_info'])} 条"
            )

            return {"metadata": metadata, "metadata_storage": metadata_storage}

        except Exception as e:
            logger.error(f"[元数据构建失败] request_id={request_id}, error_msg={str(e)}")
            return {"metadata": [], "metadata_storage": {"doc_info": []}}

    def generate_response(
        self, query: str, session_id: str, permission_ids: str | list[str] | None = None, request_id: str | None = None
    ) -> dict:
        """生成回答

        Args:
            query: 用户问题
            session_id: 会话ID
            permission_ids: 权限ID
            request_id: 请求ID

        Returns:
            dict: 包含回答、元数据等的字典
        """
        try:
            # 检查输入合法性
            if not query or not query.strip():
                raise ValueError("问题不能为空")

            # 部门格式验证和转换
            validate_permission_ids(permission_ids)
            cleaned_dep_ids: list[str] = normalize_permission_ids(permission_ids)

            # 获取对应权限的文档 ID
            permission_type = "department"
            logger.debug(
                f"[RAG对话] request_id={request_id}, 开始检索 doc_ids, 权限类型={permission_type}, 部门ID={cleaned_dep_ids}"
            )
            doc_ids = select_ids_by_permission(
                table_name="permission_doc_link", permission_type=permission_type, cleaned_dep_ids=cleaned_dep_ids
            )

            # 调试
            logger.debug(f"根据权限查出的 doc_ids: {doc_ids}")

            # 获取当前 session 的历史对话
            raw_history: list[BaseMessage] = self._get_history(session_id)

            # 查询重写(根据历史对话)
            rewrite_query = self._rewrite_query_with_history(history=raw_history, question=query, session_id=session_id)

            # 生成查询向量
            rewrite_query_vector = self._embedding_manager.embed_text(rewrite_query)

            # 执行混合检索
            if doc_ids:
                # 有可查阅的文档,进行检索
                reranked_results = self._hybrid_search.retrieve(
                    query_text=rewrite_query,
                    query_vector=rewrite_query_vector,
                    doc_id_list=doc_ids,
                    top_k=5,
                    limit=50,
                    request_id=request_id,
                )
            else:
                # 没有可查阅的文档
                reranked_results = []

            # 根据重排序结构构建元数据
            metadata_info = self._build_metadata_from_reranked_results(
                reranked_results=reranked_results, request_id=request_id
            )
            metadata, metadata_storage = (metadata_info["metadata"], metadata_info["metadata_storage"])

            logger.info(
                f"[RAG对话] request_id={request_id}, 构建后的存储元数据:\n metadata={metadata}\n metadata_storage={metadata_storage}"
            )

            # 构建 RAG 上下文(转换为 Document 格式)
            docs = []
            for result in reranked_results:
                entity = result.get("entity", {})
                doc = Document(page_content=entity.get("seg_content", ""), metadata={**entity})
                docs.append(doc)

            # 构造 rag 上下文
            messages = get_messages_for_rag(history=raw_history, docs=docs, question=query)

            logger.info(f"[RAG对话] request_id={request_id}, 构建好的上下文:\n {messages}")

            # 模型调用生成回答
            response_text = llm_manager.invoke(messages=messages, temperature=0.1, invoke_type="RAG生成")

            # 兜底手段: 若模型仍回答超出控制的内容,则强制处理
            if not docs and "抱歉，知识库中没有找到相关信息" not in response_text:
                logger.warning(f"[模型修正] 知识库为空但模型回答了内容, 进行修正, 模型回答={response_text[:200]}...")
                response_text = "抱歉，知识库中没有找到相关信息"

            # 保存历史对话到数据库
            self._save_to_history(
                session_id=session_id,
                query=query,
                answer=response_text,
                metadata=metadata_storage,
                rewrite_query=rewrite_query,
            )

            # 构建返回结果
            result = {
                "query": query,
                "rewrite_query": rewrite_query,
                "answer": response_text.strip(),
                "session_id": session_id,
                "metadata": metadata,
            }
            return result

        except Exception as e:
            logger.error(f"[RAG生成失败] request_id={request_id}, session_id={session_id}, error_msg={str(e)}")
            log_exception("RAG生成异常", exc=e)
            raise ValueError(f"生成回答失败: {str(e)}") from e

    @staticmethod
    def _rewrite_query_with_history(history: list[BaseMessage], question: str, session_id: str) -> str:
        """使用LLM根据历史上下文重写用户 query，  生成检索用 query

        Args:
            history (list[BaseMessage]): 当前会话的历史对话
            question (str): 用户的最新问题
            session_id (str): 用户会话 ID

        Returns:
            str: 改写后的问题
        """
        try:
            if not history:
                logger.info(f"会话 {session_id} 无历史对话, 直接返回原问题")
                return question

            # 构建历史对话内容字符串
            history_content = ""
            # 只提取最近的 5 轮对话, 避免上下文过长
            recent_history = history[-10:]  # 最多取 10 条消息(5 轮对话)

            for msg in recent_history:
                # 空内容
                if not msg.content or not msg.content.strip():
                    logger.warning(f"历史消息为空, 跳过: {msg}")
                    continue

                if isinstance(msg, HumanMessage):
                    history_content += f"用户: {msg.content}\n"
                elif isinstance(msg, AIMessage):
                    history_content += f"助手: {msg.content}\n"

            # 如果历史内容为空,直接返回源问题
            if not history_content.strip():
                logger.info(f"会话 {session_id} 无历史对话, 直接返回原问题")
                return question

            # 渲染查询重写提示词
            prompt, config = render_prompt(
                "query_rewrite", {"history_content": history_content.strip(), "current_question": question}
            )

            # 调用 LLM 进行查询重写
            rewrite_query = llm_manager.invoke(
                prompt=prompt,
                temperature=config["temperature"],
                max_tokens=config["max_tokens"],
                invoke_type="查询重写",
            )

            # 清理和验证结果
            rewrite_query = rewrite_query.strip()
            # 改写后为空或超长,则返回源问题
            if not rewrite_query or len(rewrite_query) > config["max_tokens"]:
                logger.warning(f"查询重写结果异常, 使用原问题, 重写结果:{rewrite_query}")
                return question

            # 调试
            logger.debug(f"查询重写完成- 原问题:{question}, 重写后:{rewrite_query}")

            return rewrite_query

        except Exception as e:
            logger.error(f"查询重写失败: {str(e)}")
            # 发生异常时返回原问题,确保系统正常运行
            return question

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


if __name__ == "__main__":
    pass
