"""
LLM生成:手动实现检索 + 历史 + 拼接 + 生成
问题:最长 token 数量问题未优化
"""

import sys

sys.path.append("/Users/jason/PycharmProjects/tk_rag")

from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_milvus import Milvus
from langchain_huggingface import HuggingFacePipeline
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate

from config import Config, logger
from src.query_process import search_documents, init_bm25_retriever
from src.database.build_milvus_db import MilvusDB


def create_llm_chain():
    """创建 LLM 对话链"""
    # 初始化 LLM
    logger.info("初始化 LLM 模型...")
    llm = AutoModelForCausalLM.from_pretrained(Config.MODEL_PATHS["llm"])
    tokenizer = AutoTokenizer.from_pretrained(Config.MODEL_PATHS["llm"])

    # 创建 llm pipeline
    pipe = pipeline(
        "text-generation",
        model=llm,
        tokenizer=tokenizer,
        device="cpu",  # 改用 cpu 避免出现 MPS 错误
        temperature=0.7,
        top_p=0.95,
        repetition_penalty=1.15,
        do_sample=True,
    )

    # 创建 Langchain 的 LLM 包装器
    llm = HuggingFacePipeline(pipeline=pipe)

    # 创建对话记忆
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
        output_key="answer",
    )

    # 创建提示词模板
    template = """基于以下信息回答问题.如果无法从信息中找到答案,请直接回答"抱歉,现有知识库中没有相关信息."
    
    信息:
    {context}
    
    历史对话:
    {chat_history}

    问题: {question}
    
    请基于以上信息,特别是历史对话的上下文,给出准确、连贯的回答.

    回答:"""

    # 创建提示词模板
    prompt = PromptTemplate(
        template=template, input_variables=["context", "chat_history", "question"]
    )

    return llm, memory, prompt


def process_query(query: str, vectorstore: Milvus, bm25_retriever, llm, memory, prompt):
    """处理用户查询并生成回答"""
    # 检查输入
    if not query or not query.strip():
        return "请输入有效的问题"

    # 构建混合检索器
    class CustomRetriever:
        def __init__(self, vectorstore, bm25_retriever):
            self.vectorstore = vectorstore
            self.bm25_retriever = bm25_retriever

        def get_relevant_documents(self, query: str, k: int = 50, top_k: int = 5):
            # 使用向量检索
            search_results = search_documents(
                query=query,
                vectorstore=self.vectorstore,
                bm25_retriever=self.bm25_retriever,
                k=k,
                top_k=top_k,
            )

            return [doc for doc, _ in search_results]
    
    custom_retriever = CustomRetriever(vectorstore, bm25_retriever)

    # 创建 langchain 对话链
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=custom_retriever,
        memory=memory,
        combine_docs_chain_kwargs={"prompt": prompt},
        return_source_documents=True,
        verbose=True,
    )

    # 调用链生成回答(Langchain 自动检索 + 历史 + 拼接 + 生成)
    logger.info(f"开始生成回答...")
    try:
        response = chain.invoke({"question": query})["answer"]  # 只获取模型的 answer 内容
        return response
    except Exception as e:
        logger.error(f"生成回答失败: {e}")
        return "生成回答失败,请稍后再试"


def main():
    """主函数"""
    # 初始化数据库连接
    db = MilvusDB()
    db.init_database()

    # 初始化embeddings
    logger.info("初始化 embeddings 模型...")
    embeddings = HuggingFaceEmbeddings(
        model_name=Config.MODEL_PATHS["embedding"],
        model_kwargs={"device": Config.DEVICE},
    )

    # 创建 Milvus 向量存储
    vectorstore = Milvus(
        embedding_function=embeddings,
        collection_name=Config.MILVUS_CONFIG["collection_name"],
        connection_args={
            "uri": Config.MILVUS_CONFIG["uri"],
            "token": Config.MILVUS_CONFIG["token"],
            "db_name": Config.MILVUS_CONFIG["db_name"],
        },
        search_params={
            "metric_type": Config.MILVUS_CONFIG["index_params"]["metric_type"],
            "params": Config.MILVUS_CONFIG["search_params"],
        },
        text_field="text_chunk",
    )

    # 初始化 BM25 检索器
    bm25_retriever = init_bm25_retriever(db)

    # 初始化 LLM 对话链
    llm, memory, prompt = create_llm_chain()

    # 测试查询
    while True:
        try:
            query = input("请输入你的问题: ")
            if not query or not query.strip():
                logger.info("输入为空,跳过本次查询")
                continue
            response = process_query(
                query, vectorstore, bm25_retriever, llm, memory, prompt
            )
            # 清理回答,只保留实际内容
            response = response.split("回答:")[-1].strip()
            logger.info(f"回答: {response}")
        except KeyboardInterrupt:
            logger.info("\n再见!")
            break
        except Exception as e:
            logger.error(f"处理查询时发生错误: {e}")
            print(f"抱歉,处理问题时出现错误,请稍后重试!")


if __name__ == "__main__":
    main()

    """
    # 使用方式
    # 初始化系统
    db = MilvusDB()
    db.init_database()
    vectorstore = ...  # 初始化向量存储
    bm25_retriever = init_bm25_retriever(db)
    llm, memory, prompt = create_llm_chain()

    # 处理查询
    response = process_query("你的问题", vectorstore, bm25_retriever, llm, memory, prompt)
    """
