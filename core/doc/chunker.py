"""文档内容分块"""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Union

from langchain.text_splitter import RecursiveCharacterTextSplitter

from config.global_config import GlobalConfig
from databases.elasticsearch.operations import ElasticsearchOperation
from databases.milvus.operations import VectorOperation
from databases.mysql.operations import ChunkOperation
from utils.converters import convert_html_to_markdown
from utils.file_ops import generate_seg_id, truncate_text
from utils.llm_utils import embedding_manager
from utils.log_utils import logger


def format_table_caption_footnote(value: Union[str, List]):
    """处理标题和脚注为列表或者空的问题"""
    if isinstance(value, str) and value.strip() is None:
        return None
    elif isinstance(value, list):
        return None if len(value) == 0 else ",".join(str(item) for item in value)
    return value


def segment_text_content(doc_id: str, doc_process_path: str, permission_ids: Union[str, list[str]],
                         request_id: str = None) -> bool:
    """分块文本内容

    Args:
        doc_id (str): 文档ID
        doc_process_path (str): 聚合处理后的文档，格式为 dict[idx:[content]]
        permission_ids (Union[str, list[str]]): 权限ID 字段，单个为字符串，多个为列表[字符串]
        request_id (str): 请求ID，如果提供则会更新数据库状态

    Returns:
        bool: 分块是否成功
    """
    start_time = time.time()
    logger.info(
        f"[文档切块] 开始处理文档, request_id={request_id}, doc_id={doc_id}, doc_process_path={doc_process_path}")

    # 后续准备迁移 Milvus,权限字段先使用 mysql 中的,milvus 中不做权限过滤
    permission_ids_str = ""  # 空字符串表示公开访问

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 初始化分块器
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=GlobalConfig.SEGMENT_CONFIG.get("max_text_length", 500),
        chunk_overlap=100,
        length_function=len,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]
    )
    logger.info(f"request_id={request_id}, 文本分块器初始化完成")

    # 初始化数据库操作实例
    chunk_op = ChunkOperation()
    vector_op = VectorOperation()
    es_op = ElasticsearchOperation()

    # 分批处理结果
    batch_size = GlobalConfig.SEGMENT_CONFIG["batch_size"]  # 每批处理的记录数
    milvus_batch = []  # 独立的 milvus 批次
    mysql_batch = []  # 独立的 mysql 批次
    es_batch = []  # 独立的 ES 批次

    # 初始化计数器
    total_records = 0

    try:
        # 验证文件是否存在
        if not Path(doc_process_path).exists():
            raise FileNotFoundError(f"处理后的文件不存在: {doc_process_path}")

        # 读取处理后的文档内容
        with open(doc_process_path, "r", encoding="utf-8") as f:
            json_content = json.load(f)

        # 初始化数据库操作对象
        total_pages = len(json_content)
        logger.info(f"request_id={request_id}, 共需处理 {total_pages} 页内容")

        for page_idx, page_contents in json_content.items():
            logger.debug(f"[文档切块] request_id={request_id}, 处理第{page_idx}页, 总页数={total_pages}")
            for content in page_contents:
                # 文本直接送入切割
                if content["type"] == "text":
                    # 检查文本长度是否需要分块
                    text_content = content["text"]
                    if len(text_content) <= GlobalConfig.SEGMENT_CONFIG.get("max_text_length", 500):
                        # 文本长度小于chunk_size，直接处理不分块
                        logger.info(
                            f"request_id={request_id}, 文本长度({len(text_content)})小于分块大小({GlobalConfig.SEGMENT_CONFIG.get('max_text_length', 500)})，不进行分块")
                        text_chunks = [text_content]
                    else:
                        # 文本长度超过chunk_size，需要分块
                        text_chunks = text_splitter.split_text(text_content)
                        logger.info(f"request_id={request_id}, 文本内容分块完成，共 {len(text_chunks)} 个块")

                    # 分批处理文本块
                    for i in range(0, len(text_chunks), batch_size):
                        batch_chunks = text_chunks[i:i + batch_size]

                        # 生成各分块的片段 id 和向量
                        for chunk in batch_chunks:
                            # 数据验证
                            if not chunk.strip():  # 空文本没有意义
                                logger.warning(f"request_id={request_id}, 跳过空文本块: '{chunk}'")
                                continue

                            seg_id = generate_seg_id(chunk)  # 片段 ID
                            vector = embedding_manager.embed_text(chunk)  # 片段向量

                            # 向量验证
                            if not isinstance(vector, list) or len(vector) != 1024:
                                logger.error(
                                    f"request_id={request_id}, 向量生成异常: {seg_id}, 长度={len(vector) if isinstance(vector, list) else 'not a list'}, 内容={chunk}")
                                continue

                            # 构建milvus存储结果
                            text_milvus_res = {
                                "vector": vector,
                                "seg_id": seg_id,
                                "seg_parent_id": "",
                                "doc_id": doc_id,
                                "seg_content": truncate_text(chunk),
                                "seg_type": "text",
                                "permission_ids": permission_ids_str,
                                "create_time": current_time,
                                "update_time": current_time,
                                "metadata": {}
                            }
                            milvus_batch.append(text_milvus_res)

                            # 构建 MySQL 存储结果
                            text_mysql_res = {
                                "seg_id": seg_id,
                                "seg_parent_id": "",
                                "seg_content": json.dumps(chunk, ensure_ascii=False),
                                "seg_len": str(len(chunk)),
                                "seg_type": "text",
                                "seg_page_idx": int(page_idx) + 1,
                                "doc_id": doc_id
                            }
                            mysql_batch.append(text_mysql_res)

                            # 构建ES存储结果
                            text_es_res = {
                                "seg_id": seg_id,
                                "seg_parent_id": "",
                                "doc_id": doc_id,
                                "seg_content": str(chunk),
                                "seg_type": "text",
                                "seg_page_idx": int(page_idx) + 1,
                                "update_time": current_time
                            }
                            es_batch.append(text_es_res)

                elif content["type"] == "table":
                    # 处理表格内容
                    logger.info(f"request_id={request_id}, 处理第 {page_idx} 页的表格内容...")

                    table_body = content.get('table_body', "").strip()
                    if not table_body:
                        logger.warning(f"request_id={request_id}, 表格内容为空: {content}")
                        continue

                    # 表格解析为markdown
                    table_markdown = convert_html_to_markdown(table_body)
                    logger.debug(f"request_id={request_id}, 表格转换为 Markdown 格式，长度: {len(table_markdown)}")

                    # 获取表格内容 Seg_id, seg_vector
                    table_seg_id = generate_seg_id(table_body)
                    # 根据表格长度选择所用内容，并 Embedding
                    segment_content = content.get('summary', table_markdown) if len(
                        table_markdown) > 1000 else table_markdown
                    table_vector = embedding_manager.embed_text(segment_content)

                    # 向量验证
                    if not isinstance(table_vector, list) or len(table_vector) != 1024:
                        logger.error(
                            f"request_id={request_id}, 表格向量生成异常: {table_seg_id}, 长度={len(table_vector) if isinstance(table_vector, list) else 'not a list'}, 内容={segment_content}")
                        continue

                    # 初始化拆表标记
                    chunk_table = False if len(table_markdown) <= 1000 else True

                    # 处理表格标题 - 可能是字符串或列表
                    table_caption = format_table_caption_footnote(content.get("table_caption", ""))
                    table_footnote = format_table_caption_footnote(content.get("table_footnote", ""))

                    # 组装表格 milvus 元数据
                    table_milvus_res = {
                        "vector": table_vector,
                        "seg_id": table_seg_id,
                        "seg_parent_id": "",
                        "doc_id": doc_id,
                        "seg_content": truncate_text(table_markdown),
                        "seg_type": "table",
                        "permission_ids": permission_ids_str,
                        "create_time": current_time,
                        "update_time": current_time,
                        "metadata": {}
                    }
                    milvus_batch.append(table_milvus_res)

                    # 组装表格 mysql 元数据
                    parent_mysql_res = {
                        "seg_id": table_seg_id,
                        "seg_parent_id": "",
                        "seg_content": table_markdown,
                        "seg_image_path": content.get("img_path", ""),
                        "seg_caption": table_caption,
                        "seg_footnote": table_footnote,
                        "seg_len": str(len(table_markdown)),
                        "seg_type": "table",
                        "seg_page_idx": int(page_idx) + 1,
                        "doc_id": doc_id
                    }
                    mysql_batch.append(parent_mysql_res)

                    # 组装表格 ES 元数据
                    table_es_res = {
                        "seg_id": table_seg_id,
                        "seg_parent_id": "",
                        "doc_id": doc_id,
                        "seg_content": table_markdown,
                        "seg_type": "table",
                        "seg_page_idx": int(page_idx) + 1,
                        "update_time": current_time
                    }
                    es_batch.append(table_es_res)

                    # 拆表流程
                    if chunk_table:
                        # 处理子表信息: 将markdown格式的内容送入切块
                        sub_table_chunks = text_splitter.split_text(table_markdown)
                        logger.debug(f"request_id={request_id}, 表格markdown分块完成，共 {len(sub_table_chunks)} 个子块")

                        for table_segment in sub_table_chunks:
                            if not table_segment.strip():  # 空文本没有意义
                                logger.warning(f"request_id={request_id}, 跳过空的子表块: '{table_segment}'")
                                continue

                            sub_table_vector = embedding_manager.embed_text(table_segment)
                            sub_seg_id = generate_seg_id(table_segment)

                            # 向量验证
                            if not isinstance(sub_table_vector, list) or len(sub_table_vector) != 1024:
                                logger.error(
                                    f"request_id={request_id}, 子表向量生成异常: {sub_seg_id}, 长度={len(sub_table_vector) if isinstance(sub_table_vector, list) else 'not a list'}, 内容={table_segment}")
                                continue

                            # 组装子表 milvus 元数据
                            sub_milvus_res = {
                                "vector": sub_table_vector,
                                "seg_id": sub_seg_id,
                                "seg_parent_id": table_seg_id,
                                "doc_id": doc_id,
                                "seg_content": truncate_text(table_segment),
                                "seg_type": "table",
                                "permission_ids": permission_ids_str,
                                "create_time": current_time,
                                "update_time": current_time,
                                "metadata": {}
                            }
                            milvus_batch.append(sub_milvus_res)

                            # 组装子表 mysql 元数据
                            sub_mysql_res = {
                                "seg_id": sub_seg_id,
                                "seg_parent_id": table_seg_id,
                                "seg_content": table_segment,
                                "seg_len": str(len(table_segment)),
                                "seg_type": "table",
                                "seg_page_idx": int(page_idx) + 1,
                                "doc_id": doc_id
                            }
                            mysql_batch.append(sub_mysql_res)

                            # 组装子表 ES 元数据
                            sub_es_res = {
                                "seg_id": sub_seg_id,
                                "seg_parent_id": table_seg_id,
                                "doc_id": doc_id,
                                "seg_content": table_segment,
                                "seg_type": "table",
                                "seg_page_idx": int(page_idx) + 1,
                                "update_time": current_time
                            }
                            es_batch.append(sub_es_res)

                elif content["type"] == "image":
                    # 判断图片内容是否为空
                    if not content.get("img_path", ""):
                        logger.warning(f"request_id={request_id}, 图片内容为空: {content}")
                        continue

                    logger.info(f"request_id={request_id}, 处理第 {page_idx} 页的图片内容...")

                    # 生成图片信息 - 处理标题可能是列表的情况
                    img_caption = format_table_caption_footnote(content.get("img_caption", ""))
                    img_footnote = format_table_caption_footnote(content.get("img_footnote", ""))

                    if not img_caption:
                        logger.warning(f"request_id={request_id}, 图片标题为空，使用默认标题")
                        img_caption = f"图片_{page_idx}_{len(mysql_batch)}"  # 页码+批次号

                    image_vector = embedding_manager.embed_text(img_caption)

                    # 向量验证
                    if not isinstance(image_vector, list) or len(image_vector) != 1024:
                        logger.error(
                            f"request_id={request_id}, 图片向量生成异常, 标题={img_caption}, 地址={content.get('img_path', '')}")
                        continue

                    image_seg_id = generate_seg_id(img_caption)

                    # 组装图片 milvus 元数据
                    image_milvus_res = {
                        "vector": image_vector,
                        "seg_id": image_seg_id,
                        "seg_parent_id": "",
                        "doc_id": doc_id,
                        "seg_content": truncate_text(img_caption),
                        "seg_type": "image",
                        "permission_ids": permission_ids_str,
                        "create_time": current_time,
                        "update_time": current_time,
                        "metadata": {}
                    }
                    milvus_batch.append(image_milvus_res)

                    # 组装图片 mysql 元数据
                    image_mysql_res = {
                        "seg_id": image_seg_id,
                        "seg_content": img_caption,
                        "seg_image_path": content.get("img_path", ""),
                        "seg_caption": img_caption,
                        "seg_footnote": img_footnote,
                        "seg_len": str(len(img_caption)),
                        "seg_type": "image",
                        "seg_page_idx": int(page_idx) + 1,
                        "doc_id": doc_id
                    }
                    mysql_batch.append(image_mysql_res)

                    # 组装图片 ES 元数据
                    image_es_res = {
                        "seg_id": image_seg_id,
                        "seg_parent_id": "",
                        "doc_id": doc_id,
                        "seg_content": img_caption,
                        "seg_type": "image",
                        "seg_page_idx": int(page_idx) + 1,
                        "update_time": current_time
                    }
                    es_batch.append(image_es_res)

                # 当批次达到指定大小时，保存到数据库
                if len(milvus_batch) >= batch_size or len(mysql_batch) >= batch_size or len(es_batch) >= batch_size:
                    # 分别保存各个数据库的批次
                    save_batch_to_databases(milvus_batch, mysql_batch, es_batch, chunk_op, vector_op, es_op)
                    total_records += len(mysql_batch)
                    milvus_batch = []
                    mysql_batch = []
                    es_batch = []

        # 保存剩余的批次
        if milvus_batch or mysql_batch or es_batch:
            save_batch_to_databases(milvus_batch, mysql_batch, es_batch, chunk_op, vector_op, es_op)
            total_records += len(mysql_batch)
            logger.info(
                f"request_id={request_id}, 已保存最后一批记录，Milvus:{len(milvus_batch)}，MySQL:{len(mysql_batch)}，ES:{len(es_batch)}")

        duration = int((time.time() - start_time) * 1000)  # 转换为毫秒
        logger.info(f"[文档切块] 文档处理完成, request_id={request_id}, doc_id={doc_id}, "
                    f"总记录数={total_records}, 耗时={duration}ms")

        return True

    except Exception as e:
        logger.error(f"[文档处理失败] request_id={request_id}, doc_id={doc_id}, error={str(e)}")
        raise


def save_batch_to_databases(milvus_batch: List[Dict],
                            mysql_batch: List[Dict],
                            es_batch: List[Dict],
                            chunk_op,
                            vector_op: VectorOperation,
                            es_op: ElasticsearchOperation
                            ) -> None:
    """保存一批数据到各个数据库

    Args:
        milvus_batch: Milvus 数据批次
        mysql_batch: MySQL 数据批次
        es_batch: ES 数据批次
        chunk_op: 分MySQL 操作实例
        vector_op: Milvus 操作实例
        es_op: ES 操作实例

    Returns:
        bool: 保存是否成功
    """
    try:
        # 1. 保存到 MySQL(原文)
        if mysql_batch:
            chunk_op.insert_chunks(mysql_batch)

        # 2. 保存到 Milvus(向量和元数据)
        if milvus_batch:
            vector_op.insert_data(milvus_batch)
            vector_op.flush()  # 执行 flush 操作

        # 3. 保存到 ES(用于 BM25 检索)
        if es_batch:
            es_op.insert_data(es_batch)
    except Exception as e:
        logger.error(f"保存批次数据失败: {str(e)}")
        raise


if __name__ == '__main__':
    # 初始化分块器
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        length_function=len,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]
    )
    print(GlobalConfig.SEGMENT_CONFIG.get("max_text_length", 500))
    print(text_splitter.__dict__)
