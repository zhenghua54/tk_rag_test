"""向量检索模块"""
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


from typing import List, Tuple
from langchain_core.documents import Document
from langchain_milvus import Milvus
from src.utils.common.logger import logger
from src.core.rag.retrieval.text_retriever import get_seg_content
import numpy as np


class VectorRetriever:
    """向量检索器类"""
    
    def __init__(self, vectorstore: Milvus):
        """初始化向量检索器
        
        Args:
            vectorstore: Milvus 向量存储实例
        """
        self._vectorstore = vectorstore

    def search(self, query: str, k: int = 5, chunk_op=None) -> List[Tuple[Document, float]]:
        """执行 milvus 向量检索
        
        Args:
            query: 查询文本
            k: 检索数量
            chunk_op: Mysql 的 ChunkOperation实例
            
        Returns:
            List[Tuple[Document, float]]: 检索结果列表
        """
        logger.info(f"开始向量检索,查询: {query}, k: {k}")
        vector_results = []
        
        try:
            # 执行向量检索
            raw_results = self._vectorstore.similarity_search_with_score(
                query=query,
                k=k
            )
            logger.info(f"向量检索原始结果数量: {len(raw_results)}")

            # 处理检索结果
            for doc, score in raw_results:
                # 获取seg_id
                seg_id = doc.metadata.get("seg_id")
                if not seg_id:
                    logger.warning(f"向量检索结果缺少seg_id: {doc.metadata}")
                    continue

                # 从MySQL获取原文
                original_text = get_seg_content(segment_id=seg_id, chunk_op=chunk_op)
                if not original_text:
                    logger.warning(f"无法获取seg_id {seg_id} 的原文内容")
                    continue

                # 构建新的Document对象
                new_doc = Document(
                    page_content=original_text,
                    metadata={
                        "seg_id": seg_id,
                        "seg_parent_id": doc.metadata.get("seg_parent_id"),
                        "doc_id": doc.metadata.get("doc_id", ""),
                        "seg_type": doc.metadata.get("seg_type", "text"),
                        "score": score
                    }
                )
                vector_results.append((new_doc, score))
                logger.debug(f"向量检索结果 - seg_id: {seg_id}, score: {score:.4f}")

            logger.debug(f"向量检索完成,获取到 {len(vector_results)} 条有效结果")
            return vector_results
            
        except Exception as error:
            logger.error(f"向量检索失败: {str(error)}")
            return []


if __name__ == '__main__':

    # # 初始化 embeddings
    # logger.debug("初始化 embeddings 模型...")
    # embeddings = init_langchain_embeddings()

    # # 创建 Milvus 向量存储
    # logger.debug("初始化 Milvus 向量存储...")
    # # 使用 langchain 框架加载 Milvus 数据库工具包
    # milvus_vectorstore = Milvus(
    #     embedding_function=embeddings,  # 指定向量模型
    #     collection_name=Config.MILVUS_CONFIG["collection_name"],    # 指定 collection 名称
    #     connection_args={   # 连接 Milvus 数据库
    #         "uri": Config.MILVUS_CONFIG["uri"],
    #         "token": Config.MILVUS_CONFIG["token"],
    #         "db_name": Config.MILVUS_CONFIG["db_name"]
    #     },
    #     search_params={
    #         "metric_type": Config.MILVUS_CONFIG["index_params"]["metric_type"],
    #         "params": Config.MILVUS_CONFIG["search_params"]
    #     },
    #     text_field="summary_text"
    # )

    # # 初始化检索器
    # vector_retriever = VectorRetriever(vectorstore=milvus_vectorstore)

    # query_text = "公司"
    # k=10

    # logger.debug("开始检索")

    # results = vector_retriever.search(
    #     query=query_text,
    #     k=k
    # )

    # print(results)
    # print(len(results))
    
    
    from pymilvus import connections, Collection
    connections.connect(host='localhost', port=19530, token='root:Milvus', db_name='default')
    collection = Collection('tk_rag')
    results = collection.query(expr="", output_fields=["segment_id", "vector"], limit=5)
    for r in results:
        print(r["segment_id"], len(r["vector"]), r["vector"][:5])  # 打印前5维
        
    print(collection.indexes)

    connections.connect(host='localhost', port=19530, token='root:Milvus', db_name='default')
    collection = Collection('tk_rag')
    # 随便取一条向量做 query
    sample = collection.query(expr="", output_fields=["vector"], limit=1)[0]["vector"]

    results = collection.search(
        data=[sample],
        anns_field="vector",
        param={"metric_type": "IP", "params": {"nprobe": 50}},
        limit=10,
        output_fields=["segment_id"]
    )
    print(results)
    
    print("-"*100)
    connections.connect(host='localhost', port=19530, token='root:Milvus', db_name='default')
    collection = Collection('tk_rag')
    vectors = [r["vector"] for r in collection.query(expr="", output_fields=["vector"], limit=10)]
    for i in range(len(vectors)):
        for j in range(i+1, len(vectors)):
            v1 = np.array(vectors[i])
            v2 = np.array(vectors[j])
            sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            print(f"sim({i},{j}) = {sim}")



