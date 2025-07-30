import re
import sys
from pathlib import Path

from langchain_core.documents import Document

from utils.table_linearized import unescape_html_table

sys.path.append(str(Path(__file__).parent.parent))

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, trim_messages

from core.rag.retriever import HybridRetriever
from databases.mysql.operations import chat_message_op, chat_session_op, chunk_op, permission_op
from utils.converters import local_path_to_url, normalize_permission_ids
from utils.llm_utils import EmbeddingManager, llm_count_tokens, llm_manager, render_prompt
from utils.log_utils import log_exception, logger
from utils.validators import validate_permission_ids


class RAGGenerator:
    """RAG 生成器，处理用户查询并生成回答"""

    # def __init__(self):
    def __init__(self):
        """初始化 RAG 生成器"""
        # 初始化会话操作类
        self.session_op = chat_session_op
        self.message_op = chat_message_op
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

    @staticmethod
    def _build_metadata_from_reranked_results(
        reranked_results: list[dict[str, Any]], request_id: str | None = None
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
            logger.debug(f"[元数据构建] request_id={request_id}, Milvus 返回的原始数据:")
            for i, result in enumerate(reranked_results):
                entity = result.get("entity", {})
                logger.debug(
                    f"  结果 {i + 1}: doc_id={entity.get('doc_id')}, seg_id={entity.get('seg_id')}, content={entity.get('seg_content', '')[:100]}..."
                )
            logger.debug(f"[元数据构建] request_id={request_id}, 提取到 {len(doc_seg_pairs)} 个唯一记录")

            # 从 mysql 获取完整记录
            mysql_records = chunk_op.get_segment_contents(
                seg_id_list=[seg_id for _, seg_id in doc_seg_pairs], doc_id_list=[doc_id for doc_id, _ in doc_seg_pairs]
            )

            # 调试
            logger.debug(f"数据库查询时用到的seg_id_list: {[seg_id for _, seg_id in doc_seg_pairs]}")
            logger.debug(f"数据库查询时用到的doc_id_list: {[doc_id for doc_id, _ in doc_seg_pairs]}")
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
            logger.debug(f"从mysql 记录中提取后的结果: \n{mysql_record_map}")

            # 构建最终数据结构
            metadata = []  # 前端展示格式
            metadata_storage = {"doc_info": []}  # 存储格式

            for result in reranked_results:
                entity = result.get("entity", {})
                seg_idx = int(entity.get("seg_idx"))
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
                    "seg_idx": seg_idx,
                    "doc_id": doc_id,
                    "seg_id": seg_id,
                    "rerank_score": rerank_score,
                    "seg_page_idx": entity.get("seg_page_idx", 0),
                    "seg_type": entity.get("seg_type", ""),
                }
                metadata_storage["doc_info"].append(storage_info)

                # 构建前端展示格式
                display_metadata = {
                    "seg_idx": seg_idx,
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
            doc_ids = permission_op.get_ids_by_permission(permission_type="department", subject_ids=cleaned_dep_ids)

            # 如果无文档可查，直接结束问答
            if not doc_ids:
                logger.warning(f"[RAG对话] request_id={request_id}, 无文档可查, 直接返回")

                answer = "抱歉，知识库中没有找到相关信息"

                # 保存历史对话到数据库
                self._save_to_history(session_id=session_id, query=query, answer=answer, metadata=[], rewrite_query="")
                return {
                    "query": query,
                    "rewrite_query": query,
                    "answer": answer,
                    "session_id": session_id,
                    "metadata": [],
                }

            # 调试
            logger.debug(f"根据权限查出的 doc_ids: {doc_ids}")

            # 获取当前 session 的历史对话
            raw_history: list[BaseMessage] = self._get_history(session_id)

            # 查询重写(根据历史对话)
            rewrite_query = self._rewrite_query_with_history(history=raw_history, question=query, session_id=session_id)

            # 生成查询向量
            rewrite_query_vector = self._embedding_manager.embed_text(rewrite_query)

            # 执行混合检索
            reranked_results = self._hybrid_search.retrieve(
                query_text=rewrite_query,
                query_vector=rewrite_query_vector,
                doc_id_list=doc_ids,
                top_k=5,
                limit=50,
                request_id=request_id,
            )

            # 如果检索结果为空，直接返回
            if not reranked_results:
                logger.warning(f"[RAG对话] request_id={request_id}, 检索结果为空, 直接返回")

                answer = "抱歉，知识库中没有找到相关信息"

                # 保存历史对话到数据库
                self._save_to_history(
                    session_id=session_id, query=query, answer=answer, metadata=[], rewrite_query=rewrite_query
                )
                return {
                    "query": query,
                    "rewrite_query": rewrite_query,
                    "answer": answer,
                    "session_id": session_id,
                    "metadata": [],
                }

            docs = []
            if reranked_results:
                # 为片段增加索引信息
                reranked_results = self._add_seg_idx(reranked_results)
                # 构建 RAG 上下文(转换为 Document 格式)
                docs = [
                    Document(
                        page_content=result.get("entity", {}).get("seg_content", ""),
                        metadata={**result.get("entity", {})},
                    )
                    for result in reranked_results
                ]

                # 调试
                logger.info(f"增加了索引的上下文: \n{docs[0] if docs else None}")

            # 构造上下文
            messages = self._get_messages_for_rag(history=raw_history, docs=docs, query=query)

            logger.info(f"[RAG对话] request_id={request_id}, 构建好的上下文:\n {messages}")

            # 模型调用生成回答
            response_text = llm_manager.invoke(messages=messages, temperature=0.1, invoke_type="RAG生成")

            # 提取引用编号, 清洗回答
            segment_idx, cleaned_answer = self._extract_segment_and_clean_answer(response_text)

            # 调试
            logger.debug(
                f"[RAG对话] request_id={request_id}, \n模型回答: {response_text}, \n\n清洗后的回答: {cleaned_answer}, \n\n提取到的编号: {segment_idx}"
            )

            # 根据重排序结构构建元数据
            filtered_reranked_results = []
            if segment_idx:
                filtered_reranked_results = [m for m in reranked_results if int(m.get("seg_idx")) in segment_idx]

            metadata_info = self._build_metadata_from_reranked_results(
                reranked_results=filtered_reranked_results, request_id=request_id
            )

            # 调试
            logger.debug(f"[RAG对话] request_id={request_id}, 过滤前的上下文:\n {reranked_results}")
            logger.debug(f"[RAG对话] request_id={request_id}, 提取后的上下文:\n {filtered_reranked_results}")
            # logger.debug(
            #     f"[RAG对话] request_id={request_id}, 构建后的存储元数据:\n metadata={metadata_info['metadata']}\n\n metadata_storage={metadata_info['metadata_storage']}"
            # )

            # 保存历史对话到数据库
            self._save_to_history(
                session_id=session_id,
                query=query,
                answer=cleaned_answer,
                metadata=metadata_info["metadata_storage"],
                rewrite_query=rewrite_query,
            )

            # 兜底手段: 若模型仍回答超出控制的内容,则强制处理
            if reranked_results and not segment_idx and "抱歉" not in cleaned_answer:
                logger.warning(f"[RAG修正] 模型回答没有引用任何知识段，进行修正, 模型回答={cleaned_answer[:200]}...")
                cleaned_answer = "抱歉，知识库中没有找到相关信息"

            # 构建返回结果
            result = {
                "query": query,
                "rewrite_query": rewrite_query,
                "answer": cleaned_answer,
                "session_id": session_id,
                "metadata": metadata_info["metadata"],
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

    @staticmethod
    def _build_history_messages(history: list[BaseMessage], history_max_len: int = 10000) -> tuple[list[dict], int]:
        """构建历史对话消息, 用于 OpenAI 接口构建数据
        - langchain的角色名称为: system, human, ai
        - openai的角色名称为: system, user, assistant

        Args:
            history: 历史对话, 采用 langchain 的 BaseMessage 格式, 角色名称应为: HumanMessage, AIMessage

        Returns:
            tuple(list[dict], int): 历史对话消息和 token 数
        """

        messages = []
        total_tokens = 0

        if not history:
            logger.debug("[消息构建] 无历史对话")
            return messages, total_tokens

        # ===== 历史对话处理 =====
        logger.debug(f"[消息构建] 开始处理历史对话, 原始条数={len(history)}")

        # 剪裁历史对话, 控制最大 token 长度, 避免使用 start_on 参数, 如果历史对话为空或只有一条消息，则不进行裁剪
        if len(history) <= 1:
            trimmed_history = history
            logger.debug("[消息构建] 历史对话为空或只有一条消息，不进行裁剪")
        else:
            trimmed_history: list[BaseMessage] = trim_messages(
                messages=history,  # list[BaseMessage]（历史对话）
                token_counter=llm_count_tokens,  # 函数，逐条调用, 计算每条消息的 token 数
                max_tokens=history_max_len,  # 限定最大 token 数
                strategy="last",  # 保留最近对话, "first"保留最早对话
                start_on="human",  # 裁剪指定角色前的内容, "ai"为从 AI 回答开始
                include_system=True,  # 是否保留 system message
                allow_partial=True,  # 超限时是否保留部分片段
            )
            logger.debug(f"[消息构建] 历史对话裁剪完成, 原始条数={len(history)}, 裁剪后条数={len(trimmed_history)}")

        # 转换为 OpenAI 接口格式
        history_tokens = 0
        for msg in trimmed_history:
            if not msg.content or not msg.content.strip():
                continue  # 忽略空内容

            msg_tokens = llm_count_tokens(msg.content)
            history_tokens += msg_tokens

            if isinstance(msg, HumanMessage):
                messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                messages.append({"role": "assistant", "content": msg.content})

        total_tokens += history_tokens
        logger.debug(
            f"[消息构建] 历史对话处理完成, 有效条数={len([m for m in messages if m['role'] in ['user', 'assistant']])}, token数={history_tokens}"
        )
        return messages, total_tokens

    @staticmethod
    def _build_knowledge_context(docs: list[Document], context_max_len: int = 10000) -> tuple[str, int]:
        """构建召回结果上下文, 用于 OpenAI 接口构建数据, 角色名称应为: system, user, assistant

        Args:
            docs: 召回结果, 采用 langchain 的 Document 格式
            context_max_len: 召回结果上下文最大长度

        Returns:
            tuple(str, int): 召回结果上下文和 token 数
        """
        total_tokens = 0
        docs_content = ""

        if not docs:
            docs_content += "知识库中无相关信息"
            logger.debug("[消息构建] 无召回结果")
            return docs_content, total_tokens

        # ===== 知识库信息 =====
        context_lines = []
        processed_docs = 0

        for doc in docs:
            if hasattr(doc, "metadata") and doc.metadata:
                seg_content = doc.metadata.get("seg_content", "")
                seg_idx = doc.metadata.get("seg_idx")
                if seg_content:
                    # 计算当前片段的 token 数
                    segment_tokens = llm_count_tokens(seg_content)
                    # 超限切割
                    if total_tokens + segment_tokens > context_max_len:
                        logger.debug("[消息构建] 知识库内容token数达到限制，裁剪后续内容")
                        break

                    docs_content += f"[段{seg_idx}]{seg_content}\n\n"
                    total_tokens += segment_tokens
                    context_lines.append(seg_content)
                    processed_docs += 1

        # 如果知识库信息不为空，则添加到 messages
        if docs_content:
            logger.debug(
                f"[消息构建] 知识库处理完成, 处理文档数={processed_docs}/{len(docs)}, context段数={len(context_lines)}, token数={total_tokens}"
            )
        else:
            # 当docs为空时，添加无相关信息提示
            docs_content += "知识库中无相关信息"
            logger.debug("[消息构建] 检索结果为空，知识库中无相关信息")

        return docs_content, total_tokens

    @staticmethod
    def _build_final_context(
        knowledge_content: str, history_messages: list[dict], query: str, history_tokens: int
    ) -> tuple[list[dict], int]:
        """构建最终的上下文, 用于 OpenAI 接口构建数据

        Args:
            knowledge_content: 知识库上下文
            history_messages: 历史对话消息
            query: 用户问题
            history_tokens: 历史对话 token 数

        Returns:
            tuple[list[dict], int]: 最终的上下文, 总 TOKEN 数
        """

        # 构建系统提示词
        system_prompt, _ = render_prompt("rag_system_prompt", {"retrieved_knowledge": knowledge_content})
        # 计算提示词 token 数量
        prompt_tokens = llm_count_tokens(system_prompt)

        messages = [{"role": "system", "content": system_prompt.strip()}]
        logger.debug("[上下文构建] 系统提示词构建完成")

        # 合并历史对话
        total_tokens = history_tokens + prompt_tokens
        messages.extend(history_messages)
        logger.debug("[上下文构建] 历史对话拼接完成")

        # 合并问题
        query_tokens = llm_count_tokens(query.strip())
        total_tokens += query_tokens
        messages.append({"role": "user", "content": query.strip()})
        logger.debug("[上下文构建] 最新问题拼接完成")

        return messages, total_tokens

    def _get_messages_for_rag(self, history: list[BaseMessage], docs: list[Document], query: str) -> list[dict]:
        """通过系统提示词, 历史对话, 用户提示词构造用于 Chat-style 模型的 messages 消息结构"""
        try:
            logger.info(f"[上下文构建] 开始, 历史对话数: {len(history)}, 文档数: {len(docs)}")

            # 1. 构建知识库上下文
            knowledge_content, knowledge_tokens = self._build_knowledge_context(docs)

            # 2. 构建历史对话
            history_messages, history_tokens = self._build_history_messages(history)

            # 3. 构建最终上下文
            messages, total_tokens = self._build_final_context(
                knowledge_content=knowledge_content,
                history_messages=history_messages,
                query=query,
                history_tokens=history_tokens,
            )

            logger.info(f"[上下文构建] 上下文构建完成, 总消息数: {len(messages)}, 总 token 数: {total_tokens}")

            return messages

        except Exception as e:
            logger.error(f"[消息构建] 失败: {str(e)}")
            log_exception("消息构建异常", exc=e)
            raise e

    @staticmethod
    def _extract_segment_and_clean_answer(answer: str) -> tuple[list, str]:
        """从模型输出中提取引用片段,并清洗模型输出

        Args:
            answer: 大模型回答

        Returns:
            tuple[list, str]: 片段索引列表和清洗后的模型回答
        """
        # 匹配标识符
        referenced = re.findall(r"\[段(\d+)]", answer)
        referenced_indices = set(int(x) for x in referenced)

        # 去除回答中的 [段x] 标签(后续可替换为其他信息)
        cleaned_answer = re.sub(r"\[段\d+]", "", answer)

        return list(referenced_indices), cleaned_answer.strip()

    @staticmethod
    def _filter_metadata_by_segment_indices(
        metadata: list[dict[str, str]], segment_idx: list[int]
    ) -> list[dict[str, str]]:
        """根据片段索引,从元数据中提取相关片段

        Args:
            metadata: 重排序后的元数据
            segment_idx: 片段索引列表

        Returns:
            list[dict[str, str]]: 提取出的相关片段
        """
        return [m for m in metadata if m.get("seg_idx") in segment_idx]

    @staticmethod
    def _add_seg_idx(reranked_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """为重排序结果增加片段索引,提供给大模型定位使用

        Args:
            reranked_results: 重排序结果

        Returns:
            list[dict[str, Any]]: 增加了片段索引的重排序结果
        """

        for idx, result in enumerate(reranked_results):
            result["entity"]["seg_idx"] = idx + 1
        return reranked_results

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
