"""混合检索模块"""
from typing import List, Any, Dict, OrderedDict, Optional, Union

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain.schema import BaseRetriever
from langchain_milvus import Milvus

from config.global_config import GlobalConfig
from databases.elasticsearch.operations import ElasticsearchOperation
from utils.log_utils import logger
from databases.mysql.operations import ChunkOperation
from core.rag.retrieval.vector_retriever import VectorRetriever
from core.rag.retrieval.bm25_retriever import BM25Retriever
from utils.llm_utils import rerank_manager


def init_retrievers():
    """初始化检索器
    
    Returns:
        tuple: (vector_retriever, bm25_retriever)
    """
    logger.info("开始初始化检索系统...")

    # 初始化 ES 检索器
    logger.info("初始化 ES 检索器...")
    es_op = ElasticsearchOperation()

    # 初始化 BM25 检索器
    logger.info("初始化 BM25 检索器...")
    bm25_retriever = BM25Retriever(es_retriever=es_op)

    # 初始化 embeddings
    logger.info("初始化 embeddings 模型...")
    embeddings = HuggingFaceEmbeddings(
        model_name=GlobalConfig.MODEL_PATHS["embedding"],
        model_kwargs={'device': GlobalConfig.DEVICE}
    )

    # 创建 Milvus 向量存储
    logger.info("创建 Milvus 向量存储...")
    vectorstore = Milvus(
        embedding_function=embeddings,
        collection_name=GlobalConfig.MILVUS_CONFIG["collection_name"],
        connection_args={
            "uri": GlobalConfig.MILVUS_CONFIG["uri"],
            "token": GlobalConfig.MILVUS_CONFIG["token"],
            "db_name": GlobalConfig.MILVUS_CONFIG["db_name"]
        },
        search_params={
            "metric_type": GlobalConfig.MILVUS_CONFIG["index_params"]["metric_type"],
            "params": GlobalConfig.MILVUS_CONFIG["search_params"]
        },
        text_field="seg_content"
    )

    logger.info("检索系统初始化完成")

    # 返回向量检索器实例
    return VectorRetriever(vectorstore), bm25_retriever


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

    def __init__(self, vector_retriever: VectorRetriever, bm25_retriever: BM25Retriever):
        """初始化混合检索器
        
        Args:
            vector_retriever: 向量检索器实例
            bm25_retriever: BM25检索器实例
        """
        super().__init__()
        self._vector_retriever = vector_retriever
        self._bm25_retriever = bm25_retriever

    def get_relevant_documents(self, query: str, *, callbacks=None, tags=None, metadata=None, **kwargs) -> List[
        Document]:
        """实现 BaseRetriever 的方法

        Args:
            query: 用户查询
            callbacks: 回调函数
            tags: 标签
            metadata: 元数据

        Returns:
            List[Document]: 相关文档列表
        """
        # 从 kwargs 中获取参数，如果没有则使用默认值
        permission_ids = kwargs.get("permission_ids")
        k = kwargs.get("k", 20)
        top_k = kwargs.get("top_k", 10)
        chunk_op = kwargs.get("chunk_op")

        return self.search_documents(query, permission_ids=permission_ids, k=k, top_k=top_k, chunk_op=chunk_op)

    def search_documents(self, query: str, *, permission_ids: str = None, k: int = 20, top_k: int = 5,
                         chunk_op=None) -> Union[List[Document], None]:
        """自定义搜索文档方法

        Args:
            query: 用户查询
            permission_ids: 权限ID列表
            k: 初始检索数量
            top_k: 最终返回结果数量
            chunk_op: ChunkOperation实例

        Returns:
            List[Document]: 相关文档列表
        """
        try:
            logger.info(f"[混合检索] 开始检索,查询: {query}, 权限ID: {permission_ids}, k: {k}, top_k: {top_k}")

            # 向量检索
            vector_results: dict[str, float] = self._vector_retriever.search(
                query=query,
                permission_ids=permission_ids,
                k=k,
            )

            # BM25检索
            bm25_results: dict[str, float] = self._bm25_retriever.search(
                query=query,
                permission_ids=permission_ids,
                k=k,
            )

            # 合并结果
            merged_results: dict[str, float] = merge_search_results(vector_results, bm25_results)
            logger.info(f"[混合检索] 合并结果完成,共 {len(merged_results)} 条")

            # 如果没有检索到结果，直接返回空列表
            if not merged_results:
                logger.info(f"[混合检索] 没有检索到结果，返回空列表")
                return None

            # 从 mysql 获取所需的原文内容
            seg_ids = list(merged_results.keys())
            logger.info(f"[混合检索] 从MySQL获取原文内容,seg_ids数量: {len(seg_ids)}, 权限ID: {permission_ids}")
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
            logger.info(f"[混合检索] 从MySQL获取到 {len(mysql_records)} 条原文记录")

            # 再次对mysql获取到的原文内容进行过滤，避免遗漏
            rerank_input = []
            filtered_count = 0
            for record in mysql_records:
                # 处理记录中的权限 ID
                if permission_ids:
                    # 获取记录中的权限ID
                    record_permission_ids = record.get("permission_ids", "")

                    # 如果记录有权限ID且与用户权限不匹配，则跳过
                    if record_permission_ids and str(record_permission_ids) != str(permission_ids):
                        logger.info(
                            f"权限过滤: 跳过文档 {record.get('seg_id')}, 权限不匹配 (需要: {permission_ids}, 实际: {record_permission_ids})")
                        filtered_count += 1
                        continue

                # 构建记录信息
                doc = Document(
                    page_content=record.get("seg_content", ""),
                    metadata={
                        **record
                    }
                )
                rerank_input.append(doc)

            logger.info(f"[混合检索] 权限过滤后剩余 {len(rerank_input)} 条结果 (过滤掉 {filtered_count} 条)")

            # 重排序
            reranked_result = []
            if rerank_input:
                scores: List[float] = rerank_manager.rerank(
                    query=query,
                    passages=[doc.page_content for doc in rerank_input]
                )

                # 将分数与文档配对
                reranked_result = [
                    (doc, score) for doc, score in zip(rerank_input, scores) if score > -5.0
                ]

                # 按分数排序并提取前 tok_k 个
                reranked_result.sort(key=lambda x: x[1], reverse=True)
                # 使用一阶差分算法进行文档过滤
                reranked_result = self.detect_cliff_and_filter(reranked_result, top_k=top_k)

            logger.info(f"[重排序] 重排过滤完成, 返回 {len(reranked_result)} 条结果")

            # 提取文档列表
            return reranked_result

        except Exception as error:
            logger.error(f"[混合检索] 检索失败: {str(error)}")
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
    def detect_cliff_and_filter(reranked_result: List[tuple[Document, float]],
                                top_k: int = 10
                                ) -> list[tuple[Document, float]]:
        """一阶差分算法, 自动检测重排分数的断崖点，并据此过滤文档。
        Args:
            reranked_result: 排名后的 rerank 列表,包括文档和得分
            top_k: 最大保留文档数，None 表示不限。

        Returns:
            List[Document]: 过滤后的文档和分数列表（保留到断崖点前）。
        """
        # 将文档和对应分数打包，并按分数从高到低排序
        sorted_scores = [s for _, s in reranked_result]  # 仅保留排序后的分数

        # 计算一阶差分：相邻两个分数之间的“下降值”
        deltas = [sorted_scores[i + 1] - sorted_scores[i] for i in range(len(sorted_scores) - 1)]

        # 如果没有差值（说明文档少于2个），直接返回全部文档
        if not deltas:
            return reranked_result

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


vector_retriever, bm25_retriever = init_retrievers()
hybrid_retriever = HybridRetriever(vector_retriever, bm25_retriever)

if __name__ == '__main__':
    query = "发行人"
    vector_retriever, bm25_retriever = init_retrievers()
    hyper_ob = HybridRetriever(vector_retriever, bm25_retriever)
    result = hyper_ob.get_relevant_documents(query, permission_ids="1")
    print(result)
