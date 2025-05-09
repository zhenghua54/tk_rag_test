"""使用 streamlit web 框架部署 RAG 问答系统"""

import os
import sys
from typing import List

# Streamlit 框架
import streamlit as st
# Langchain 框架
from langchain.chains import ConversationalRetrievalChain
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_milvus import Milvus

# 项目包
sys.path.append("/Users/jason/PycharmProjects/tk_rag")
from config import Config, logger
from src.database.build_milvus_db import MilvusDB
from src.llm_generate import process_query, CustomRetriever, create_llm_chain
from src.query_process import init_bm25_retriever


# 初始化 RAG 系统
@st.cache_resource
def init_rag_chain():
    # 初始化数据库连接
    db = MilvusDB()
    db.init_database()

    # 初始化embeddings
    logger.info("初始化 embeddings 模型...")
    embeddings = HuggingFaceEmbeddings(
        model_name=Config.MODEL_PATHS["embedding"],
        model_kwargs={"device": Config.DEVICE}
    )

    # 创建 Milvus 向量存储
    logger.info("初始化 Milvus 向量存储...")
    vectorstore = Milvus(
        embedding_function=embeddings,
        collection_name=Config.MILVUS_CONFIG["collection_name"],
        connection_args={
            "uri": Config.MILVUS_CONFIG["uri"],
            "token": Config.MILVUS_CONFIG["token"],
            "db_name": Config.MILVUS_CONFIG["db_name"], },
        search_params={
            "metric_type": Config.MILVUS_CONFIG["index_params"]["metric_type"],
            "params": Config.MILVUS_CONFIG["search_params"], },
        text_field="text_chunk",
    )

    # 初始化 BM25 检索器
    logger.info("初始化 BM25 检索器...")
    bm25_retriever = init_bm25_retriever(db)

    # 初始化混合检索器并添加日志
    logger.info("初始化混合检索器...")
    custom_retriever = CustomRetriever(vectorstore, bm25_retriever)

    # 初始化 LLM 对话链
    llm, memory, chat_prompt, condense_question_prompt = create_llm_chain()

    # 创建 langchain 对话链
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=custom_retriever,
        memory=memory,  # 使用 langchain 内部机制保存历史会话(input,output)
        combine_docs_chain_kwargs={
            "prompt": chat_prompt,
        },
        condense_question_prompt=condense_question_prompt,  # query 重写模板
        return_source_documents=True,
        verbose=True,  # 设置日志为 False,避免日志过多
    )

    return chain


# 页面布局
st.set_page_config(
    page_title="<UNK> RAG <UNK>",
    # page_icon="http://www.xinchan.cn/file/upload/202110/16/1731354666.png",
    page_icon="💬",
    layout="wide",
)
st.title("💬 RAG 智能知识问答系统")

# 初始化 Chain
chain = init_rag_chain()

# 输入提问
query = st.text_input("请输入你的问题: ")

# 提交按钮
if st.button("提交"):
    if query.strip():
        with st.spinner("<UNK> 思考中 <UNK>..."):
            answer = process_query(query, chain)
            st.success(answer)
    else:
        st.warning("请输入有效问题. ")
