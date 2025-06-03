"""使用 langchain 框架处理用户 query"""
import psutil
import os
from typing import List, Tuple, Any

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_milvus import Milvus
from sentence_transformers import CrossEncoder

# 项目配置
from config.settings import Config, logger
from src.database.milvus.connection import MilvusDB
from src.database.mysql.operations import ChunkOperation


def log_memory_usage():
    """记录当前内存使用情况"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    logger.info(f"内存使用: {memory_info.rss / 1024 / 1024:.2f} MB")


# def init_bm25_retriever(db: MilvusDB, batch_size: int = 1000):
#     """初始化 BM25 检索器，使用分批加载
    
#     Args:
#         batch_size: 每批处理的文档数量
#     """
#     logger.info(f"开始初始化 BM25 检索器...")
    
#     try:
#         # 创建空的 BM25 检索器
#         bm25_retriever = BM25Retriever.from_documents([])
        
#         # 分批加载数据
#         with ChunkOperation() as chunk_op:
#             # 获取总记录数
#             total_count = chunk_op.get_count()
            
#             # 分批处理
#             for offset in range(0, total_count, batch_size):
#                 # 获取一批数据
#                 chunks = chunk_op.select_records(
#                     fields=["segment_text", "segment_id", "doc_id", "parent_segment_id"],
#                     limit=batch_size,
#                     offset=offset
#                 )
                
#                 # 构建文档列表
#                 batch_docs = []
#                 for chunk in chunks:
#                     metadata = {
#                         "segment_id": chunk["segment_id"],
#                         "doc_id": chunk["doc_id"],
#                         "parent_segment_id": chunk["parent_segment_id"],
#                     }
#                     doc = Document(
#                         page_content=chunk["segment_text"],
#                         metadata=metadata
#                     )
#                     batch_docs.append(doc)
                
#                 # 更新 BM25 检索器
#                 bm25_retriever.add_documents(batch_docs)
                
#                 # 清理内存
#                 del batch_docs
                
#                 logger.info(f"已处理 {min(offset + batch_size, total_count)}/{total_count} 条记录")
        
#         logger.info(f"BM25 检索器初始化完成")
#         return bm25_retriever
        
#     except Exception as e:
#         logger.error(f"初始化 BM25 检索器失败: {str(e)}")
#         return BM25Retriever.from_documents([Document(page_content="初始化失败")])


def get_hybrid_search_results(query: str, vectorstore: Milvus, bm25_retriever: BM25Retriever, k: int = 50) -> List[Tuple[Any, float]]:
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
    vector_results = vectorstore.similarity_search_with_score(
        query=query, 
        k=k, 
        filter={"principal_ids": ["1"]}
    )
    # 1.1 获取检索到的文档的相似度分数
    vector_results_score_list = [result[-1] for result in vector_results]
    logger.info(f"向量检索完成,获取到 {len(vector_results)} 条结果, 文档分数: {vector_results_score_list}")

    # 2. BM25 检索
    logger.info(f"开始 BM25 检索...")
    bm25_docs = []
    try:
        # 使用 BM25 检索器对查询进行检索
        bm25_docs = bm25_retriever.invoke(query, k=k)
        logger.info(f"BM25 检索完成,获取到 {len(bm25_docs)} 条结果")
    except Exception as e:
        logger.error(f"BM25 检索失败: {str(e)}")
        bm25_docs = []

    # 3. 合并结果并去重
    logger.info(f"开始合并并去重结果...")
    seen_contents = set()
    merged_results = []

    # 3.1 添加向量检索结果
    for doc, score in vector_results:
        segment_id = doc.metadata.get("segment_id")
        if segment_id not in seen_contents:
            # 根据类型处理元数据
            doc_type = doc.metadata.get("type")

            # 处理通用字段
            doc.metadata.update({
                "document_name": doc.metadata.get("document_name"),
                "page_idx": doc.metadata.get("page_idx"),
                "principal_ids": doc.metadata.get("principal_ids"),
                "create_time": doc.metadata.get("create_time"),
                "update_time": doc.metadata.get("update_time"),
                "source_type": "vector"
            })
            
            # 根据特定类型处理特定字段
            if doc_type == "text":
                # 处理文本类型
                doc.metadata["summary_text"] = doc.metadata.get("summary_text")

            if doc_type == "table":
                # 处理表格类型
                if "metadata" in doc.metadata:
                    metadata = doc.metadata["metadata"]
                    if "raw_table_segment_id" in metadata:
                        # 子表，需要关联母表信息
                        doc.metadata["parent_table"] = metadata["raw_table_segment_id"]
                        # 子表只补充基本元数据信息，不包含img_path、caption和footnote字段
                        doc.metadata.update({
                            "table_raw": metadata.get("table_raw"),
                            "table_token_length": metadata.get("table_token_length")
                        })
                    else:
                        # 母表包含所有元数据信息
                        doc.metadata.update({
                            "table_raw": metadata.get("table_raw"),
                            "table_token_length": metadata.get("table_token_length"),
                            "img_path": metadata.get("img_path"),
                            "caption": metadata.get("caption"),
                            "footnote": metadata.get("footnote")
                        })
            elif doc_type == "image":
                # 处理图片类型
                if "metadata" in doc.metadata:
                    metadata = doc.metadata["metadata"]
                    doc.metadata.update({
                        "img_path": metadata.get("img_path"),
                        "caption": metadata.get("caption"),
                        "footnote": metadata.get("footnote")
                    })
            merged_results.append((doc, score))
            seen_contents.add(segment_id)

    # 3.2 添加 BM25 检索结果
    for doc in bm25_docs:
        segment_id = doc.metadata.get("segment_id")
        if segment_id not in seen_contents:
            # 从 MySQL 获取完整信息
            with ChunkOperation() as chunk_op:
                chunk_info = chunk_op.select_record(
                    fields=["segment_id",  "doc_id", "parent_segment_id"],
                    conditions={"segment_id": segment_id}  
                )
                if chunk_info:
                    # 补充元数据信息
                    doc.metadata.update(chunk_info[0])
            
            doc.metadata["source_type"] = "bm25"
            merged_results.append((doc, 0.5))
            seen_contents.add(segment_id)

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
    pairs = []
    for doc, _ in merged_results:
        doc_type = doc.metadata.get("type")
        if doc_type == "table":
            # 对于表格，使用摘要进行重排序
            content = doc.metadata.get("summary_text", doc.page_content)
        elif doc_type == "image":
            # 对于图片，使用标题进行重排序
            content = doc.metadata.get("caption", doc.page_content)
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
