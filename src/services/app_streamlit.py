"""使用 streamlit web 框架部署 rag 问答系统"""

import sys
from typing import List, Any

# 引入 Streamlit 框架(Web UI)
import streamlit as st
# 引入 Langchain 组件
from langchain.chains import ConversationalRetrievalChain
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_milvus import Milvus

# 加载项目模块
sys.path.append("/Users/jason/PycharmProjects/tk_rag")
from config.settings import Config
from src.utils.common.logger import logger
from src.database.milvus.connection import MilvusDB
from src.utils.llm_generate import CustomRetriever, create_llm_chain
from src.utils.query_process import init_bm25_retriever

# Streamlit 页面配置
st.set_page_config(
    page_title="天宽 rag 智能问答",
    page_icon="http://www.xinchan.cn/file/upload/202110/16/1731354666.png",
    layout="wide",
)

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
        # text_field="text_chunk", # 不传, Document.page_content 为空, 使用seg_id 通过 mysql 提取原文内容.
    )

    # 初始化 BM25 规则检索器
    logger.info("初始化 BM25 检索器...")
    bm25_retriever = init_bm25_retriever(db)

    # 创建混合检索器
    logger.info("初始化混合检索器...")
    custom_retriever = CustomRetriever(vectorstore, bm25_retriever)

    # 初始化 LLM（大模型）、对话历史、提示词
    llm, memory, chat_prompt = create_llm_chain()

    # 创建 langchain 对话链
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=custom_retriever,
        memory=memory,  # 使用 langchain 内部机制保存历史会话(input,output)
        combine_docs_chain_kwargs={
            "prompt": chat_prompt,
        },
        return_source_documents=True,
        verbose=True,  # 设置日志为 False,避免日志过多
    )

    return chain, memory


def format_source_docs(source_docs: List[Any]) -> str:
    """
    生成论文引用风格的参考资料，每条为卡片，超出20字截断，点击弹窗显示全文。
    """
    chips = []
    modals = []
    for i, doc in enumerate(source_docs, 1):
        if hasattr(doc, 'metadata') and hasattr(doc, 'page_content'):
            metadata = doc.metadata
            content = doc.page_content
        else:
            metadata = doc.get('metadata', {})
            content = doc.get('page_content', '')

        # 卡片内容截断为20字
        short_content = content.replace('\n', ' ').replace('\r', '')[:20]
        if len(content) > 20:
            short_content += "..."

        # 生成唯一ID，确保JavaScript能正确找到元素
        doc_id = f"source-doc-{i}"
        modal_id = f"{doc_id}-mask"

        # 卡片 - 使用data-modal-id属性，JavaScript会处理点击事件
        chip = f"""<span class="source-doc-chip" data-modal-id="{modal_id}">{i}: {short_content}</span>"""
        chips.append(chip)

        # 弹窗
        modal = f"""
<div id="{modal_id}" class="source-doc-modal-mask">
  <div class="source-doc-modal">
    <span class="source-doc-modal-close" data-modal-id="{modal_id}">&times;</span>
    <div style="font-weight:bold;margin-bottom:0.5rem;">来源 {i}: {metadata.get('document_source', '未知')}</div>
    <div style="white-space: pre-wrap;line-height:1.7;">{content}</div>
  </div>
</div>"""
        modals.append(modal)

    # 参考资料 chips 区域
    chips_html = f"""<div class="source-docs">{''.join(chips)}</div>"""
    # 弹窗全部拼接
    modals_html = ''.join(modals)
    
    return chips_html + modals_html


# 发送按钮功能
def send_message():
    query = st.session_state.user_input.strip()
    if query:
        # 存入用户消息 (history)
        st.session_state.history.append({"role": "user", "content": query})

        # 设置加载状态
        st.session_state.is_processing = True
        
        # 调用 chain 获取回答
        with st.spinner("思考中..."):
            chain = st.session_state.chain
            logger.info(f"开始检索和生成回答，用户问题: {query}")
            response = chain.invoke({"question": query})

            # 补充引用文档，不手动 add_ai_message
            if response.get('source_documents'):
                # 找到最后一条 AIMessage，补充 additional_kwargs
                for msg in reversed(st.session_state.memory.chat_memory.messages):
                    if msg.type == "ai":
                        msg.additional_kwargs = {'sources': response.get('source_documents')}
                        break

            # history 存档,不参与渲染
            st.session_state.history.append({
                "role": "assistant",
                "content": response['answer'],
                "sources": response.get('source_documents')
            })

        # 清空输入框
        st.session_state.user_input = ""
        
        # 重置加载状态
        st.session_state.is_processing = False


# 清空历史按钮功能
def clear_history():
    st.session_state.memory.clear()
    st.session_state.user_input = ""  # 清空输入框
    st.session_state.is_processing = False  # 重置处理状态


def main():
    st.title("天宽 rag 企业知识问答系统")
    
    # 添加全局CSS和JavaScript
    st.markdown(
        """
        <style>
        .main {
            padding: 0rem 1rem;
        }
        .stTextInput>div>div>input {
            font-size: 14px;
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

        /* 聊天气泡整体样式 */
        .chat-message.assistant {
            border: 1px solid #475063;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
            padding: 1.5rem;
            background: #f8fafd;
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            width: 100%;
            box-sizing: border-box;
            margin-left: 0;
        }

        .chat-message .content {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            width: 100%;
        }
        
        /* 头像和昵称横向排列，垂直居中对齐 */
        .chat-message .header {
            display: flex;
            flex-direction: row;
            align-items: center;
            margin-bottom: 8px;
            width: 100%;
        }
        
        .chat-message .avatar {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            object-fit: cover;
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }
        
        .chat-message .message {
            flex: 1;
            width: 100%;
            padding-left: 20px; /* 与昵称左对齐 */
            box-sizing: border-box;
        }

        /* 参考资料区域与内容左对齐 */
        .source-docs {
            margin-top: 0.5rem;
            width: 100%;
            display: flex;
            flex-wrap: wrap;
            align-items: flex-start;
            gap: 0.5rem;
            padding-left: 20px; /* 与昵称左对齐 */
        }

        /* 单条参考资料卡片 */
        .source-doc-chip {
            display: inline-block;
            background: #e6f0fa;
            color: #222;
            border-radius: 8px;
            padding: 0.3rem 0.9rem;
            font-size: 12px;
            margin: 0 0.3rem 0.3rem 0;
            cursor: pointer;
            max-width: 180px;
            white-space: normal;
            overflow: hidden;
            content-overflow: ellipsis;
            vertical-align: middle;
            border: 1px solid #b3d4fc;
            transition: background 0.2s;
            content-align: left;
            word-break: break-all;
        }

        /* 鼠标悬停高亮 */
        .source-doc-chip:hover {
            background: #d0e7fa;
        }

        /* 让卡片自动换行 */
        .source-docs {
            flex-wrap: wrap;
            word-break: break-all;
        }

        /* 弹窗遮罩 */
        .source-doc-modal-mask {
            position: fixed;
            z-index: 9999;
            left: 0; top: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.3);
            display: none;
            align-items: center;
            justify-content: center;
        }

        /* 弹窗内容 */
        .source-doc-modal {
            background: #fff;
            border-radius: 10px;
            padding: 2rem 1.5rem 1.5rem 1.5rem;
            max-width: 90vw;
            max-height: 70vh;
            overflow-y: auto;
            box-shadow: 0 4px 24px rgba(0,0,0,0.18);
            position: relative;
            min-width: 300px;
        }

        .source-doc-modal-close {
            position: absolute;
            right: 1.2rem;
            top: 1.2rem;
            font-size: 1.5rem;
            color: #888;
            cursor: pointer;
            font-weight: bold;
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
        .icon-button {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.3rem;
            font-size: 14px;
        }
        .icon-button img {
            width: 18px;
            height: 18px;
            vertical-align: middle;
        }
        /* 统一按钮间距 */
        div[data-testid="column"] {
            padding-right: 16px !important;
        }

        /* 让按钮内文字不换行 + 适中 padding */
        button[kind="secondary"] {
            width: 100px;
            white-space: nowrap;
            padding: 6px 0px;
            font-size: 14px;
        }
        button[kind="primary"] {
            width: 100px;
            white-space: nowrap;
            padding: 6px 0px;
            font-size: 14px;
        }
        
        /* 修复内容区域排版问题 */
        [data-testid="stVerticalBlockBorderWrapper"] {
            gap: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        
        /* 回到顶部按钮 */
        .back-to-top {
            position: fixed;
            right: 20px;
            bottom: 120px;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: #475063;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            z-index: 9999;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            opacity: 0.9;
            transition: all 0.3s;
            font-size: 20px;
            font-weight: bold;
        }
        .back-to-top:hover {
            opacity: 1;
            transform: translateY(-3px);
            box-shadow: 0 4px 15px rgba(0,0,0,0.4);
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    # 添加JavaScript脚本，确保在DOM加载完成后执行
    st.markdown(
        """
        <script>
        // 立即执行函数，确保代码在iframe内立即运行
        (function() {
            // 延迟执行，确保DOM已完全加载
            setTimeout(function() {
                setupEventListeners();
            }, 1000);
            
            // 设置事件监听器
            function setupEventListeners() {
                console.log("设置事件监听器...");
                
                // 创建回到顶部按钮
                const backToTop = document.createElement('div');
                backToTop.className = 'back-to-top';
                backToTop.innerHTML = '↑';
                backToTop.setAttribute('title', '回到顶部');
                
                // 添加点击事件
                backToTop.addEventListener('click', function() {
                    window.scrollTo({top: 0, behavior: 'smooth'});
                });
                
                // 添加到body
                document.body.appendChild(backToTop);
                console.log("回到顶部按钮已创建");
                
                // 监听滚动事件，控制按钮显示/隐藏
                window.addEventListener('scroll', function() {
                    if (window.scrollY > 300) {
                        backToTop.style.display = 'flex';
                    } else {
                        backToTop.style.display = 'none';
                    }
                });
                
                // 初始化按钮显示状态
                if (window.scrollY > 300) {
                    backToTop.style.display = 'flex';
                }
                
                // 监听点击事件 - 使用事件委托
                document.addEventListener('click', function(e) {
                    // 参考资料卡片点击
                    if(e.target.classList.contains('source-doc-chip') || e.target.closest('.source-doc-chip')) {
                        const chip = e.target.classList.contains('source-doc-chip') ? e.target : e.target.closest('.source-doc-chip');
                        const modalId = chip.getAttribute('data-modal-id');
                        console.log("点击了来源卡片，modal ID:", modalId);
                        
                        // 查找模态框
                        const modal = document.getElementById(modalId);
                        if(modal) {
                            modal.style.display = 'flex';
                            console.log("显示模态框:", modalId);
                        } else {
                            console.log("未找到模态框:", modalId);
                        }
                    }
                    
                    // 关闭弹窗 - 点击遮罩
                    if(e.target.classList.contains('source-doc-modal-mask')) {
                        e.target.style.display = 'none';
                        console.log("关闭模态框 - 点击遮罩");
                    }
                    
                    // 关闭弹窗 - 点击关闭按钮
                    if(e.target.classList.contains('source-doc-modal-close')) {
                        const modalId = e.target.getAttribute('data-modal-id');
                        const modal = document.getElementById(modalId);
                        if(modal) {
                            modal.style.display = 'none';
                            console.log("关闭模态框 - 点击关闭按钮");
                        }
                    }
                });
                
                // 自动滚动到底部
                function scrollToBottom() {
                    window.scrollTo({
                        top: document.body.scrollHeight,
                        behavior: 'smooth'
                    });
                }
                
                // 监听内容变化
                const observer = new MutationObserver(function(mutations) {
                    console.log("检测到DOM变化，准备滚动到底部");
                    setTimeout(scrollToBottom, 300);
                });
                
                // 找到聊天容器并监听变化
                const chatContainer = document.getElementById('chat-container');
                if (chatContainer) {
                    observer.observe(chatContainer, { 
                        childList: true, 
                        subtree: true 
                    });
                    console.log("已设置聊天容器变化监听");
                    
                    // 初始滚动到底部
                    setTimeout(scrollToBottom, 500);
                } else {
                    console.log("未找到聊天容器");
                }
            }
            
            // 尝试在父窗口和iframe中都执行
            if (window.parent) {
                try {
                    // 在父窗口中执行
                    window.parent.eval(`(${setupEventListeners.toString()})()`);
                    console.log("在父窗口执行事件监听器");
                } catch(e) {
                    console.error("在父窗口执行失败:", e);
                }
            }
        })();
        </script>
        """,
        unsafe_allow_html=True
    )

    # 添加回车键发送消息的JavaScript
    st.markdown(
        """
        <script>
        // 监听回车键发送消息
        document.addEventListener('keydown', function(event) {
            // 检查是否按下了回车键，且不是在组合键中
            if (event.key === 'Enter' && !event.shiftKey && !event.ctrlKey && !event.altKey) {
                // 查找输入框
                const input = document.querySelector('input[id="text_input_user"]');
                if (input && input.value.trim() !== '') {
                    // 查找发送按钮 - 更精确的选择器
                    const sendButton = document.querySelector('button[kind="primary"]');
                    if (sendButton && !sendButton.disabled) {
                        sendButton.click();
                        event.preventDefault();
                    }
                }
            }
        });
        </script>
        """,
        unsafe_allow_html=True
    )

    # 初始化 session_state
    if "history" not in st.session_state:
        st.session_state.history = []

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "chain" not in st.session_state or "memory" not in st.session_state:
        chain, memory = init_rag_chain()
        st.session_state.chain = chain
        st.session_state.memory = memory

    if "user_input" not in st.session_state:
        st.session_state.user_input = ""
        
    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False

    # 主界面
    # 显示历史消息
    chat_container = st.container()
    with chat_container:
        st.markdown('<div id="chat-container" class="chat-container">', unsafe_allow_html=True)

        memory = st.session_state.memory
        for message in memory.chat_memory.messages:
            with st.container():
                if message.type == 'human':
                    st.markdown(f"""
<div class="chat-message user">
    <div class="content">
        <div class="header">
            <div class="avatar">👤</div>
            <strong>用户:</strong>
        </div>
        <div class="message">
            {message.content}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
                else:
                    # 合并助手内容和参考资料 chips
                    sources_html = ""
                    if hasattr(message, 'additional_kwargs') and message.additional_kwargs.get('sources'):
                        sources_html = format_source_docs(message.additional_kwargs['sources'])

                    # 确保不会有多余的div标签
                    reply_html = f"""
<div class="chat-message assistant">
    <div class="content">
        <div class="header">
            <div class="avatar">🤖</div>
            <strong>助手:</strong>
        </div>
        <div class="message">
            {message.content}
        </div>
        {sources_html}
    </div>
</div>
"""
                    st.markdown(reply_html, unsafe_allow_html=True)

    # 固定输入区域
    st.markdown('<div class="input-container">', unsafe_allow_html=True)
    col1, col2 = st.columns([6, 2])

    with col1:
        st.text_input(
            label="输入",
            placeholder="请输入要咨询的问题",
            key="user_input",
            on_change=send_message,
            label_visibility="collapsed",
            disabled=st.session_state.is_processing
        )

    with col2:
        bcol1, bcol2 = st.columns([1, 1])
        with bcol1:
            st.button(
                "发送" if not st.session_state.is_processing else "思考中...", 
                key="send_button", 
                on_click=send_message, 
                use_container_width=True, 
                type="primary",
                disabled=st.session_state.is_processing
            )
        with bcol2:
            st.button(
                "清空历史", 
                key="clear_button", 
                on_click=clear_history, 
                use_container_width=True,
                disabled=st.session_state.is_processing
            )


if __name__ == "__main__":
    main()
