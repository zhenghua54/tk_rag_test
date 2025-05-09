"""使用 streamlit web 框架部署 RAG 问答系统"""

import os
import sys
from typing import List, Dict, Any

# 引入 Streamlit 框架(Web UI)
import streamlit as st
# 引入 Langchain 组件
from langchain.chains import ConversationalRetrievalChain
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_milvus import Milvus

# 加载项目模块
sys.path.append("/Users/jason/PycharmProjects/tk_rag")
from config import Config, logger
from src.database.build_milvus_db import MilvusDB
from src.llm_generate import process_query, CustomRetriever, create_llm_chain
from src.query_process import init_bm25_retriever

# Streamlit 页面配置
st.set_page_config(
    page_title="天宽 RAG 智能问答",
    page_icon="http://www.xinchan.cn/file/upload/202110/16/1731354666.png",
    layout="wide",
)

# 自定义 CSS 样式
st.markdown("""
<style>
    .main {
        padding: 0rem 1rem;
    }
    .stTextInput>div>div>input {
        font-size: 16px;
    }
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
        border: 1px solid #e0e0e0;
    }
    .chat-message.user {
        border-color: #2b313e;
    }
    .chat-message.assistant {
        border-color: #475063;
    }
    .chat-message .content {
        display: flex;
        flex-direction: row;
        align-items: flex-start;
    }
    .chat-message .avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        margin-right: 1rem;
    }
    .chat-message .message {
        flex: 1;
    }
    .source-docs {
        margin-top: 1rem;
        padding: 1rem;
        border: 1px solid #e0e0e0;
        border-radius: 0.5rem;
    }
    .source-doc {
        margin-bottom: 0.5rem;
        padding: 0.5rem;
    }
    .source-doc-title {
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .source-doc-content {
        display: none;
        margin-top: 0.5rem;
        padding: 0.5rem;
        background-color: #f5f5f5;
        border-radius: 0.3rem;
    }
    .source-doc:hover .source-doc-content {
        display: block;
    }
    .input-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background-color: white;
        padding: 1rem;
        border-top: 1px solid #e0e0e0;
        z-index: 1000;
    }
    .chat-container {
        margin-bottom: 100px;
    }
</style>
""", unsafe_allow_html=True)


#  Streamlit 缓存:只初始化一次 RAG 系统
@st.cache_resource
def init_rag_chain():
    # 初始化 Milvus 数据库连接
    db = MilvusDB()
    db.init_database()

    # 初始化 Embedding 模型
    logger.info("初始化 embeddings 模型...")
    embeddings = HuggingFaceEmbeddings(
        model_name=Config.MODEL_PATHS["embedding"],
        model_kwargs={"device": Config.DEVICE}
    )

    # 创建 Milvus 向量检索器
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

    # 初始化 BM25 规则检索器
    logger.info("初始化 BM25 检索器...")
    bm25_retriever = init_bm25_retriever(db)

    # 创建混合检索器
    logger.info("初始化混合检索器...")
    custom_retriever = CustomRetriever(vectorstore, bm25_retriever)

    # 初始化 LLM（大模型）、对话历史、提示词
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

    return chain,memory


def format_source_docs(source_docs: List[Dict[str, Any]]) -> str:
    """格式化源文档信息"""
    formatted_docs = []
    for i, doc in enumerate(source_docs, 1):
        metadata = doc.metadata
        content = doc.page_content[:500] + "..." if len(doc.page_content) > 500 else doc.page_content
        
        formatted_doc = f"""
        <div class="source-doc">
            <div class="source-doc-title">
                来源 {i}: {metadata.get('document_source', '未知')}
            </div>
            <div class="source-doc-content">
                {content}
            </div>
        </div>
        """
        formatted_docs.append(formatted_doc)
    
    return "\n".join(formatted_docs)


def main():
    st.title("💬 RAG 智能知识问答系统")

    # 初始化历史对话
    if "history" not in st.session_state:
        st.session_state.history = []

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "chain" not in st.session_state or "memory" not in st.session_state:
        chain, memory = init_rag_chain()
        st.session_state.chain = chain
        st.session_state.memory = memory

        # 主界面
    # 显示历史消息
    chat_container = st.container()
    with chat_container:
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        for message in st.session_state.history:
            with st.container():
                # 用户消息
                if message['role'] == 'user':
                    st.markdown(f"""
                    <div class="chat-message user">
                        <div class="content">
                            <div class="avatar">👤</div>
                            <div class="message">
                                <strong>用户: </strong><br>
                                {message['content']}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                # 助手消息
                else:
                    st.markdown(f"""
                    <div class="chat-message assistant">
                        <div class="content">
                            <div class="avatar">🤖</div>
                            <div class="message">
                                <strong>助手: </strong><br>
                                {message['content']}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                # 如果是助手的回答,显示源文档
                if message.get('sources'):
                    st.markdown(f"""
                    <div class="source-docs">
                        <h4>参考资料</h4>
                        {format_source_docs(message['sources'])}
                    </div>
                    """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 固定在底部的输入区域
    st.markdown('<div class="input-container">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([6, 1, 1])
    with col1:
        user_input = st.text_input("请输入你的问题: ", key="user_input")
    with col2:
        if st.button("发送"):
            query = st.session_state.user_input
            if query.strip():
                st.session_state.history.append({
                    "role": "user",
                    "content": query.strip()
                })

                # 获取回答
                with st.spinner("思考中..."):
                    memory = st.session_state.memory
                    response = st.session_state.chain.invoke({"question": query.strip(),"chat_history":memory.buffer})

                    # 添加助手回答
                    st.session_state.history.append({
                        "role": "assistant",
                        "content": response["answer"],
                        "sources": response.get("source_documents")
                    })

            # 清空输入框 — 安全方式
            st.rerun()
    with col3:
        if st.button("清空历史"):
            st.session_state.messages = []
            st.session_state.history = []
            st.session_state.chain, st.session_state.memory = init_rag_chain()
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
