"""混合检索模块"""

import time
from typing import Any

from config.global_config import GlobalConfig
from databases.milvus.flat_collection import FlatCollectionManager
from utils.llm_utils import embedding_manager, rerank_manager
from utils.log_utils import logger


class HybridRetriever:
    """混合检索器，结合向量检索和全文检索"""

    def __init__(self):
        """初始化混合检索器"""

        # 初始化 FLAT Collection 管理器
        self._flat_manager = FlatCollectionManager(
            collection_name=GlobalConfig.MILVUS_CONFIG["collection_name"]
        )

    # def _full_text_search(
    #     self,
    #     query_text: str,
    #     doc_ids: list[str],
    #     limit: int,
    #     request_id: str | None = None,
    # ) -> list[dict[str, Any]]:
    #     """执行全文检索 (BM25)
    #
    #     Args:
    #         query_text: 查询文本
    #         doc_ids: 文档ID列表
    #         limit: 返回结果数量
    #         request_id: 请求 ID
    #
    #     Returns:
    #         List[Dict[str, Any]]: 全文检索结果
    #     """
    #     try:
    #         logger.info(
    #             f"[全文检索] request_id={request_id}, 开始检索，查询: {query_text}"
    #         )
    #
    #         # 获取全文检索迭代器
    #         full_text_iterator = self._flat_manager.full_text_search(
    #             query_text=query_text, doc_ids=doc_ids, output_fields=["*"]
    #         )
    #
    #         if full_text_iterator is None:
    #             logger.warning(f"[全文检索] request_id={request_id}, 迭代器为空")
    #             return []
    #
    #         # 提取实体记录
    #         full_text_results = []
    #         try:
    #             while True:
    #                 batch = full_text_iterator.next()
    #                 if not batch:
    #                     break
    #
    #                 # 处理每个批次的结果
    #                 for hit in batch:
    #                     result = hit.to_dict()
    #                     full_text_results.append(result)
    #
    #         except Exception as e:
    #             logger.error(
    #                 f"[全文检索] request_id={request_id}, 迭代器遍历失败: {str(e)}"
    #             )
    #         finally:
    #             # 确保关闭迭代器
    #             full_text_iterator.close()
    #
    #         # 根据分数排序（BM25 分数越高越好）并提取前 limit 条
    #         full_text_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    #         full_text_results = full_text_results[:limit]
    #
    #         logger.info(
    #             f"[全文检索] request_id={request_id}, 完成，返回 {len(full_text_results)} 条结果"
    #         )
    #         return full_text_results
    #
    #     except Exception as e:
    #         logger.error(f"[全文检索] request_id={request_id}, 失败: {str(e)}")
    #         return []
    #
    # def _vector_search(
    #     self,
    #     query_vector: list[float],
    #     doc_ids: list[str],
    #     limit: int,
    #     request_id: str | None = None,
    # ) -> list[dict[str, Any]]:
    #     """执行向量检索
    #
    #     Args:
    #         query_vector: 查询向量
    #         doc_ids: 文档ID列表
    #         limit: 返回结果数量
    #         request_id: 请求 ID
    #
    #     Returns:
    #         List[Dict[str, Any]]: 向量检索结果
    #     """
    #     try:
    #         logger.info(
    #             f"[向量检索] request_id={request_id}, 开始检索，向量维度: {len(query_vector)}"
    #         )
    #
    #         # 获取向量检索迭代器
    #         vector_iterator = self._flat_manager.vector_search_iterator(
    #             query_vector=query_vector, doc_ids=doc_ids, output_fields=["*"]
    #         )
    #
    #         if vector_iterator is None:
    #             logger.warning(f"[向量检索] request_id={request_id}, 迭代器为空")
    #             return []
    #
    #         # 提取实体记录
    #         vector_results = []
    #
    #         try:
    #             while True:
    #                 batch = vector_iterator.next()
    #                 if not batch:
    #                     break
    #
    #                 # 处理每个批次的结果
    #                 for hit in batch:
    #                     result = hit.to_dict()
    #                     vector_results.append(result)
    #
    #         except Exception as e:
    #             logger.error(
    #                 f"[向量检索] request_id={request_id}, 迭代器遍历失败: {str(e)}"
    #             )
    #         finally:
    #             # 确保关闭迭代器
    #             vector_iterator.close()
    #
    #         # 根据相似度排序（向量相似度越高越好）并提取前 limit 条
    #         vector_results.sort(key=lambda x: x.get("distance", 0), reverse=True)
    #         vector_results = vector_results[:limit]
    #
    #         logger.info(
    #             f"[向量检索] request_id={request_id}, 完成，返回 {len(vector_results)} 条结果"
    #         )
    #         return vector_results
    #
    #     except Exception as e:
    #         logger.error(f"[向量检索] request_id={request_id}, 失败: {str(e)}")
    #         return []
    #
    # def _merge_results(
    #     self,
    #     full_text_results: list[dict[str, Any]],
    #     vector_results: list[dict[str, Any]],
    # ) -> list[dict[str, Any]]:
    #     """合并全文检索和向量检索结果
    #
    #     Args:
    #         full_text_results: 全文检索结果
    #         vector_results: 向量检索结果
    #
    #     Returns:
    #         List[Dict[str, Any]]: 合并后的结果
    #     """
    #     # 合并结果
    #     merged_result = full_text_results + vector_results
    #     logger.info(f"[结果合并] 合并后总数: {len(merged_result)} 条")
    #
    #     # 按 Milvus 分数排序(distance 和 score)
    #     merged_result.sort(
    #         key=lambda x: x.get("distance", x.get("score", 0)), reverse=True
    #     )
    #
    #     logger.info(
    #         f"[结果合并] 合并后的内容: {[(result['entity']['doc_id'], result['entity']['seg_id'], result['distance'], result['entity']['seg_content']) for result in merged_result]}"
    #     )
    #
    #     # 去重(基于doc_id 和seg_id)
    #     seen_keys = set()
    #     unique_results = []
    #     for result in merged_result:
    #         entity = result.get("entity", {})
    #         seg_id = entity.get("seg_id")
    #         doc_id = entity.get("doc_id")
    #
    #         if doc_id and seg_id:
    #             key = (doc_id, seg_id)
    #             if key not in seen_keys:
    #                 seen_keys.add(key)
    #                 unique_results.append(result)
    #
    #             else:
    #                 logger.debug(
    #                     f"[结果合并] 发现重复记录: doc_id={doc_id}, seg_id={seg_id}"
    #                 )
    #         else:
    #             logger.warning(
    #                 f"[结果合并] 记录缺少必要字段: doc_id={doc_id}, seg_id={seg_id}"
    #             )
    #
    #     logger.info(f"[结果合并] 去重后结果: {len(unique_results)} 条")
    #     return unique_results
    # def _hybrid_search(
    #     self,
    #     query_text: str,
    #     query_vector: list[float],
    #     doc_id_list: list[str],
    #     limit: int,
    # ) -> dict[str, Any] | None:
    #     """milvus 向量库混合检索
    #
    #     Args:
    #         query_text: 查询文本
    #         query_vector: 查询向量
    #         doc_id_list: 文档ID列表
    #         limit: 返回结果数量
    #
    #     Returns:
    #         List[Dict[str, Any]]: 检索结果列表
    #     """
    #     logger.info("[混合检索] 执行 Milvus 混合检索")
    #     start_time = time.time()
    #     try:
    #         # 获取 Milvus 的混合检索结果
    #         hybrid_results = self._flat_manager.optimized_hybrid_search(
    #             query_text=query_text,
    #             query_vector=query_vector,
    #             doc_id_list=doc_id_list,
    #             limit=limit,
    #         )
    #
    #         # 计算耗时
    #         duration = time.time() - start_time
    #         logger.info(f"[混合检索] Milvus 混合检索完成, 耗时: {duration:.3f}s")
    #
    #         return {
    #             "vector_results": vector_results,
    #             "full_text_results": full_text_results,
    #             "duration": duration,
    #         }
    #
    #     except Exception as e:
    #         logger.error(f"[混合检索] 检索失败: {str(e)}")
    #         return None

    def retrieve(
        self,
        query_text: str,
        query_vector: list[float],
        doc_id_list: list[str],
        top_k: int,
        limit: int,
        request_id: str | None = None,
    ) -> list[dict]:
        """执行混合检索流程

        Args:
            query_text: 查询文本
            query_vector: 查询向量
            doc_id_list: 文档 ID 列表
            top_k: 最终返回的结果数量
            limit: 初始检索数量
            request_id: 请求 ID

        Returns:
            List[Document]: 重排序后的实体记录列表
        """
        logger.info(
            f"[混合检索] request_id={request_id}, 开始检索, limit={limit}, top_k={top_k}"
        )
        start_time = time.time()

        # 执行混合检索
        try:
            logger.info("[混合检索] 执行 Milvus 混合检索")
            # 获取 Milvus 的混合检索结果
            hybrid_results = self._flat_manager.optimized_hybrid_search(
                query_text=query_text,
                query_vector=query_vector,
                doc_id_list=doc_id_list,
                limit=limit,
            )

            # 计算耗时
            duration = time.time() - start_time
            logger.info(f"[混合检索] Milvus 混合检索完成, 耗时: {duration:.3f}s")
            #
            # # 执行全文检索(BM25)和向量检索
            # full_text_results = self._full_text_search(
            #     query_text=query_text, doc_ids=doc_ids, limit=limit
            # )
            # vector_results = self._vector_search(
            #     query_vector=query_vector, doc_ids=doc_ids, limit=limit
            # )
            #
            # # 合并结果并按 Milvus 分数排序
            # merged_results = self._merge_results(
            #     full_text_results=full_text_results,
            #     vector_results=vector_results,
            # )
            # if not merged_results:
            #     logger.info(f"[混合检索] request_id={request_id}, 没有检索到结果")
            #     return []

            # 执行 rerank 重排序
            reranked_results = self._custom_rerank(
                query_text=query_text,
                hybrid_results=hybrid_results[0],
                top_k=top_k,
                request_id=request_id,
            )

            # 计算耗时
            duration = time.time() - start_time
            logger.info(
                f"[混合检索] request_id={request_id}, 检索完成, 耗时: {duration:.3f}s, 返回={len(reranked_results)}条结果"
            )

            # 返回结果
            return reranked_results

        except Exception as e:
            logger.error(f"[混合检索] request_id={request_id}, 检索失败: {str(e)}")
            return []

    @staticmethod
    def _detect_cliff_and_filter(
        filtered_results: list[dict], top_k: int, request_id: str | None = None
    ) -> list[dict]:
        """一阶差分算法, 自动检测重排分数的断崖点，并据此过滤文档。
        Args:
            filtered_results: 排名后的 rerank 列表, 分数为 rerank_score, 相似度分数为 distance
            top_k: 最大保留文档数，None 表示不限。

        Returns:
            List[dict]: 过滤后的文档列表（保留到断崖点前）。
        """
        # 提取 rerank 分数
        scores = [result.get("rerank_score", 0.0) for result in filtered_results]

        # 计算一阶差分：相邻两个分数之间的“下降值”
        deltas = [scores[i + 1] - scores[i] for i in range(len(scores) - 1)]

        # 检查deltas 是否为空
        if not deltas:
            logger.warning(
                f"[梯度截断] request_id={request_id}, 差分列表为空，直接返回前 top_k 个结果"
            )
            return filtered_results[:top_k]

        # 找出“下降最大”的位置（断崖点）
        min_delta = min(deltas)
        cliff_index = None
        for idx, delta in enumerate(deltas):
            if delta == min_delta:
                cliff_index = idx + 1
                break

        # 取 min(cliff_index, top_k)
        cliff_index = min(cliff_index, top_k) if cliff_index else top_k

        logger.info(
            f"[梯度截断] request_id={request_id}, 检测到断崖点位置: {cliff_index}, 返回前 {cliff_index} 个结果"
        )

        # 返回断崖前的文档列表
        return filtered_results[:cliff_index]

    def _custom_rerank(
        self,
        query_text: str,
        hybrid_results: list[dict[str, Any]],
        top_k: int,
        request_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """执行 rerank 重排序, 并根据相关性过滤

        Args:
            query_text: 查询文本
            hybrid_results: Milvus 混合检索结果
            top_k: 最终返回数量
            request_id: 请求 ID

        Returns:
             list[dict[str, Any]]: 重排序并过滤后的结果
        """
        try:
            if not hybrid_results:
                logger.info(f"[重排序] request_id={request_id}, Milvus 混合检索为空")
                return []

            # 提取文本内容用于 rerank
            passages = []
            for result in hybrid_results:
                content = result.get("entity", {}).get("seg_content")
                passages.append(content)

            # 执行 rerank
            scores = rerank_manager.rerank(
                query=query_text,
                passages=passages,
            )
            # 添加 rerank 分数到结果中
            for result, score in zip(hybrid_results, scores, strict=False):
                result["rerank_score"] = score

            # 按 rerank 分数排序
            hybrid_results.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)

            logger.info(
                f"[重排序] request_id={request_id}, 按照 rerank 分数排序后的结果:\n {hybrid_results}"
            )

            # 相关性过滤(基于 rerank 分数)
            relevance_threshold = -20  # 相关性阈值，可根据实际效果调整
            filtered_results = []
            for result in hybrid_results:
                score = result.get("rerank_score", 0)
                if score >= relevance_threshold:
                    filtered_results.append(result)
                else:
                    seg_id = result.get("entity", {}).get("seg_id", "unknown")
                    logger.debug(
                        f"[相关性过滤] request_id={request_id}, 过滤低相关性文档, score={score:.4f}, seg_id={seg_id}"
                    )

            logger.info(
                f"[相关性过滤] request_id={request_id}, 过滤前={len(hybrid_results)}, 过滤后={len(filtered_results)}, 阈值={relevance_threshold}"
            )

            # 空结果处理
            if not filtered_results:
                logger.warning(
                    f"[相关性过滤] request_id={request_id}, 所有文档相关性都低于阈值: {relevance_threshold}"
                )
                return []

            if len(filtered_results) <= top_k:
                logger.info(
                    f"[相关性过滤] request_id={request_id}, 文档数量: {len(filtered_results)} < {top_k}, 直接返回."
                )
                return filtered_results

            # 使用一阶差分算法进行梯度截断
            final_results = self._detect_cliff_and_filter(
                filtered_results, top_k=top_k, request_id=request_id
            )
            logger.info(
                f"[重排序] request_id={request_id}, 完成, 梯度截断后={len(final_results)}条结果"
            )
            return final_results

        except Exception as error:
            logger.error(f"[重排序失败] error_msg={str(error)}")
            return []


hybrid_retriever = HybridRetriever()

if __name__ == "__main__":
    # # 测试相似度检索
    # rag = HybridRetriever()
    # query = "质量管理"
    # embedding_manager = EmbeddingManager()
    # query_vector = embedding_manager.embed_text(query)
    # doc_ids = [
    #     "9b9baf68f3e743d2ad4899ce6ecae6d50f09f9144b807eda710780585a4409ec",
    # ]
    # limit = 2
    # iter = rag._search_vector(query_vector=query_vector, doc_ids=doc_ids, limit=limit)
    # print(len(iter))
    # # 测试迭代器
    # # print(list(iter[0].keys()))
    # # print(list(iter[0]["entity"].keys()))
    # print("-" * 20)
    # for doc in iter:
    #     print(doc)

    # 使用示例
    retriever = HybridRetriever()

    # 准备查询参数
    query_text = "人工智能技术"
    query_vector = embedding_manager.embed_text(query_text)
    doc_ids = ["doc_001", "doc_002", "doc_003"]
    limit = 10

    # 执行混合检索
    results = retriever._hybrid_search(
        query_text=query_text, query_vector=query_vector, doc_ids=doc_ids, limit=limit
    )

    if results:
        print(f"向量检索结果: {len(results['vector_results'])} 条")
        print(f"全文检索结果: {len(results['full_text_results'])} 条")
        print(f"检索耗时: {results['duration']:.3f}s")
