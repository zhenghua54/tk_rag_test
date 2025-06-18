""" 文件分块 - langchain 实现 备份"""

import os
import hashlib
from typing import List, Dict, Any
from databases.milvus.connection import MilvusDB
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

from utils.common.logger import logger



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


def get_file_content(doc_path: str) -> str:
    """根据文件类型加载文件内容
    
    Args:
        doc_path: 文件路径

    Returns:
        content: 文件内容
    """
    file_ext = os.path.splitext(doc_path)[1].lower()

    try:
        if file_ext == '.pdf':
            loader = PyPDFLoader(doc_path)
            pages = loader.load()
            return "\n".join([page.page_content for page in pages])
        elif file_ext == '.docx':
            loader = Docx2txtLoader(doc_path)
            return loader.load()[0].page_content
        elif file_ext == '.txt':
            loader = TextLoader(doc_path, encoding='utf-8')
            return loader.load()[0].page_content
        else:
            raise ValueError(f"不支持的文件类型: {file_ext}")
    except Exception as e:
        print(f"读取文件 {doc_path} 时出错: {str(e)}")
        return ""


def get_text_splitter(doc_path: str) -> Any:
    """根据文件类型返回对应的分块器
    
    Args:
        doc_path: 文件路径

    Returns:
        text_splitter: 分块器
    """
    file_ext = os.path.splitext(doc_path)[1].lower()

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


def get_current_max_id(milvus_db: MilvusDB) -> int:
    """获取当前数据库中的最大 ID
    
    Args:
        milvus_db: 向量库连接

    Returns:
        current_id: 当前最大 ID
    """
    try:
        result = milvus_db.client.query(
            collection_name=milvus_db.collection_name,
            filter="id >= 0",
            output_fields=["id"],
            limit=1,
            order_by=[("id", "desc")]
        )
        return result[0]["id"] if result else -1
    except Exception as e:
        logger.error(f"获取最大 ID 时出错: {str(e)}")
        return -1


def process_file(merge_json_doc_path: str) -> List[Dict[str, Any]]:
    """处理单个文件并返回分块结果
    
    Args:
        merge_json_doc_path: 最终处理完的 json 文件路径

    Returns:
        results: 分块结果
    """

    # 获取文件内容
    content = get_file_content(merge_json_doc_path)
    if not content:
        return []

    # 为整个文档生成 UUID
    doc_id = generate_doc_id(content)

    # 获取对应的分块器
    text_splitter = get_text_splitter(merge_json_doc_path)

    # 分块
    chunks = text_splitter.split_text(content)

    # 准备结果
    results = []
    # 获取当前最大 ID 并加 1 作为起始 ID
    current_id = get_current_max_id() + 1

    for chunk in chunks:
        results.append({
            'id': current_id,
            'text_chunk': chunk,
            'document_source': os.path.basename(merge_json_doc_path),
            'partment': '',  # 可以根据需要设置
            'role': '',  # 可以根据需要设置
            'doc_id': doc_id  # 所有分块共享同一个 doc_id
        })
        current_id += 1

    print(f"文件 {merge_json_doc_path} 被分成 {len(chunks)} 个块")
    return results


def process_directory(directory_path: str) -> List[Dict[str, Any]]:
    """处理目录下的所有支持的文件
    
    Args:
        directory_path: 目录路径

    Returns:
        all_results: 所有分块结果
    """
    all_results = []
    supported_extensions = {'.pdf', '.docx', '.txt'}

    for root, _, files in os.walk(directory_path):
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.splitext(file)[1].lower() in supported_extensions:
                results = process_file(file_path)
                all_results.extend(results)

    return all_results


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
