""" 固定长度文件分块 """

import os
import uuid
import hashlib
import pandas as pd
from typing import List, Dict, Any

# 使用 langchain 的文本分块器
from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter
)
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader
)

from src.utils.common.logger import logger


def generate_doc_id(text: str) -> str:
    """根据文本内容生成唯一的哈希值
    
    Args:
        text: 文本内容

    Returns:
        doc_id: 64位哈希值
    """
    # 使用 SHA-256 生成哈希值
    doc_id = hashlib.sha256(text.encode('utf-8')).hexdigest()
    return doc_id


def get_text_splitter(file_ext: str) -> Any:
    """根据文件类型返回对应的分块器
    
    Args:
        file_ext: 文件扩展名

    Returns:
        text_splitter: 分块器
    """

    if file_ext == '.pdf':
        # PDF 文件使用较小的块大小，因为通常包含更多格式化内容
        return RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]
        )
    elif file_ext == '.docx':
        # Word 文件使用较大的块大小，因为通常包含更多连续文本
        return RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]
        )
    elif file_ext == '.txt':
        # 纯文本文件使用标准分块器
        return CharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100,
            separator="\n"
        )
    else:
        # 默认使用递归字符分块器
        return RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]
        )


def segment_content(model: SentenceTransformer, file_content: str) -> Dict[str, List[str]]: 
    """文档内容切分, 按照元素切割, 返回切分后的文本列表
    
    Args:
        file_content: 文件内容
            特殊标记符:
                \n===TABLE_START===\n, \n===TABLE_END===\n, 
                \n===IMAGE_START===\n, \n===IMAGE_END===\n, 
                \n===PAGE_{page_idx}_START===\n

    Returns:
        chunks: 包含文档ID和切分后的文本块列表的字典
    """
    # 初始化结果字典
    chunks = {}
    
    # 获取文档ID
    doc_id = generate_doc_id(file_content)
    chunks['doc_id'] = doc_id
    chunks['chunks'] = []
    
    # 获取默认的分块器
    text_splitter = get_text_splitter(".txt")
    
    # 当前页码
    current_page = 0
    
    # 定义正则表达式模式
    import re
    pattern = re.compile(
        r"\n===PAGE_(\d+)_START===\n" +
        r"|(?P<table>\n===TABLE_START===\n(.*?)\n===TABLE_END===\n)" +
        r"|(?P<image>\n===IMAGE_START===\n(.*?)\n===IMAGE_END===\n)",
        flags=re.DOTALL
    )
    
    # 按顺序处理所有匹配项
    pos = 0
    for match in pattern.finditer(file_content):
        start, end = match.span()
        
        # 提取到的元素开头不是上一个元素的结尾时,说明存在文本内容, 需要切分
        if start > pos:
            raw_text = file_content[pos:start].strip()
            if raw_text:
                for chunk in text_splitter.split_text(raw_text):
                    segment_id = generate_doc_id(chunk)
                    chunks['chunks'].append({
                        "segment_id": segment_id,
                        "content": chunk,
                        "type": "text",
                        "page": current_page
                    })

        # 处理匹配到的内容
        if match.group(1):  # 页码匹配
            current_page = int(match.group(1))
        elif match.group("table"):
            table_content = match.group(3).strip()
            segment_id = generate_doc_id(table_content)
            chunks['chunks'].append({
                "segment_id": segment_id,
                "content": table_content,
                "type": "table",
                "page": current_page
            })
            
        elif match.group("image"):
            image_content = match.group(5).strip()
            segment_id = generate_doc_id(image_content)
            chunks['chunks'].append({
                "segment_id": segment_id,
                "content": image_content,
                "type": "image",
                "page": current_page
            })

        pos = end

    # 处理最后剩余的正文
    if pos < len(file_content):
        raw_text = file_content[pos:].strip()
        if raw_text:
            for chunk in text_splitter.split_text(raw_text):
                segment_id = generate_doc_id(chunk)
                chunks['chunks'].append({
                    "segment_id": segment_id,
                    "content": chunk,
                    "type": "text",
                    "page": current_page
                })
    
    return chunks

def segment_chunk_content(content_list: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """切分文本, 返回切分后的文本列表
    
    Args:
        content_list: 文档内容列表, 按照元素粗切后的
        
        
    """
    # 提取元素块
    content_chunk = content_list[1]['chunks']
    
    # 对表格内容
    

if __name__ == "__main__":
    
    # 初始化向量库连接
    milvus_db = MilvusDB()
    milvus_db.init_database()

    # 加载集合 （如果已经加载过，则不需要加载）
    try:
        milvus_db.client.load_collection(milvus_db.collection_name)
        print(f"成功加载集合: {milvus_db.collection_name}")
    except Exception as e:
        print(f"加载集合时出错: {str(e)}")
    
    
    # 示例用法
    directory_path = "/Users/jason/PycharmProjects/tk_rag/data/raw"
    all_results = process_directory(directory_path)
    print(all_results)
    exit()

    # 保存结果
    output_path = "processed_chunks.csv"
    df.to_csv(output_path, index=False)
    print(f"处理完成，结果已保存到 {output_path}")
    print(f"总共处理了 {len(df)} 个文本块")
    print(f"唯一文档数量：{df['doc_id'].nunique()}")
