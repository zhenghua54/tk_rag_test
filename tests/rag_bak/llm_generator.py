"""使用 langchain+LLM 完成 rag 生成内容"""

import os
from typing import List

# Langchain 框架
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts import PromptTemplate
from langchain.schema import BaseRetriever, Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_milvus import Milvus
from langchain_openai import ChatOpenAI

# 项目包
from config.settings import Config
from config
from src.utils.query_process import search_documents, init_bm25_retriever
from src.database.milvus.connection import MilvusDB

# 构建混合检索器
class CustomRetriever(BaseRetriever):
    def __init__(self, vectorstore, bm25_retriever):
        super().__init__()
        self._vectorstore = vectorstore
        self._bm25_retriever = bm25_retriever

    # 替换 CustomRetriever 内部的 .vectorstore 和 .bm25_retriever ,使用已定义的替换
    @property
    def vectorstore(self):
        return self._vectorstore

    @property
    def bm25_retriever(self):
        return self._bm25_retriever

    def _get_relevant_documents(self, query: str, k: int = 50, top_k: int = 5, score_threshold: float = 0.1) -> List[
        Document]:
        # 防止空 query 跳过检索的问题
        if not query or not query.strip():
            logger.warning("检索器收到空 query, 跳过检索")
            return []

        # 使用向量检索
        search_results = search_documents(
            query=query,
            vectorstore=self.vectorstore,
            bm25_retriever=self.bm25_retriever,
            k=k,
            top_k=top_k
        )

        # 只保留向量检索分数 >= 阈值的文档
        filtered_docs = [doc for doc, score in search_results if score >= score_threshold]

        if not filtered_docs:
            logger.info("检索结果为空，返回空文档防止死循环")
            return []

        return filtered_docs


def create_llm_chain():
    """初始化 LLM、记忆和提示模板"""

    # 创建问题重写模板
    logger.info("初始化 rag prompt 模板...")

    # 使用langchain集成智谱 AI,可更换为其他模型
    logger.info("初始化 LLM 模型...")
    # 智谱 AI
    # llm = ChatOpenAI(
    #     temperature=0.7,
    #     model='glm-4-plus',
    #     openai_api_key=os.getenv("ZHIPU_API_KEY"),
    #     openai_api_base="https://open.bigmodel.cn/api/paas/v4/"
    # )

    # 混元 API
    llm = ChatOpenAI(
        temperature=0.7,
        model='hunyuan-turbos-latest',
        openai_api_key=os.getenv("DASHSCOPE_API_KEY"),
        openai_api_base="https://api.hunyuan.cloud.tencent.com/v1",
        extra_body={
            "enable_enhancement": True,
        }
    )

    logger.info("初始化问题改写 prompt 模板...")
    chat_prompt = PromptTemplate(
        input_variables=["context", "chat_history", "question"],
        template="""你是一个专业且严谨的企业知识问答助手。

你的任务是基于企业知识库中的信息，准确并清晰地回答用户提出的问题。  
请遵循以下规则：

1. 只依据提供的知识内容 {context} 作答，不要编造信息。
2. 如果 {context} 中没有足够信息，请直接回答：「抱歉，知识库中没有找到相关信息」。
3. 结合上下文历史对话 {chat_history}，理解用户当前问题 {question}，保持回答简洁明了。
4. 回答中如涉及多个要点，可使用项目符号 (•) 或编号分点表达。

---  
【知识库信息】  
{context}

---  
【历史对话】  
{chat_history}

---  
【用户问题】  
{question}

请给出你的专业回答："""
    )

    memory = ConversationBufferWindowMemory(
        memory_key="chat_history",
        return_messages=True,
        input_key="question",
        output_key="answer",
        k=5,
        human_prefix="用户",
        ai_prefix="助手",
    )

    return llm, memory, chat_prompt


def process_query(query: str, chain):
    """处理用户查询并生成回答"""
    # 检查输入
    if not query or not query.strip():
        return "请输入有效的问题"

    # 调用链生成回答(Langchain 自动检索 + 历史 + 拼接 + 生成)
    try:
        # 模型生成
        logger.info("开始生成回答...")
        response = chain.invoke({"question": query})
        """
        {'question': '天宽是谁?', 'chat_history': [], 'answer': '天宽是华为生态伙伴中运营算力中心数量最多、理念最新、能力最强的AI运营商。他们在AI运营领域具有显著的优势，包括对政策的深入理解和利用、强大的技术能力以及广泛的生态链接能力。天宽不仅在华东片区的算力商业市场占据了英伟达的主要市场份额，还被多个地市的AICC算力中心邀请去做运营管理。', 'source_documents': [Document(metadata={'document_source': '公司能力交流口径-2025:02定稿版.docx', 'partment': '', 'role': '', 'doc_id': '03ff5429-4ad2-3d69-6f47-1caa4113c3e1', 'title': '一、AI运营\n\n天宽是华为生态伙伴中运营算力中心数量最多，理念最新，能力最强的AI运营商\n\n杭州AICC的运营效果目前在国内是属于第一梯队（北京、深圳、杭州），杭州市政府很典型的小政府、大市场，主要依靠市场自身的运作机制，北京、深圳在政府行业背书有天然的优势，且政府参与程度较深。像第二梯队里的天津、宁波等算力中心，算力全免费，杭州AICC是收费的，且费用不低；（杭州910B租赁费11000/p每月）\n\n天津、山东、福州等地市的AICC算力中心，都邀请天宽去做运营管理\n\n在华东片区的算力商业市场，占据了英伟达的主要市场份额（这部分要注意交流场景，选择性介绍这块的能力）。\n\n算力运营优势：\n\n对于政策的理解和利用：首先，天宽深入研究和解读政策文件（政府、华为等），充分利用政策帮助客户和伙伴降本增效，提高品牌知名度；\n\n技术能力：一方面我们联合客户和伙伴连续几年申请省、市国产AI相关的重大科技项目；另一方面我们有专业的技术专家团队，保障模型在国产化算力平台上的落地。\n\n生态链接能力：我们持续发展了一批国产化算力生态的用户，包括模型企业、高校、运营商等。', 'id': 0, 'source_type': 'vector'}, page_content='一、AI运营\n\n天宽是华为生态伙伴中运营算力中心数量最多，理念最新，能力最强的AI运营商\n\n杭州AICC的运营效果目前在国内是属于第一梯队（北京、深圳、杭州），杭州市政府很典型的小政府、大市场，主要依靠市场自身的运作机制，北京、深圳在政府行业背书有天然的优势，且政府参与程度较深。像第二梯队里的天津、宁波等算力中心，算力全免费，杭州AICC是收费的，且费用不低；（杭州910B租赁费11000/p每月）\n\n天津、山东、福州等地市的AICC算力中心，都邀请天宽去做运营管理\n\n在华东片区的算力商业市场，占据了英伟达的主要市场份额（这部分要注意交流场景，选择性介绍这块的能力）。\n\n算力运营优势：\n\n对于政策的理解和利用：首先，天宽深入研究和解读政策文件（政府、华为等），充分利用政策帮助客户和伙伴降本增效，提高品牌知名度；\n\n技术能力：一方面我们联合客户和伙伴连续几年申请省、市国产AI相关的重大科技项目；另一方面我们有专业的技术专家团队，保障模型在国产化算力平台上的落地。\n\n生态链接能力：我们持续发展了一批国产化算力生态的用户，包括模型企业、高校、运营商等。')]}
        """
        return response["answer"].strip()
    except Exception as e:
        logger.error(f"生成回答失败: {e}")
        return "生成回答失败, 请稍后再试"


def show_chat_history(memory):
    """打印历史对话"""
    logger.info("历史对话内容:")
    if not memory.chat_memory.messages:
        logger.info("暂无历史对话")
        return

    for i, message in enumerate(memory.chat_memory.messages, 1):
        logger.info(f"{i}. {message.type}: {message.content}")


def main():
    """主程序入口"""
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
        # text_field="summary_text", # 不传, Document.page_content 为空, 使用seg_id 通过 mysql 提取原文内容.
    )

    # 初始化 BM25 检索器
    bm25_retriever = init_bm25_retriever(db)

    # 初始化混合检索器并添加日志
    logger.info("开始初始化混合检索器...")
    custom_retriever = CustomRetriever(vectorstore, bm25_retriever)
    logger.info("混合检索器初始化完成")

    # 初始化 LLM 对话链
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

    # 测试查询
    while True:
        try:
            query = input("请输入你的问题: ")
            if not query or not query.strip():
                logger.info("输入为空, 跳过本次查询")
                continue

            # 打印历史对话
            if query.lower() in ["history", "h"]:
                show_chat_history(memory)
                continue

            response = process_query(query, chain)
            logger.info(f"回答: {response}")

        except KeyboardInterrupt:
            logger.info("\n再见!")
            break
        except Exception as e:
            logger.error(f"处理查询时发生错误: {e}")


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
