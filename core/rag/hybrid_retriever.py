"""混合检索模块"""
from typing import List, Any, Dict, OrderedDict, Union, Optional

from langchain.schema import BaseRetriever
from langchain_core.documents import Document

from config.global_config import GlobalConfig
# from core.rag.retrieval.bm25_retriever import BM25Retriever
from core.rag.retrieval.vector_retriever import VectorRetriever
# from databases.elasticsearch.operations import ElasticsearchOperation
from databases.milvus.flat_collection import FlatCollectionManager
from databases.mysql.operations import ChunkOperation
from utils.llm_utils import rerank_manager
from utils.log_utils import logger, log_exception


# def init_retrievers():
#     """初始化检索器
#
#     Returns:
#         tuple: (vector_retriever, bm25_retriever)
#     """
#     # logger.info(f"[检索系统] 开始初始化检索系统")
#
#     # # 初始化 ES 检索器
#     # logger.debug(f"[检索系统] 初始化ES检索器")
#     # es_op = ElasticsearchOperation()
#
#     # # 初始化 BM25 检索器
#     # logger.debug(f"[检索系统] 初始化BM25检索器")
#     # bm25_retriever = BM25Retriever(es_retriever=es_op)
#
#     # 初始化milvus 检索器
#     logger.debug(f"[检索系统] 创建Milvus向量存储")
#     # 使用自定义的 FlatCollectionManager
#     flat_manager = FlatCollectionManager(collection_name=GlobalConfig.MILVUS_CONFIG["collection_name"])
#
#     logger.info(f"[检索系统] 初始化完成")
#
#     # 返回向量检索器实例
#     # return VectorRetriever(flat_manager),bm25_retriever
#     return VectorRetriever(flat_manager)


def merge_search_results(
        vector_results: dict[str, float],
        bm25_results: dict[str, float]
) -> dict[str, float]:
    """合并向量检索和 BM25 检索结果
    
    Args:
        vector_results: 向量检索结果(seg_id, score)
        bm25_results: BM25 检索结果
        
    Returns:
        dict[str, float]: 合并后的结果字典(seg_id, score)
    """
    merged_results = OrderedDict()
    seen_ids = set()

    # 合并结果保持顺序
    for seg_id, score in vector_results.items():
        if seg_id not in seen_ids:
            merged_results[seg_id] = score
            seen_ids.add(seg_id)

    for seg_id, score in bm25_results.items():
        if seg_id not in seen_ids:
            merged_results[seg_id] = score
            seen_ids.add(seg_id)

    return merged_results


class HybridRetriever(BaseRetriever):
    """混合检索器，结合向量检索和 ES BM25 检索"""

    def __init__(self, **kwargs):
        """初始化混合检索器

        Args:
            **kwargs: 传递给父类的参数
        """
        # 调用父类初始化
        super().__init__(**kwargs)

        # 初始化 FLAT Collection 管理器
        self._flat_manager = FlatCollectionManager(
            collection_name=GlobalConfig.MILVUS_CONFIG["collection_name"]
        )

        # 初始化向量检索器 和 BM25检索器
        # self._vector_retriever,self._bm25_retriever = init_retrievers()
        # 初始化 Milvus 检索器
        self._milvus_retriever = VectorRetriever(self._flat_manager)

    def _get_relevant_documents(self, query: str, *, callbacks=None,
                                tags=None, metadata=None, **kwargs) -> List[Document]:
        """重写父类方法 _get_relevant_documents
        
        Args:
            query: 用户查询
            callbacks: 回调函数
            tags: 标签
            metadata: 元数据
            **kwargs: 其他参数
            
        Returns:
            List[Document]: 相关文档列表
        """
        # 调用 search_documents 方法，但只返回 Document 列表
        results = self.search_documents(
            query=query,
            permission_ids=kwargs.get("permission_ids"),
            k=kwargs.get("k", 20),
            top_k=kwargs.get("top_k", 10),
            chunk_op=kwargs.get("chunk_op")
        )

        # 确保返回的是 Document 列表
        if isinstance(results, list):
            return results
        else:
            return []

    def invoke(self, user_input: str, **kwargs) -> List[Document]:
        """重写父类方法 BaseRetriever 的方法(0.1.46 新版本统一接口)

        Args:
            user_input: 用户查询
            **kwargs: 其他参数
            
        Returns:
            List[Document]: 相关文档列表，分数存储在 metadata 中
        """
        permission_ids: Union[str, List[str]] = kwargs.get("permission_ids")
        k = kwargs.get("k", 20)
        top_k = kwargs.get("top_k", 5)
        chunk_op = kwargs.get("chunk_op")

        return self.search_documents(
            user_input,
            permission_ids=permission_ids,
            k=k,
            top_k=top_k,
            chunk_op=chunk_op,
        )

    def search_documents(self, query: str, *, cleaned_dep_ids: List[str] = None, k: int = 20,
                         top_k: int = 10, chunk_op=None, request_id: str = None) -> List[Document]:
        """自定义搜索文档方法

        Args:
            query: 用户查询
            cleaned_dep_ids: 清洗后的权限 ID 列表
            k: 初始检索数量
            top_k: 最终返回结果数量
            chunk_op: ChunkOperation实例
            request_id: 请求 ID

        Returns:
            List[Document]: 相关文档列表，分数存储在 metadata 中
        """
        try:
            logger.info(f"[混合检索] request_id={request_id}, 开始检索, 查询长度: {len(query)}, 权限ID: {cleaned_dep_ids}, k: {k}, top_k: {top_k}")


            # 根据权限 ID 获取到 doc_ids


            # 向量检索
            vector_results: dict[str, float] = self._vector_retriever.search(
                query=query,
                permission_ids=permission_ids,
                k=k,
            )

            # BM25检索
            bm25_results: dict[str, float] = self._bm25_retriever.search(
                query=query,
                k=k,
            )

            # 合并结果
            merged_results: dict[str, float] = merge_search_results(vector_results, bm25_results)
            logger.debug(
                f"[混合检索] 结果合并完成, 向量结果={len(vector_results)}条, BM25结果={len(bm25_results)}条, 合并后={len(merged_results)}条")

            # 如果没有检索到结果，直接返回空列表
            if not merged_results:
                logger.info(f"[混合检索] 没有检索到结果")
                return []

            # 从 mysql 获取所需的原文内容(已过滤权限)
            seg_ids = list(merged_results.keys())
            logger.debug(f"[混合检索] 开始原文提取, 片段数量={len(seg_ids)}, 权限ID={permission_ids}")

            mysql_records = []

            if chunk_op is not None:
                mysql_records: List[Dict[str, Any]] = chunk_op.get_segment_contents(
                    seg_ids=seg_ids,
                    permission_ids=permission_ids,  # 确保传递权限ID
                )
            else:
                with ChunkOperation() as chunk_op:
                    mysql_records: List[Dict[str, Any]] = chunk_op.get_segment_contents(
                        seg_ids=seg_ids,
                        permission_ids=permission_ids,  # 确保传递权限ID
                    )
            logger.debug(f"[混合检索] 原文提取完成, 权限过滤后返回={len(mysql_records)}条结果")

            # 构建 Document 对象
            rerank_input = []
            for record in mysql_records:
                # 构建记录信息
                doc = Document(
                    page_content=record.get("seg_content", ""),
                    metadata={**record}
                )
                rerank_input.append(doc)

            logger.debug(f"[混合检索] 构建Document对象完成, 共={len(rerank_input)}条")

            # 重排序
            # reranked_result = []
            # if rerank_input:
            #     scores: List[float] = rerank_manager.rerank(
            #         query=query,
            #         passages=[doc.page_content for doc in rerank_input]
            #     )
            #
            #     # 将分数存储到 Document 的 metadata 中
            #     for doc, score in zip(rerank_input, scores):
            #         doc.metadata['rerank_score'] = score
            #         reranked_result.append(doc)
            #
            #     # 根据rerank分数排序
            #     reranked_result.sort(key=lambda x: x.metadata.get("rerank_score", 0), reverse=True)
            #
            #     # 使用一阶差分算法进行文档过滤
            #     reranked_result = self.detect_cliff_and_filter(reranked_result, top_k=top_k)

            # 使用自定义重排序方法（包含相关性过滤）
            reranked_result = self._custom_rerank(query, rerank_input, top_k)

            logger.info(f"[混合检索] 检索完成, 返回={len(reranked_result)}条结果")

            # 提取 Document 列表
            return reranked_result

        except Exception as error:
            logger.error(f"[混合检索失败] error_msg={str(error)}")
            log_exception("混合检索异常", exc=error)
            return []

    @staticmethod
    def normalize_score(scores: List[float]) -> List[float]:
        """将得分列表归一化后(线性回归)返回"""
        if scores and len(scores) <= 1:
            return scores
        min_score, max_score = min(scores), max(scores)
        # 大于 1 * 10^-5 时,计算归一化才有意义
        if max_score - min_score > 1e-5:
            norm_scores = [(s - min_score) / (max_score - min_score) for s in scores]
        else:
            # 所有分数基本相等, 没有归一化的意义
            norm_scores = [0.0 for _ in scores]
        return norm_scores

    @staticmethod
    def detect_cliff_and_filter(reranked_result: List[Document],
                                top_k: int = 10
                                ) -> List[Document]:
        """一阶差分算法, 自动检测重排分数的断崖点，并据此过滤文档。
        Args:
            reranked_result: 排名后的 rerank 列表, 分数在 Document.metadata 中
            top_k: 最大保留文档数，None 表示不限。

        Returns:
            List[Document]: 过滤后的文档列表（保留到断崖点前）。
        """
        # 提取分数
        sorted_scores = [doc.metadata.get('rerank_score', 0) for doc in reranked_result]

        # # 将文档和对应分数打包，并按分数从高到低排序
        # sorted_scores = [s for _, s in reranked_result]  # 仅保留排序后的分数

        # 无法计算差值时,直接截断前top_k个
        if len(reranked_result) <= 1:
            return reranked_result[:top_k]

        # 计算一阶差分：相邻两个分数之间的“下降值”
        deltas = [sorted_scores[i + 1] - sorted_scores[i] for i in range(len(sorted_scores) - 1)]

        cliff_index: Optional[int] = None

        # 找出“下降最大”的位置（断崖点）
        min_delta = min(deltas)
        for idx, delta in enumerate(deltas):
            if delta == min_delta:
                cliff_index = idx + 1
                break

        # 若设置了 top_k，则取 min(cliff_index, top_k)
        if top_k is not None:
            cliff_index = min(cliff_index, top_k)

        # 返回断崖前的文档列表
        return reranked_result[:cliff_index]

    def _custom_rerank(self, query: str, results: List[Document], top_k: int = 10) -> List[Document]:
        """自定义重排序 - 增加相关性过滤

        Args:
            query: 查询文本
            results: 检索结果
            top_k: 最终返回数量

        Returns:
            List[Document]: 重排序并过滤后的结果
        """
        try:
            reranked_result = []
            if results:
                # 步骤1: 重排序
                scores: List[float] = rerank_manager.rerank(
                    query=query,
                    passages=[doc.page_content for doc in results]
                )

                # 步骤2: 将分数存储到 Document 的 metadata 中
                for doc, score in zip(results, scores):
                    doc.metadata['rerank_score'] = score
                    reranked_result.append(doc)

                # 步骤3: 根据rerank分数排序
                reranked_result.sort(key=lambda x: x.metadata.get("rerank_score", 0), reverse=True)

                # 修复格式化字符串问题
                if reranked_result:
                    highest_score = reranked_result[0].metadata.get('rerank_score', 0)
                    lowest_score = reranked_result[-1].metadata.get('rerank_score', 0)
                    logger.debug(
                        f"[重排序] 完成, 原始结果数={len(reranked_result)}, 分数范围=[{lowest_score:.4f}, {highest_score:.4f}]")
                else:
                    logger.debug(f"[重排序] 完成, 原始结果数=0")

                # 步骤4: 相关性过滤 - 过滤掉相关性太低的文档
                relevance_threshold = -5  # 相关性阈值，可根据实际效果调整
                filtered_results = []
                for doc in reranked_result:
                    score = doc.metadata.get("rerank_score", 0)
                    if score >= relevance_threshold:
                        filtered_results.append(doc)
                    else:
                        logger.debug(
                            f"[相关性过滤] 过滤低相关性文档, score={score:.4f}, seg_id={doc.metadata.get('seg_id', 'unknown')}")

                logger.info(
                    f"[相关性过滤] 完成, 过滤前={len(reranked_result)}, 过滤后={len(filtered_results)}, 阈值={relevance_threshold}")

                # 步骤5: 如果过滤后结果为空，返回空列表
                if not filtered_results:
                    logger.warning(f"[相关性过滤] 所有文档相关性都低于阈值{relevance_threshold}，返回空结果")
                    return []

                # 步骤6: 使用一阶差分算法进行梯度截断
                final_results = self.detect_cliff_and_filter(filtered_results, top_k=top_k)

                logger.info(
                    f"[重排序] 完成, 相关性过滤后={len(filtered_results)}, 梯度截断后={len(final_results)}条结果")
                return final_results

            else:
                logger.info(f"[重排序] 无输入结果，返回空列表")
                return []

        except Exception as error:
            logger.error(f"[重排序失败] error_msg={str(error)}")
            return []





# vector_retriever, bm25_retriever = init_retrievers()
hybrid_retriever = HybridRetriever()

if __name__ == '__main__':
    query = "发行人"
    vector_retriever, bm25_retriever = init_retrievers()
    hyper_ob = HybridRetriever()
    result = hyper_ob.get_relevant_documents(query, permission_ids="1")
    print(result)
