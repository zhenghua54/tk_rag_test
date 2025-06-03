"""文档内容分块"""

import hashlib
import json
from typing import List, Dict, Optional
from datetime import datetime
from langchain.text_splitter import RecursiveCharacterTextSplitter

from src.core.document.processor import html_table_to_markdown
from src.utils.common.logger import logger
from src.utils.common.args_validator import Validator
from src.core.llm.extract_summary import extract_table_summary, extract_text_summary
from src.database.mysql.operations import ChunkOperation
from src.database.milvus.operations import VectorOperation
from src.core.embedding.embedder import embed_text
from config.settings import Config


def generate_segment_id(content: str) -> str:
    """生成片段ID

    Args:
        content (str): 片段内容

    Returns:
        str: 片段ID（SHA256哈希值）
    """
    # 如果输入是列表，将其转换为字符串
    if isinstance(content, list):
        content = " ".join(str(item) for item in content)
    # 确保输入是字符串类型
    if not isinstance(content, str):
        content = str(content)
    return hashlib.sha256(content.encode()).hexdigest()


def segment_text_content(doc_id: str, document_name: str, page_content_dict: dict, principal_ids: List[str]):
    """分块文本内容

    Args:
        doc_id (str): 文档ID
        document_name (str): 文档名称
        page_content_dict (dict[idx:[content]]): 文本内容列表，每条记录为单页内容字典
        principal_ids (List[str]): 权限ID列表

    Returns:
        List[Dict]: 分块结果列表
    """
    logger.info(f"开始处理文档 {document_name} (doc_id: {doc_id}) 的分块...")
    
    # 参数验证
    Validator.validate_not_empty(document_name, "document_name")
    Validator.validate_doc_id(doc_id)
    Validator.validate_type(page_content_dict, dict, "page_content_dict")
    Validator.validate_list_not_empty(principal_ids, "principal_ids")

    # 初始化分块器
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        length_function=len,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]
    )
    logger.info("文本分块器初始化完成")

    # 分批处理结果
    batch_size = Config.SEGMENT_CONFIG["batch_size"]  # 每批处理的记录数
    milvus_batch = []
    mysql_batch = []

    # 遍历处理每一页的内容
    total_pages = len(page_content_dict)
    logger.info(f"开始处理 {total_pages} 页内容...")
    
    for page_idx, page_contents in page_content_dict.items():
        logger.info(f"正在处理第 {page_idx} 页内容...")

        # 如果是文本
        text_list = []
        for content in page_contents:
            # 累积文本内容
            if content["type"] == "text":
                text_list.append(content["text"].strip())
                continue
            elif content["type"] == "table":
                # 非文本内容时，处理已累积的文本内容
                texts = "".join(text_list).strip()  # 提取积累的文本
                text_list = []  # 置空存储
                
                # 对文本分块
                text_chunks = text_splitter.split_text(texts)
                logger.info(f"文本内容分块完成，共 {len(text_chunks) + 1} 个块")
                
                # 分批处理文本块
                for i in range(0, len(text_chunks), batch_size):
                    batch_chunks = text_chunks[i:i + batch_size]
                    
                    # 生成各分块的片段 id 和向量
                    for chunk in batch_chunks:
                        segment_id = generate_segment_id(chunk)  # 片段 ID
                        vector = embed_text(chunk)  # 片段向量
                        logger.debug(f"生成文本片段向量，segment_id: {segment_id}")
                    
                        # 构建milvus存储结果
                        text_milvus_res = {
                            "vector": vector,
                            "segment_id": segment_id,
                            "doc_id": doc_id,
                            "document_name": document_name,
                            "summary_text": chunk,
                            "type": "text",
                            "page_idx": int(page_idx),
                            "principal_ids": principal_ids,
                            "create_time": "",  # 插入数据时更新
                            "update_time": "",  # 插入数据时更新
                            "metadata": {}
                        }
                        milvus_batch.append(text_milvus_res)

                        # 构建 MySQL 存储结果
                        text_mysql_res = {
                            "segment_text": str(chunk),
                            "doc_id": doc_id,
                            "segment_id": segment_id,
                            "parent_segment_id": None,
                        }
                        mysql_batch.append(text_mysql_res)

                    # 当批次达到指定大小时，保存到数据库
                    if len(milvus_batch) >= batch_size:
                        save_batch(milvus_batch, mysql_batch)
                        milvus_batch = []
                        mysql_batch = []
                        logger.info(f"已保存 {batch_size} 条记录")

                # 处理表格内容
                logger.info(f"处理第 {page_idx} 页的表格内容...")

                # 判断表格内容是否为空
                if not content.get('table_body'):
                    logger.warning(f"表格内容为空: {content}")
                    continue

                # 1. 表格解析为markdown后，长度 < 1000
                table_html = content['table_body'].strip()
                table_markdown = html_table_to_markdown(table_html)
                logger.info(f"表格转换为 Markdown 格式，长度: {len(table_markdown)}")
                
                if len(table_markdown) > 1000:
                    logger.info("表格内容较长，进行分块处理...")
                    # 保存母表信息：
                    table_table_vector = embed_text(content['table_summary'])
                    parent_segment_id = generate_segment_id(content["table_body"])
                    logger.debug(f"生成母表向量，parent_segment_id: {parent_segment_id}")
                    
                    parent_milvus_res = {
                        "vector": table_table_vector,
                        "segment_id": parent_segment_id,
                        "doc_id": doc_id,
                        "document_name": document_name,
                        "summary_text": content['table_summary'],
                        "type": "parent_table",
                        "page_idx": int(page_idx),
                        "principal_ids": principal_ids,
                        "create_time": "",  # 插入数据时更新
                        "update_time": "",  # 插入数据时更新
                        "metadata": {
                            "table_raw": table_markdown,
                            "table_token_length": len(table_markdown),
                            "img_path": content['img_path'],
                            "caption": content['table_caption'],
                            "footnote": content['table_footnote'],
                        }
                    }
                    milvus_batch.append(parent_milvus_res)
                    table_mysql_res = {
                        "segment_text": str(table_html),
                        "doc_id": doc_id,
                        "segment_id": parent_segment_id,
                        "parent_segment_id": None
                    }
                    mysql_batch.append(table_mysql_res)

                    # 处理子表信息: 将markdown格式的内容送入切块
                    sub_table_chunks = text_splitter.split_text(table_markdown)
                    logger.info(f"表格分块完成，共 {len(sub_table_chunks)} 个子块")
                    
                    for table_segment in sub_table_chunks:
                        sub_table_vector = embed_text(table_segment)
                        sub_segment_id = generate_segment_id(table_segment)
                        logger.debug(f"生成子表向量，sub_segment_id: {sub_segment_id}")
                        
                        # 构建子表信息
                        sub_milvus_res = {
                            "vector": sub_table_vector,
                            "segment_id": sub_segment_id,
                            "doc_id": doc_id,
                            "document_name": document_name,
                            "summary_text": "",
                            "type": "sub_table",
                            "page_idx": int(page_idx),
                            "principal_ids": principal_ids,
                            "create_time": "",  # 插入数据时更新
                            "update_time": "",  # 插入数据时更新
                            "metadata": {
                                "table_raw": table_segment,
                                "raw_table_segment_id": parent_segment_id,
                                "table_token_length": len(table_segment),
                            }
                        }
                        milvus_batch.append(sub_milvus_res)
                        sub_mysql_res = {
                            "segment_text": str(table_segment),
                            "doc_id": doc_id,
                            "segment_id": sub_segment_id,
                            "parent_segment_id": parent_segment_id,
                        }
                        mysql_batch.append(sub_mysql_res)
                else:
                    logger.info("表格内容较短，直接处理...")
                    # 表格长度小于1000，正常进行分块
                    table_vector = embed_text(table_markdown)
                    table_segment_id = generate_segment_id(content["table_body"])
                    logger.debug(f"生成表格向量，table_segment_id: {table_segment_id}")
                    
                    table_milvus_res = {
                        "vector": table_vector,
                        "segment_id": table_segment_id,
                        "doc_id": doc_id,
                        "document_name": document_name,
                        "summary_text": content['table_summary'],
                        "type": "table",
                        "page_idx": int(page_idx),
                        "principal_ids": principal_ids,
                        "create_time": "",  # 插入数据时更新
                        "update_time": "",  # 插入数据时更新
                        "metadata": {
                            "table_raw": table_markdown,
                            "table_token_length": len(table_markdown),
                            "img_path": content['img_path'],
                            "caption": content['table_caption'],
                            "footnote": content['table_footnote'],
                        }
                    }
                    milvus_batch.append(table_milvus_res)
                    table_mysql_res = {
                        "segment_text": str(table_html),
                        "doc_id": doc_id,
                        "segment_id": table_segment_id,
                        "parent_segment_id": None,
                    }
                    mysql_batch.append(table_mysql_res)

            elif content["type"] == "image":
                # 非文本内容时，处理已累积的文本内容
                texts = "".join(text_list).strip()  # 提取积累的文本
                text_list = []  # 置空存储
                
                # 对文本分块
                text_chunks = text_splitter.split_text(texts)
                logger.info(f"文本内容分块完成，共 {len(text_chunks) + 1} 个块")
                
                # 分批处理文本块
                for i in range(0, len(text_chunks), batch_size):
                    batch_chunks = text_chunks[i:i + batch_size]
                    
                    # 生成各分块的片段 id 和向量
                    for chunk in batch_chunks:
                        segment_id = generate_segment_id(chunk)  # 片段 ID
                        vector = embed_text(chunk)  # 片段向量
                        logger.debug(f"生成文本片段向量，segment_id: {segment_id}")
                    
                        # 构建milvus存储结果
                        text_milvus_res = {
                            "vector": vector,
                            "segment_id": segment_id,
                            "doc_id": doc_id,
                            "document_name": document_name,
                            "summary_text": chunk,
                            "type": "text",
                            "page_idx": int(page_idx),
                            "principal_ids": principal_ids,
                            "create_time": "",  # 插入数据时更新
                            "update_time": "",  # 插入数据时更新
                            "metadata": {}
                        }
                        milvus_batch.append(text_milvus_res)

                        # 构建 MySQL 存储结果
                        text_mysql_res = {
                            "segment_text": str(chunk),
                            "doc_id": doc_id,
                            "segment_id": segment_id,
                            "parent_segment_id": None,
                        }
                        mysql_batch.append(text_mysql_res)

                    # 当批次达到指定大小时，保存到数据库
                    if len(milvus_batch) >= batch_size:
                        save_batch(milvus_batch, mysql_batch)
                        milvus_batch = []
                        mysql_batch = []
                        logger.info(f"已保存 {batch_size} 条记录")
                
                
                # 处理图片
                # 判断图片内容是否为空
                if not content.get('img_path'):
                    logger.warning(f"图片内容为空: {content}")
                    continue

                logger.info(f"处理第 {page_idx} 页的图片内容...")
                image_title = content["img_caption"]    # 图片标题
                image_vector = embed_text(image_title)
                image_segment_id = generate_segment_id(image_title)
                logger.debug(f"生成图片向量，image_segment_id: {image_segment_id}")
                
                image_milvus_res = {
                    "vector": image_vector,
                    "segment_id": image_segment_id,
                    "doc_id": doc_id,
                    "document_name": document_name,
                    "summary_text": None,
                    "type": "image",
                    "page_idx": int(page_idx),
                    "principal_ids": principal_ids,
                    "create_time": "",  # 插入数据时更新
                    "update_time": "",  # 插入数据时更新
                    "metadata": {
                        "img_path": content['img_path'],
                        "caption": content['img_caption'],
                        "footnote": content['img_footnote'],
                    }
                }
                milvus_batch.append(image_milvus_res)
                img_segment_text = {"title":image_title,"img_path":content['img_path']}
                image_mysql_res = {
                    "segment_text": json.dumps(img_segment_text),
                    "doc_id": doc_id,
                    "segment_id": image_segment_id,
                    "parent_segment_id": None,
                }
                mysql_batch.append(image_mysql_res)
            else:
                logger.warning(f"元素未切块：{content}")

    # 保存剩余的批次
    if milvus_batch or mysql_batch:
        save_batch(milvus_batch, mysql_batch)
        logger.info(f"已保存剩余 {len(milvus_batch)} 条记录")
    
    logger.info(f"文档分块完成")
    return True


def save_batch(milvus_batch: List[Dict], mysql_batch: List[Dict]) -> bool:
    """保存一批数据到数据库
    
    Args:
        milvus_batch: Milvus 数据批次
        mysql_batch: MySQL 数据批次
        
    Returns:
        bool: 保存是否成功
    """
    try:
        # 保存到 MySQL
        with ChunkOperation() as chunk_op:
            for segment in mysql_batch:
                chunk_info = {
                    "segment_text": segment["segment_text"],
                    "doc_id": segment["doc_id"],
                    "segment_id": segment["segment_id"],
                    "parent_segment_id": segment["parent_segment_id"],
                }
                try:
                    # 尝试插入，如果失败则更新
                    chunk_op.insert(chunk_info)
                except Exception as e:
                    if "Duplicate entry" in str(e):
                        # 如果是重复记录，则更新
                        chunk_op.update_by_doc_id(segment["segment_id"], chunk_info)
                    else:
                        raise
        
        # 保存到 Milvus
        vector_op = VectorOperation()
        try:
            vector_op.insert_data(milvus_batch)
        finally:
            vector_op.close()
        
        return True
    except Exception as e:
        logger.error(f"保存批次数据失败: {str(e)}")
        raise
