"""自定义代码处理用户 query"""

import sys
sys.path.append("/Users/jason/PycharmProjects/tk_rag")

import jieba
from rich import print
from rank_bm25 import BM25Okapi
from langchain_milvus import Milvus
from sentence_transformers import CrossEncoder
from langchain_huggingface import HuggingFaceEmbeddings
from typing import List, Tuple, Dict, Any

from config import Config  # 添加配置导入
from src.database.build_milvus_db import MilvusDB


def get_vector_search_results(query: str, k: int = 50) -> List[Tuple[Any, float]]:
    """使用向量相似度进行检索
    
    Args:
        query: 查询文本
        k: 返回结果数量
        
    Returns:
        检索结果列表，每个元素为 (文档, 相似度分数) 的元组
    """
    print("\n=== 向量相似度检索 ===")
    results = vectorstore.similarity_search_with_score(
        query=query,
        k=k,
        filter={
            "partment": "",  # 可以根据需要添加过滤条件
            "role": ""      # 可以根据需要添加过滤条件
        }
    )
    
    # # 打印结果
    # for i, (doc, score) in enumerate(results, 1):
    #     print(f"\n结果 {i}:")
    #     print(f"相似度分数: {score}")
    #     print(f"文档内容: {doc.page_content[:200]}...")
    #     print(f"元数据: {doc.metadata}")
    
    return results

def get_bm25_search_results(query: str, k: int = 50) -> List[Tuple[Any, float]]:
    print("\n=== BM25 检索 ===")
    query_tokens = list(jieba.cut(query))

    try:
        stats = vectorstore.client.get_collection_stats(
            collection_name=vectorstore.collection_name
        )
        total_docs = stats["row_count"]
        print(f"数据库中的文档总数: {total_docs}")

    except Exception as e:
        print(f"获取文档总数时出错: {str(e)}，默认使用1000")
        total_docs = 1000

    # 明确提前返回
    if total_docs == 0:
        print("警告：数据库中没有文档，跳过 BM25 检索")
        return []

    print("正在获取所有文档...")

    try:
        all_docs = vectorstore.similarity_search(
            query="",  
            k=min(total_docs, 1000)  
        )
    except Exception as e:
        print(f"获取文档时出错: {str(e)}")
        return []
    
    print(f"成功获取的文档数: {len(all_docs)}")
    return all_docs

def merge_results(vector_results: List[Tuple[Any, float]], 
                 bm25_results: List[Tuple[Any, float]]) -> List[Tuple[Any, float]]:
    """合并并去重检索结果
    
    Args:
        vector_results: 向量检索结果
        bm25_results: BM25检索结果
        
    Returns:
        合并后的结果列表
    """
    print("\n=== 合并检索结果 ===")
    # 使用文档内容作为去重依据
    seen_contents = set()
    merged_results = []
    
    # 首先添加向量检索结果
    for doc, score in vector_results:
        content = doc.page_content
        if content not in seen_contents:
            seen_contents.add(content)
            merged_results.append((doc, score))
    
    # 然后添加 BM25 检索结果
    for doc, score in bm25_results:
        content = doc.page_content
        if content not in seen_contents:
            seen_contents.add(content)
            merged_results.append((doc, score))
    
    print(f"合并后的结果数量: {len(merged_results)}")
    return merged_results

def rerank_results(query: str, 
                  merged_results: List[Tuple[Any, float]], 
                  top_k: int = 10) -> List[Tuple[Any, float]]:
    """使用 BGE-Rerank 模型进行重排序
    
    Args:
        query: 查询文本
        merged_results: 合并后的检索结果
        top_k: 返回结果数量
        
    Returns:
        重排序后的结果列表
    """
    print("\n=== 重排序 ===")
    # 初始化重排序模型
    reranker = CrossEncoder(Config.MODEL_PATHS["rerank"])
    
    # 准备重排序数据
    pairs = [(query, doc.page_content) for doc, _ in merged_results]
    
    # 计算重排序分数
    rerank_scores = reranker.predict(pairs)
    
    # 将重排序分数与原始结果组合
    reranked_results = [(doc, float(score)) for (doc, _), score in zip(merged_results, rerank_scores)]
    
    # 按重排序分数排序
    reranked_results.sort(key=lambda x: x[1], reverse=True)
    
    # 获取前 top_k 个结果
    final_results = reranked_results[:top_k]
    
    # # 打印结果
    # for i, (doc, score) in enumerate(final_results, 1):
    #     print(f"\n结果 {i}:")
    #     print(f"重排序分数: {score}")
    #     print(f"文档内容: {doc.page_content[:200]}...")
    #     print(f"元数据: {doc.metadata}")
    
    return final_results

def main():
    # 假设用户的提问
    user_query = "发行人在行业中的竞争情况是什么?"
    print(f"\n用户查询: {user_query}")
    
    # 1. 向量相似度检索
    vector_results = get_vector_search_results(user_query, k=50)
    
    # 2. BM25 检索
    bm25_results = get_bm25_search_results(user_query, k=50)
    
    # 3. 合并结果
    merged_results = merge_results(vector_results, bm25_results)
    
    # 4. 重排序
    final_results = rerank_results(user_query, merged_results, top_k=10)
    
    print("\n=== 最终结果 ===")
    for i, (doc, score) in enumerate(final_results, 1):
        print(f"\n结果 {i}:")
        print(f"最终分数: {score}")
        print(f"文档内容: {doc.page_content}")
        print(f"元数据: {doc.metadata}")

if __name__ == "__main__":

    # 初始化数据库连接
    db = MilvusDB()
    db.init_database()

    # 初始化 embeddings
    embeddings = HuggingFaceEmbeddings(
        model_name=Config.MODEL_PATHS["embedding"],
        model_kwargs={'device': Config.DEVICE}
    )
    
    # 创建 Milvus 向量存储
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

    # main()
    user_query = "发行人在行业中的竞争情况是什么?"
    all_docs_with_scores = vectorstore.similarity_search_with_score(
        query=user_query,  
        k=1000  ,
    )
    for i,(doc,score) in enumerate(all_docs_with_scores):
        if score > 0.7:
            print(f"文档 {i+1} 内容: {doc.page_content[:200]}...")
            print(f"文档 {i+1} 相似度分数: {score:.4f}\n")



#     test_text = """
#     发行人在行业中的竞争情况

# （一）发行人在行业中的竞争地位

# 公司成立于2007年，是国内领先的数智化服务供应商，被工信部认定为专精特新“小巨人”企业，通过CMMI 5级能力成熟度认证，还荣获高新技术企业称号。自成立以来，公司依托长期的技术积累、优质的产品以及专业的服务质量管理，已经发展成为面向全国的数智化服务领域综合服务商。截至2024年12月31日，公司业务已经覆盖全国主要省份，并在欧洲设立分支机构。

# 在与主要客户关系方面，公司已与华为合作超17年，是昇腾生态运营伙伴、昇腾原生开发伙伴（大模型方向）、昇腾算力使能服务伙伴，是华为政企主流服务供应商，是华为终端解决方案合作伙伴。曾先后荣获华为各类奖项50余项，近2年连续获得其“中国区技术服务大比武一等奖”，近2年连续获得其“地区部能力建设专项奖”，获得其“政企服务金牌供应商奖”，获得其“企业服务战略贡献奖”，曾连续3年获得华为终端“黄金级解决方案合作伙伴”，获得华为云“优秀解决方案供应商”，华为云CTSP资质，昇腾创新大赛（杭州）银奖、开发者大赛（贵州）一等奖、鲲鹏创新大赛银奖等。"""

#     model = SentenceTransformer(Config.MODEL_PATHS["embedding"])
#     print(f"test_text 向量: {model.encode(user_query)}[:10]")
#         # 检查 query 向量
#     print(f"query 向量: {embeddings.embed_query(user_query)}[:10]")

#     # 插入一条新数据
#     row = {
#         'id': 9999,
#         'vector': model.encode(user_query),
#         'title': user_query,
#         'document_source': 'test',
#         'partment': '',
#         'role': '',
#         'doc_id': 'test'
#     }
#     db.insert_data([row])


    # stats = vectorstore.client.get_collection_stats(collection_name=db.collection_name)
    # print(stats)
    # total_docs = stats["row_count"]
    # print(f"数据库中的文档总数: {total_docs}")

    # from pymilvus import MilvusClient

    # client = MilvusClient(uri="http://10.211.55.3:19530/", token="root:Milvus")
    # client.using_database("tk_db")  # 切换到你的数据库
    # stats = client.get_collection_stats(collection_name="enterprise_doc_vectors")
    # print(stats)
    # print("条目数：", stats["row_count"])