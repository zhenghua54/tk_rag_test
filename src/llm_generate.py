"""使用 langchain+LLM 完成 RAG 生成内容"""

import sys

sys.path.append("/Users/jason/PycharmProjects/tk_rag")

from sympy import content
from transformers.models.auto.modeling_auto import AutoModelForCausalLM
from transformers.models.auto.tokenization_auto import AutoTokenizer
from transformers.pipelines import pipeline
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_milvus import Milvus
from langchain_huggingface import HuggingFacePipeline
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory, ConversationBufferWindowMemory
from langchain.prompts import (
    PromptTemplate,
    MessagesPlaceholder,
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain.schema import BaseRetriever, Document
from langchain_core.messages import SystemMessage, HumanMessage
from typing import List

from config import Config, logger
from src.query_process import search_documents, init_bm25_retriever
from src.database.build_milvus_db import MilvusDB


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

    def _get_relevant_documents(
        self, query: str, k: int = 50, top_k: int = 5, score_threshold: float = 0.5
    ) -> List[Document]:

        # 防止空 query 跳过检索的问题
        if not query or not query.strip():
            logger.info("检索器收到空 query,跳过检索")
            return []

        # 使用向量检索
        search_results = search_documents(
            query=query,
            vectorstore=self.vectorstore,
            bm25_retriever=self.bm25_retriever,
            k=k,
            top_k=top_k,
        )
        # 只保留分数 >= 阈值的文档
        filtered_docs = [
            doc for doc, score in search_results if score >= score_threshold
        ]

        return filtered_docs


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
        temperature=0.3,
        top_p=0.95,
        repetition_penalty=1.15,
        do_sample=True,
        max_new_tokens=2048,  # 最大生成 token 数
    )

    # 创建 Langchain 的 LLM 包装器
    llm = HuggingFacePipeline(
        pipeline=pipe,
        model_kwargs={"max_new_tokens": 2048, "stream": True},
    )

    # 创建对话记忆:使用窗口剪裁机制
    memory = ConversationBufferWindowMemory(
        memory_key="chat_history",
        return_messages=True,
        output_key="answer",
        input_key="question",
        k=5,  # 只保留最后5条对话
        human_prefix="用户",
        ai_prefix="助手",
    )

    # 创建提示词模板
    chat_prompt = PromptTemplate(
        input_variables=["context", "chat_history", "question"],
        template="""你是一个专业的企业知识问答助手. 基于以下信息回答问题.如果无法从信息中找到答案,请直接回答"抱歉,现有知识库中没有相关信息."

    当前检索到的信息:
    {context}

    历史对话:
    {chat_history}

    最新问题: {question}

    回答:""",
    )

    # 创建问题重写模板
    condense_question_prompt = PromptTemplate(
        template="""
    基于以下对话历史和当前问题,重写为独立问题,只输出问题,不要多余解释,不要复读提示词.

    对话历史:
    {chat_history}

    当前问题:
    {question}

    重写后的问题:""",
        input_variables=["chat_history", "question"],
    )
    return llm, memory, chat_prompt, condense_question_prompt


def process_query(
    query: str,
    vectorstore: Milvus,
    bm25_retriever,
    llm,
    memory,
    prompt,
    condense_question_prompt,
    custom_retriever,
    chain,
):
    """处理用户查询并生成回答"""
    # 检查输入
    if not query or not query.strip():
        return "请输入有效的问题"

    # 调用链生成回答(Langchain 自动检索 + 历史 + 拼接 + 生成)
    try:
        # 获取回答
        logger.info(f"开始生成回答...")
        # 模型生成
        response = chain.invoke({"question": query})

        return response["answer"].strip()
    except Exception as e:
        logger.error(f"生成回答失败: {e}")
        return "生成回答失败,请稍后再试"


def show_chat_history(memory):
    """显示历史对话内容"""
    logger.info("历史对话内容:")
    if not memory.chat_memory.messages:
        logger.info("暂无历史对话")
        return

    for i, message in enumerate(memory.chat_memory.messages, 1):
        logger.info(f"{i}. {message.type}: {message.content}")


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

    # 初始化混合检索器并添加日志
    logger.info("开始初始化混合检索器...")
    custom_retriever = CustomRetriever(vectorstore, bm25_retriever)
    logger.info("混合检索器初始化完成")

    # 初始化 LLM 对话链
    llm, memory, chat_prompt, condense_question_prompt = create_llm_chain()

    # 创建 langchain 对话链
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=custom_retriever,
        memory=memory,
        combine_docs_chain_kwargs={"prompt": chat_prompt},
        condense_question_prompt=condense_question_prompt,  # query 重写模板
        return_source_documents=True,
        verbose=False,  # 设置日志为 False,避免日志过多
    )

    # 测试查询
    while True:
        try:
            query = input("请输入你的问题: ")
            if not query or not query.strip():
                logger.info("输入为空,跳过本次查询")
                continue

            # 显示历史对话
            if query.lower() in ["history", "h"]:
                show_chat_history(memory)
                continue

            response = process_query(
                query,
                vectorstore,
                bm25_retriever,
                llm,
                memory,
                chat_prompt,
                condense_question_prompt,
                custom_retriever,  # 初始化后的检索器
                chain,
            )
            logger.info(f"回答: {response}")

            # 更新历史对话
            memory.save_context({"question": query}, {"answer": response})

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
