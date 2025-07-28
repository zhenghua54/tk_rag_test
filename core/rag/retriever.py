"""混合检索模块"""

import time
from typing import Any

from config.global_config import GlobalConfig
from databases.milvus.flat_collection import FlatCollectionManager
from utils.llm_utils import embedding_manager, rerank_manager
from utils.log_utils import log_exception, logger


class HybridRetriever:
    """混合检索器，结合向量检索和全文检索"""

    def __init__(self):
        """初始化混合检索器"""

        # 初始化 FLAT Collection 管理器
        self._flat_manager = FlatCollectionManager(collection_name=GlobalConfig.MILVUS_CONFIG["collection_name"])

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
            list[Document]: 重排序后的实体记录列表
        """
        logger.info(f"[混合检索] request_id={request_id}, 开始检索, limit: {limit}, top_k: {top_k}")
        start_time = time.time()

        # 执行混合检索
        try:
            # 获取 Milvus 的混合检索结果, (milvus自带混合检索)类型: <class 'pymilvus.client.search_result.SearchResult'>
            # 获取 Milvus 的混合检索结果, (自定义实现混合检索)类型: list[list[dict]]
            hybrid_results: list[list[dict]] = self._flat_manager.optimized_hybrid_search(
                query_text=query_text, query_vector=query_vector, doc_id_list=doc_id_list, limit=limit
            )
            logger.debug("[混合检索] hybrid_results: ")
            for result in hybrid_results[0]:
                logger.debug(result)

            # 计算耗时
            duration = time.time() - start_time
            logger.info(
                f"[混合检索] request_id={request_id}, Milvus 混合检索完成, 耗时: {duration:.3f}s, 召回数量：{len(hybrid_results[0])} "
            )

            # # 调试
            # if hybrid_results:
            #     logger.debug(f"[混合检索] request_id={request_id}, Milvus 混合检索召回内容: ")
            #     for result in hybrid_results[0]:
            #         logger.debug(f"doc_id: {result['entity']['doc_id']}")
            #         logger.debug(f"seg_id: {result['entity']['seg_id']}")
            #         logger.debug(f"seg_content: {result['entity']['seg_content']}")

            # 执行 rerank 重排序
            reranked_results = self._custom_rerank(
                query_text=query_text, hybrid_results=hybrid_results[0], top_k=top_k, request_id=request_id
            )

            # 计算耗时
            duration = time.time() - start_time
            logger.info(
                f"[混合检索] request_id={request_id}, 检索完成, 耗时: {duration:.3f}s, 返回: {len(reranked_results)} 条结果"
            )

            # 返回结果
            return reranked_results

        except Exception as e:
            logger.error(f"[混合检索] request_id={request_id}, 检索失败: {str(e)}")
            log_exception("混合检索失败", exc=e)
            return []

    @staticmethod
    def _detect_cliff_and_filter(filtered_results: list[dict], top_k: int, request_id: str | None = None) -> list[dict]:
        """一阶差分算法, 自动检测重排分数的断崖点，并据此过滤文档。
        Args:
            filtered_results: 排名后的 rerank 列表, 分数为 rerank_score, 相似度分数为 distance
            top_k: 最大保留文档数，None 表示不限。

        Returns:
            list[dict]: 过滤后的文档列表（保留到断崖点前）。
        """
        # 提取 rerank 分数
        scores = [result.get("rerank_score", 0.0) for result in filtered_results]

        # 计算一阶差分：相邻两个分数之间的“下降值”
        deltas = [scores[i + 1] - scores[i] for i in range(len(scores) - 1)]

        # 检查deltas 是否为空
        if not deltas:
            logger.warning(f"[梯度截断] request_id={request_id}, 差分列表为空，直接返回前 top_k 个结果")
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

        logger.info(f"[梯度截断] request_id={request_id}, 检测到断崖点位置: {cliff_index}, 返回前 {cliff_index} 个结果")

        # 返回断崖前的文档列表
        return filtered_results[:cliff_index]

    def _custom_rerank(
        self, query_text: str, hybrid_results: list[dict[str, Any]], top_k: int, request_id: str | None = None
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
            scores = rerank_manager.rerank(query=query_text, passages=passages)
            # 添加 rerank 分数到结果中
            for result, score in zip(hybrid_results, scores, strict=False):
                result["rerank_score"] = score

            # 按 rerank 分数排序
            hybrid_results.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)

            # 调试
            logger.debug(f"[重排序] request_id={request_id}, 按照 rerank 分数排序后的结果:")
            for result in hybrid_results:
                logger.debug(result)

            # 相关性过滤(基于 rerank 分数)
            relevance_threshold = -5  # 相关性阈值，可根据实际效果调整
            filtered_results = []
            for result in hybrid_results:
                score = result.get("rerank_score", 0)
                if score >= relevance_threshold:
                    filtered_results.append(result)
                else:
                    seg_id = result.get("entity", {}).get("seg_id", "unknown")
                    logger.debug(
                        f"[重排序] 阈值过滤, request_id={request_id}, 低于阈值,过滤掉该分块, seg_id: {seg_id}, score: {score:.4f}"
                    )

            # 调试
            logger.debug(
                f"[重排序] 阈值过滤, request_id={request_id}, 过滤前: {len(hybrid_results)}, 过滤后: {len(filtered_results)}, 阈值: {relevance_threshold}"
            )

            # 空结果处理
            if not filtered_results:
                logger.warning(f"[重排序] 阈值过滤, request_id={request_id}, 所有文档相关性都低于阈值")
                return []

            # 调试
            logger.debug(f"[重排序] 阈值过滤, request_id={request_id}, 阈值过滤后的分块内容如下:")
            for result in filtered_results:
                logger.debug(result)

            if len(filtered_results) <= top_k:
                logger.info(
                    f"[重排序] 阈值过滤, request_id={request_id}, 文档数量: {len(filtered_results)} < {top_k}, 直接返回."
                )
                return filtered_results

            # 使用一阶差分算法进行梯度截断
            final_results = self._detect_cliff_and_filter(filtered_results, top_k=top_k, request_id=request_id)
            logger.info(
                f"[重排序] 梯度过滤, request_id={request_id}, 梯度过滤完成, 过滤前 {len(filtered_results)} 条, 过滤后: {len(final_results)} 条"
            )

            # 调试
            if not final_results:
                logger.debug(f"[重排序] 梯度过滤, request_id={request_id}, 阈值过滤后的分块内容如下:")
                for result in final_results:
                    logger.debug(result)

            return final_results

        except Exception as error:
            logger.error(f"[重排序] 失败: {str(error)}")
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
    query_text = "省外出差补贴"
    query_vector = embedding_manager.embed_text(query_text)
    doc_id_list = [
        "308802d4082973cf8c3a548413585e753b4d37ffa8f8e16a3a005e8023066e52",
        "84bf50f240e290c94c850ee5f936838368c61b7f1e3be4f321f4aa9c2b843021",
        "162680e39129e7f6a7df0005160ac5fbb11d7c7fd1b65d7182e4ea8b2b258b26",
        "c2815526bd0fafe2ab7874b43efe9b58cf840c6dba94d49228a2d9506cbffd62",
    ]
    limit = 10

    # 执行混合检索
    results = retriever.retrieve(
        query_text=query_text, query_vector=query_vector, doc_id_list=doc_id_list, limit=limit, top_k=limit
    )

    if results:
        for result in results:
            print(result)
