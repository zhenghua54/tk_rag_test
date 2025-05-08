"""query_processed 代码补充:实现 BM25 检索器的分数计算"""

import sys
sys.path.append("/Users/jason/PycharmProjects/tk_rag")

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_milvus import Milvus
from langchain_huggingface import HuggingFaceEmbeddings
from typing import List, Tuple, Any
# 项目配置
from config import Config,logger
from src.database.build_milvus_db import MilvusDB

from rank_bm25 import BM25Okapi

def init_bm25_retriever(db:MilvusDB):
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


def get_hybrid_search_results(query: str, vectorstore: Milvus, bm25_retriever: BM25Retriever, k: int = 50) -> List[Tuple[Any, float]]:
    # ... 前面代码保持不变 ...
    
    # 2. 获取所有文档用于 BM25 检索
    logger.info(f"开始 BM25 检索...")
    bm25_docs_with_scores = []

    try:
        # 获取BM25检索结果
        bm25_docs = bm25_retriever.get_relevant_documents(query, k=k)
        
        # 使用rank_bm25直接计算分数
        # 1. 准备语料库
        tokenized_corpus = [doc.page_content.split() for doc in bm25_docs]
        # 2. 初始化BM25模型
        bm25 = BM25Okapi(tokenized_corpus)
        # 3. 对查询进行分词
        tokenized_query = query.split()
        # 4. 获取分数
        raw_scores = bm25.get_scores(tokenized_query)
        
        # 5. 归一化分数（可选）
        max_score = max(raw_scores) if raw_scores.size > 0 else 1.0
        normalized_scores = [float(score/max_score) for score in raw_scores] if max_score > 0 else raw_scores
        
        # 6. 组合文档和分数
        bm25_docs_with_scores = [(doc, score) for doc, score in zip(bm25_docs, normalized_scores)]
            
    except Exception as e:
        logger.error(f"BM25 检索失败: {str(e)}")
        bm25_docs_with_scores = []

    # # 3. 使用位置作为近似分数计算方法
    # bm25_docs_with_scores = []

    # try:
    #     bm25_docs = bm25_retriever.get_relevant_documents(query,k=k)

    #     # 使用位置作为近似分数计算方法
    #     for i,doc in enumerate(bm25_docs):
    #         # 根据位置计算分数,排名越靠前分数越高
    #         score = 1.0 - (i/len(bm25_docs)) if len(bm25_docs) > 0 else 0.0
    #         bm25_docs_with_scores.append((doc,score))

    # except Exception as e:
    #     logger.error(f"BM25 检索失败: {str(e)}")
    #     bm25_docs_with_scores = []

    # logger.info(f"BM25 检索完成,获取到 {len(bm25_docs_with_scores)} 条结果")
    
    # ... 后面代码保持不变 ...


if __name__ == "__main__":
    logger.info("初始化检索系统...")

    # 初始化数据库连接
    db = MilvusDB()
    db.init_database()

    # 初始化 embeddings
    logger.info("初始化 embeddings 模型...")
    embeddings = HuggingFaceEmbeddings(
        model_name=Config.MODEL_PATHS["embedding"],
        model_kwargs={'device': Config.DEVICE}
    )
    
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
        text_field="text_chunk",
    )
    logger.info("Milvus 向量存储初始化完成")
    

    # 初始化 BM25 检索器
    bm25_retriever = init_bm25_retriever(db)