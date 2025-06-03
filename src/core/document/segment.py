"""文档内容分块"""

import hashlib
import json
from typing import List, Dict, Optional
from datetime import datetime
from langchain.text_splitter import RecursiveCharacterTextSplitter

from src.utils.common.logger import logger
from src.utils.common.args_validator import Validator
from src.core.llm.extract_summary import extract_table_summary, extract_text_summary
from src.database.mysql.operations import ChunkOperation
from src.database.milvus.operations import MilvusOperation
from src.core.embedding.embedder import embed_text


def generate_segment_id(content: str) -> str:
    """生成片段ID

    Args:
        content (str): 片段内容

    Returns:
        str: 片段ID（SHA256哈希值）
    """
    return hashlib.sha256(content.encode()).hexdigest()


def


def segment_text_content(document_text: str, doc_id: str, principal_ids: List[str], document_name: str) -> List[Dict]:
    """分块文本内容

    Args:
        document_text (str): 文本内容, json 格式的字符串
        doc_id (str): 文档ID
        principal_ids (List[str]): 权限ID列表
        document_name (str): 文档名称

    Returns:
        List[Dict]: 分块结果列表
    """
    # 参数验证
    Validator.validate_not_empty(document_text, "document_text")
    Validator.validate_type(document_text, str, "document_text")
    Validator.validate_doc_id(doc_id)
    Validator.validate_list_not_empty(principal_ids, "principal_ids")

    # 初始化分块器
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        length_function=len,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]
    )

    # 遍历处理每一页的内容
    for page_idx, page_contents in enumerate(json.loads(document_text)):
        # 如果是文本
        text_list = []
        for content in page_contents:
            # 累积文本内容
            if content["type"] == "text":
                text_list.append(content["text"].strip())
                continue
            else:
                # 非文本内容时，处理已累积的文本内容
                texts = "".join(text_list).strip()
                # 对文本分块
                chunks = text_splitter.split_text(texts)
                # 生成各分块的片段 id
                for chunk in chunks:
                    segment_id = generate_segment_id(chunk)  # 片段 ID
                    vector = embed_text(chunk)  # 片段向量
                    # 构建milvus存储结果
                    milvus_res = {
                        "vector": vector,
                        "segment_id": segment_id,
                        "doc_id": doc_id,
                        "document_name":document_name,
                        "summary_text": chunk,
                        "type": "text",
                        "page_idx": page_idx,
                        "principal_ids": json.dumps(principal_ids),
                        "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "metadata": {}
                    }
                    # 构建 MySQL 存储结果
                    mysql_res = {
                        "segment_text": json.dumps(milvus_res),
                        "doc_id": doc_id,
                        "segment_id": segment_id
                    }

        try:

            # 分块
            chunks = text_splitter.split_text(text)
            logger.info(f"文本分块完成，共 {len(chunks)} 块")

            # 处理每个分块
            results = []
            for chunk in chunks:
                # 生成片段ID
                segment_id = generate_segment_id(chunk)

                # 生成摘要
                summary = extract_text_summary(chunk)

                # 生成向量
                vector = get_embedding(chunk)

                # 构建结果
                # result = {
                #     "vector": vector,
                #     "segment_id": segment_id,
                #     "doc_id": doc_id,
                #     "document_name": document_name,
                #     "summary_text": summary,
                #     "type": "text",
                #     "page_idx": page_idx,
                #     "principal_ids": json.dumps(principal_ids),
                #     "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                #     "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                #     "metadata": {}
                # }
                results.append(result)

            return results
        except Exception as e:
            logger.error(f"文本分块失败: {e}")
            raise

    def segment_table_content(table_html: str, page_idx: int, doc_id: str, document_name: str, principal_ids: List[str],
                              img_path: str = "", caption: str = "", footnote: str = "") -> List[Dict]:
        """分块表格内容

        Args:
            table_html (str): HTML格式的表格
            page_idx (int): 页码
            doc_id (str): 文档ID
            document_name (str): 文档名称
            principal_ids (List[str]): 权限ID列表
            img_path (str, optional): 图片路径. Defaults to "".
            caption (str, optional): 图片说明. Defaults to "".
            footnote (str, optional): 图片脚注. Defaults to "".

        Returns:
            List[Dict]: 分块结果列表
        """
        # 参数验证
        Validator.validate_not_empty(table_html, "table_html")
        Validator.validate_type(table_html, str, "table_html")
        Validator.validate_doc_id(doc_id)
        Validator.validate_list_not_empty(principal_ids, "principal_ids")

        try:
            # 计算表格字符长度
            table_token_length = len(table_html)

            # 生成片段ID
            segment_id = generate_segment_id(table_html)

            # 生成摘要
            summary = extract_table_summary(table_html)

            # 生成向量
            vector = get_embedding(table_html)

            # 构建元数据
            metadata = {
                "table_raw": table_html,
                "table_token_length": table_token_length,
                "img_path": img_path,
                "caption": caption,
                "footnote": footnote
            }

            # 根据表格长度决定是否分块
            if table_token_length > 1000:
                # 分块处理
                results = []

                # 添加母表
                parent_result = {
                    "vector": vector,
                    "segment_id": segment_id,
                    "doc_id": doc_id,
                    "document_name": document_name,
                    "summary_text": summary["summary"],
                    "type": "table",
                    "page_idx": page_idx,
                    "principal_ids": json.dumps(principal_ids),
                    "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "metadata": metadata
                }
                results.append(parent_result)

                # 添加子表
                child_result = {
                    "vector": vector,
                    "segment_id": generate_segment_id(f"{segment_id}_chunk"),
                    "doc_id": doc_id,
                    "document_name": document_name,
                    "type": "chunk_table",
                    "page_idx": page_idx,
                    "principal_ids": json.dumps(principal_ids),
                    "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "metadata": {
                        **metadata,
                        "raw_table_segment_id": segment_id
                    }
                }
                results.append(child_result)

                return results
            else:
                # 不分块处理
                result = {
                    "vector": vector,
                    "segment_id": segment_id,
                    "doc_id": doc_id,
                    "document_name": document_name,
                    "summary_text": summary["summary"],
                    "type": "table",
                    "page_idx": page_idx,
                    "principal_ids": json.dumps(principal_ids),
                    "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "metadata": metadata
                }
                return [result]
        except Exception as e:
            logger.error(f"表格分块失败: {e}")
            raise

    def segment_image_content(img_path: str, caption: str, footnote: str, page_idx: int, doc_id: str,
                              document_name: str, principal_ids: List[str]) -> Dict:
        """分块图片内容

        Args:
            img_path (str): 图片路径
            caption (str): 图片说明
            footnote (str): 图片脚注
            page_idx (int): 页码
            doc_id (str): 文档ID
            document_name (str): 文档名称
            principal_ids (List[str]): 权限ID列表

        Returns:
            Dict: 分块结果
        """
        # 参数验证
        Validator.validate_not_empty(img_path, "img_path")
        Validator.validate_type(img_path, str, "img_path")
        Validator.validate_doc_id(doc_id)
        Validator.validate_list_not_empty(principal_ids, "principal_ids")

        try:
            # 处理标题
            if len(caption) > 500:
                summary = extract_text_summary(caption)
            else:
                summary = caption

            # 生成片段ID
            segment_id = generate_segment_id(f"{img_path}{caption}{footnote}")

            # 生成向量
            vector = get_embedding(caption)

            # 构建结果
            result = {
                "vector": vector,
                "segment_id": segment_id,
                "doc_id": doc_id,
                "document_name": document_name,
                "summary_text": summary,
                "type": "image",
                "page_idx": page_idx,
                "principal_ids": json.dumps(principal_ids),
                "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "metadata": {
                    "img_path": img_path,
                    "caption": caption,
                    "footnote": footnote
                }
            }
            return result
        except Exception as e:
            logger.error(f"图片分块失败: {e}")
            raise

    def save_segments(segments: List[Dict]) -> bool:
        """保存分块结果

        Args:
            segments (List[Dict]): 分块结果列表

        Returns:
            bool: 保存是否成功
        """
        try:
            # 参数验证
            Validator.validate_list_not_empty(segments, "segments")

            # 保存到 MySQL
            with ChunkOperation() as chunk_op:
                for segment in segments:
                    chunk_info = {
                        "segment_text": json.dumps(segment),
                        "doc_id": segment["doc_id"],
                        "segment_id": segment["segment_id"]
                    }
                    chunk_op.insert(chunk_info)

            # 保存到 Milvus
            with MilvusOperation() as milvus_op:
                milvus_op.insert_vectors(segments)

            logger.info(f"成功保存 {len(segments)} 个分块")
            return True
        except Exception as e:
            logger.error(f"保存分块失败: {e}")
            return False
