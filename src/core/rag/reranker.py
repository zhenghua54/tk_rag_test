"""重排序模块"""
from typing import List, Tuple, Any
from sentence_transformers import CrossEncoder

from config.settings import Config
from src.utils.common.logger import logger
from langchain_core.documents import Document


def init_rerank_model() -> CrossEncoder:
    """初始化重排序模型
    
    Returns:
        CrossEncoder: 重排序模型实例
    """
    return CrossEncoder(Config.MODEL_PATHS["rerank"], device=Config.DEVICE)


def rerank_results(query: str, merged_results: List[Document], top_k: int = 50) -> List[Tuple[Document, float]]:
    """使用 BGE-Rerank 模型进行重排序
    
    Args:
        query (str): 用户查询文本
        merged_results (List[Document]): 检索结果文档列表
        top_k (int): 返回结果数量
        
    Returns:
        List[Tuple[Document, float]]: 重排序后的结果列表
    """
    logger.info(f"开始重排序,输入结果数量: {len(merged_results)}, top_k: {top_k}")

    # 初始化重排序模型
    logger.debug(f"初始化重排序模型...")
    try:
        reranker = init_rerank_model()
    except Exception as e:
        logger.error(f"重排序模型初始化失败: {str(e)}")
        # 如果初始化失败，返回原始结果并分配默认分数
        return [(doc, 1.0) for doc in merged_results[:top_k]]

    # 准备重排序数据
    pairs = []
    for doc in merged_results:
        doc_type = doc.metadata.get("seg_type")
        if doc_type == "table":
            # 对于表格，使用摘要进行重排序
            content = doc.metadata.get("seg_caption", doc.page_content)
        elif doc_type == "image":
            # 对于图片，使用标题进行重排序
            content = doc.metadata.get("seg_caption", doc.page_content)
        else:
            # 对于文本，直接使用内容
            content = doc.page_content
        pairs.append([query, content])

    # 分批处理计算重排序分数,避免批处理大小问题
    batch_size = 1
    rerank_scores = []
    # 分批计算重排序分数
    for i in range(0, len(pairs), batch_size):
        batch_pairs = pairs[i:i + batch_size]
        batch_scores = reranker.predict(batch_pairs)
        rerank_scores.extend(batch_scores if isinstance(batch_scores, list) else [batch_scores])

    # 将重排序分数更新到文档元数据中
    for i, (doc, score) in enumerate(zip(merged_results, rerank_scores)):
        # 保留原始检索分数
        original_score = doc.metadata.get("score", 0.0)
        # 更新为重排序分数
        doc.metadata["score"] = float(score)
        # 可选：添加原始分数字段
        doc.metadata["original_score"] = original_score

    # 将重排序分数和原始结果结合
    reranked_results = [(doc, float(score)) for doc, score in zip(merged_results, rerank_scores)]

    # 按重排序分数排序
    reranked_results.sort(key=lambda x: x[1], reverse=True)

    # 获取前 top_k 个结果
    final_results = reranked_results[:top_k]
    logger.info(f"重排序完成,返回 {len(final_results)} 条结果")

    # 返回前 top_k 个结果
    return final_results


if __name__ == '__main__':
    import sys

    # 测试重排序功能
    test_query = "测试查询"
    test_docs = [
        Document(page_content="测试文档1", metadata={"seg_type": "text"}),
        Document(page_content="测试文档2", metadata={"seg_type": "text"}),
        Document(page_content="测试文档3", metadata={"seg_type": "text"})
    ]
    
    results = rerank_results(test_query, test_docs, top_k=2)
    for doc, score in results:
        print(f"分数: {score:.4f}, 内容: {doc.page_content}") 