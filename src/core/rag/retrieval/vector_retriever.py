"""向量检索模块"""
from collections import OrderedDict
from typing import List
from langchain_milvus import Milvus
from src.utils.common.logger import logger
import numpy as np


class VectorRetriever:
    """向量检索器类"""
    
    def __init__(self, vectorstore: Milvus):
        """初始化向量检索器
        
        Args:
            vectorstore: Milvus 向量存储实例
        """
        self._vectorstore = vectorstore

    def search(self, query: str, permission_ids: str = None, k: int = 5, chunk_op=None) -> dict[str, float]:
        """执行 milvus 向量检索
        
        Args:
            query: 查询文本
            permission_ids: 权限ID
            k: 检索数量
            chunk_op: Mysql 的 ChunkOperation实例
            
        Returns:
            dict[str, float]: 检索结果字典(seg_id, score)
        """
        logger.info(f"开始向量检索,查询: {query}, 权限ID: {permission_ids}, k: {k}")
        vector_results = OrderedDict()  # 使用OrderedDict保持顺序
        seen_parent_ids = set()  # 用于记录已处理过的父片段ID
        
        try:
            # 不带权限过滤的检索
            search_params = {
                "search_type": "similarity",
                "k": k
            }
            
            raw_result = self._vectorstore.similarity_search_with_score(
                query=query,
                **search_params
            )
            logger.info("=== 不带权限过滤的检索结果 ===")
            for doc, score in raw_result:
                logger.info(f"文档ID: {doc.metadata.get('doc_id')}, "
                          f"片段ID: {doc.metadata.get('seg_id')}, "
                          f"权限ID: {doc.metadata.get('permission_ids')}, "
                          f"相似度分数: {score:.4f}")
            
            # 带权限过滤的检索
            permission_results = raw_result
            if permission_ids:
                try:
                    search_params = {
                        "search_type": "similarity",
                        "k": k
                    }
                    if permission_ids:
                        search_params["filter"] = f'permission_ids == "{permission_ids}"'
                    
                    permission_results = self._vectorstore.similarity_search_with_score(
                        query=query,
                        **search_params
                    )
                    logger.info("=== 带权限过滤的检索结果 ===")
                    for doc, score in permission_results:
                        logger.info(f"文档ID: {doc.metadata.get('doc_id')}, "
                                  f"片段ID: {doc.metadata.get('seg_id')}, "
                                  f"权限ID: {doc.metadata.get('permission_ids')}, "
                                  f"相似度分数: {score:.4f}")
                except Exception as e:
                    logger.warning(f"带权限过滤检索失败，使用不带权限的结果: {str(e)}")
                
            # 处理检索结果
            for doc, score in permission_results:
                seg_id = doc.metadata.get("seg_id") # 片段ID
                doc_id = doc.metadata.get("doc_id") # 文档ID，用来检索权限
                logger.debug(f"向量检索结果 - seg_id: {seg_id}, doc_id: {doc_id}, score: {score:.4f}")
                if not seg_id:
                    logger.warning(f"向量检索结果缺少seg_id: {doc.metadata}")
                    continue            
                # 添加子块结果    
                vector_results[seg_id] = score
                # 添加父块结果
                seg_parent_id = doc.metadata.get("seg_parent_id", "").strip()
                if seg_parent_id and seg_parent_id not in seen_parent_ids:
                    seen_parent_ids.add(seg_parent_id)
                    logger.debug(f"向量检索结果 - 检测到父片段ID: {seg_parent_id}")
                    vector_results[seg_parent_id] = score * 0.1  # 父块的分数为子块的 10%

            logger.debug(f"向量检索完成,获取到 {len(vector_results)} 条有效结果")
            return vector_results
            
        except Exception as error:
            logger.error(f"向量检索失败: {str(error)}")
            return {}  # 返回空字典而不是空列表


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
    results = collection.query(expr="", output_fields=["seg_id", "vector"], limit=5)
    for r in results:
        print(r["seg_id"], len(r["vector"]), r["vector"][:5])  # 打印前5维
        
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
        output_fields=["seg_id"]
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



