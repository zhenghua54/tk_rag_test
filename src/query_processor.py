"""使用 langchain 框架处理用户 query"""

from typing import List, Tuple, Any

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_milvus import Milvus
from sentence_transformers import CrossEncoder

# 项目配置
from config import Config, logger
from src.utils.database.milvus_connect import MilvusDB


def init_bm25_retriever(db: MilvusDB):
    """初始化 BM25 检索器,从 Milvus 的 text_chunk 字段中获取所有文档内容
        
    Returns:
        初始化好的 BM25 检索器
    """
    logger.info(f"开始初始化 BM25 检索器...")

    try:
        # 从 Milvus 中获取所有文档内容
        text_chunks = db.get_all_text_chunks()
        all_docs = [Document(page_content=chunk) for chunk in text_chunks]

        bm25_retriever = BM25Retriever.from_documents(all_docs)
        logger.info(f"BM25 检索器初始化完成, 包含 {len(all_docs)} 条文档")
        return bm25_retriever
    except Exception as e:
        logger.error(f"初始化 BM25 检索器失败: {str(e)}")
        return BM25Retriever.from_documents([Document(page_content="初始化失败")])


def get_hybrid_search_results(query: str, vectorstore: Milvus, bm25_retriever: BM25Retriever, k: int = 50) -> List[
    Tuple[Any, float]]:
    """使用 Langchain 框架实现混合检索(向量检索 + BM25)获取结果
    
    Args:
        query (str): 用户查询文本
        k (int): 返回结果数量
        
    Returns:
        检索结果列表,每个元素为 (文档,相似度分数) 的元祖
    """
    logger.info(f"开始混合检索,查询: {query}, k: {k}")

    # 1. 向量检索
    logger.info(f"开始向量检索...")
    vector_results = vectorstore.similarity_search_with_score(query=query, k=k, filter={"partment": "",  # 可以根据需要添加过滤条件
                                                                                        "role": ""  # 可以根据需要添加过滤条件
                                                                                        })
    # 1.1 获取检索到的文档的相似度分数
    vector_results_score_list = [result[-1] for result in vector_results]
    logger.info(f"向量检索完成,获取到 {len(vector_results)} 条结果, 文档分数: {vector_results_score_list}")

    # 2. BM25 检索(仅召回)
    logger.info(f"开始 BM25 检索...")
    bm25_docs = []
    try:
        # 只获取文档,不计算分数
        bm25_docs = bm25_retriever.invoke(query, k=k)
    except Exception as e:
        logger.error(f"BM25 检索失败: {str(e)}")
        bm25_docs = []

    logger.info(f"BM25 检索完成,获取到 {len(bm25_docs)} 条结果")

    # 3. 合并结果并去重
    logger.info(f"开始合并并去重结果...")
    seen_contents = set()
    merged_results = []

    # 3.1 添加向量检索结果
    for doc, score in vector_results:
        content = doc.page_content
        if content not in seen_contents:
            # 添加来源标记到元数据
            doc.metadata["source_type"] = "vector"
            merged_results.append((doc, score))
            seen_contents.add(content)

    # 3.2 添加 BM25 检索结果(使用默认分数 0.5,若需要计算则需要定义规则,计算分数)
    for doc in bm25_docs:
        content = doc.page_content
        if content not in seen_contents:
            # 添加来源标记到元数据
            doc.metadata["source_type"] = "bm25"
            # 使用默认分数 0.5,后续通过 rerank 排序后会重新计算分数
            merged_results.append((doc, 0.5))
            seen_contents.add(content)

    logger.info(f"混合检索完成,合并后共有 {len(merged_results)} 条结果")
    return merged_results


def rerank_results(query: str, merged_results: List[Tuple[Any, float]], top_k: int = 50) -> List[Tuple[Any, float]]:
    """使用 BGE-Rerank 模型进行重排序
    
    Args:
        query (str): 用户查询文本
        merged_results (List[Tuple[Any, float]]): 检索结果列表
        k (int): 返回结果数量
        
    Returns:
        重排序后的结果列表
    """
    logger.info(f"开始重排序,输入结果数量: {len(merged_results)}, top_k: {top_k}")

    # 初始化重排序模型
    logger.info(f"初始化重排序模型...")
    reranker = CrossEncoder(Config.MODEL_PATHS["rerank"], device=Config.DEVICE)

    # 准备重排序数据
    pairs = [[query, doc.page_content] for doc, _ in merged_results]

    # 分批处理计算重排序分数,避免批处理大小问题
    batch_size = 1
    rerank_scores = []
    # 分批计算重排序分数
    for i in range(0, len(pairs), batch_size):
        batch_pairs = pairs[i:i + batch_size]
        batch_scores = reranker.predict(batch_pairs)
        rerank_scores.extend(batch_scores)

    # 将重排序分数和原始结果结合
    reranked_results = [(doc, float(score)) for (doc, _), score in zip(merged_results, rerank_scores)]

    # 按重排序分数排序
    reranked_results.sort(key=lambda x: x[1], reverse=True)

    # 获取前 top_k 个结果
    final_results = reranked_results[:top_k]
    logger.info(f"重排序完成,返回 {len(final_results)} 条结果")

    # 返回前 top_k 个结果
    return final_results


def search_documents(query: str, vectorstore: Milvus, bm25_retriever: BM25Retriever, k: int = 50, top_k: int = 10) -> \
        List[Tuple[Any, float]]:
    """完整的检索流程
    
    Args:
        query: 查询文本
        vectorstore: Milvus 向量存储实例
        bm25_retriever: BM25 检索器实例
        k: 初始检索数量
        top_k: 最终返回结果数量
        
    Returns:
        检索结果列表
    """
    logger.info(f"开始文档检索流程,查询: {query}, k: {k}, top_k: {top_k}")

    # 1. 混合检索
    merged_results = get_hybrid_search_results(query, vectorstore, bm25_retriever, k=k)

    # 2. 重排序
    final_results = rerank_results(query, merged_results, top_k=top_k)

    logger.info(f"文档检索流程完成")
    return final_results


def main(user_query: str, vectorstore: Milvus, bm25_retriever: BM25Retriever):
    """主函数
    
    Args:
        vectorstore: Milvus 向量存储实例
        bm25_retriever: BM25 检索器实例
    """

    # 执行检索
    results = search_documents(query=user_query, vectorstore=vectorstore, bm25_retriever=bm25_retriever, k=50, top_k=5)

    # 打印检索结果
    logger.info(f"开始打印检索结果:")
    for i, (doc, score) in enumerate(results):
        logger.info(f"\n结果 {i + 1}: 分数: {score:.4f}")
        logger.debug(f"文档内容: {doc.page_content[:200]}...")
        logger.debug(f"元数据: {doc.metadata}")


if __name__ == "__main__":
    logger.info("初始化检索系统...")

    # 假设用户的提问
    user_query = "天宽是谁?"

    # 初始化数据库连接
    db = MilvusDB()
    db.init_database()
    # 初始化 embeddings
    logger.info("初始化 embeddings 模型...")
    embeddings = HuggingFaceEmbeddings(model_name=Config.MODEL_PATHS["embedding"],
                                       model_kwargs={'device': Config.DEVICE})
    # 创建 Milvus 向量存储
    logger.debug(f"创建 Milvus 向量存储...")
    vectorstore = Milvus(
        embedding_function=embeddings,
        collection_name=Config.MILVUS_CONFIG["collection_name"],
        connection_args={
            "uri": Config.MILVUS_CONFIG["uri"],
            "token": Config.MILVUS_CONFIG["token"],
            "db_name": Config.MILVUS_CONFIG["db_name"]
        },
        search_params={
            "metric_type": Config.MILVUS_CONFIG["index_params"]["metric_type"],
            "params": Config.MILVUS_CONFIG["search_params"]
        },
        text_field="text_chunk", )
    logger.info("Milvus 向量存储初始化完成")

    bm25_retriever = init_bm25_retriever(db)

    # 执行主函数
    main(user_query, vectorstore, bm25_retriever)

    # print(dir(bm25_retriever))
    # print(db.collection.schema)
    # print(Config.MODEL_PATHS["rerank"]) # /Users/jason/models/BAAI/bge-reranker-v2-m3

    # user_query = "发行人在行业中的竞争情况是什么?"
    # vector_results = vectorstore.similarity_search_with_score(query=user_query, k=1000, )

    # user_query = "发行人在行业中的竞争情况是什么?"  # all_docs_with_scores = vectorstore.similarity_search_with_score(
    #     query=user_query,
    #     k=1000  ,
    # )  # for i,(doc,score) in enumerate(all_docs_with_scores):
    #     if score > 0.7:
    #         print(f"文档 {i+1} 内容: {doc.page_content[:200]}...")
    #         print(f"文档 {i+1} 相似度分数: {score:.4f}\n")
