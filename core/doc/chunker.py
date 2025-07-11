"""文档内容分块"""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Union, Any

from langchain.text_splitter import RecursiveCharacterTextSplitter

from config.global_config import GlobalConfig
from databases.elasticsearch.operations import ElasticsearchOperation
from databases.milvus.flat_collection import FlatCollectionManager
from databases.mysql.operations import ChunkOperation
from utils.file_ops import generate_seg_id, truncate_text
from utils.llm_utils import embedding_manager
from utils.log_utils import logger
from utils.table_linearized import html_to_structured_linear, escape_html_table


def format_table_caption_footnote(value: Union[str, List]):
    """处理标题和脚注为列表或者空的问题"""
    if isinstance(value, str) and value.strip() is None:
        return None
    elif isinstance(value, list):
        return None if len(value) == 0 else ",".join(str(item) for item in value)
    return value


def _build_milvus_data(doc_id: str, seg_content: str, seg_type: str, seg_page_idx: int,
                       current_time: str, metadata: json = None, request_id: str = None) -> Dict[str, Any]:
    """
    构建 milvus 存储数据结构

    Args:
        doc_id: 文档 ID
        seg_content: 分块内容,除存储外,还用来生成 seg_id 和 seg_dense_vector
        seg_type: 分块类型
        seg_page_idx: 分块所属页码
        current_time: 创建/更新时间, 格式为 ("%Y-%m-%d %H:%M:%S")
        metadata: 元数据
        request_id: 请求 ID

    Returns:
        Dict[str,Any]: 构建好的记录字典
    """

    # 数据验证
    seg_content = seg_content.strip()
    seg_id = generate_seg_id(seg_content)  # 片段 ID
    dense_vector = embedding_manager.embed_text(seg_content)  # 片段向量

    # 向量验证
    if not isinstance(dense_vector, list) or len(dense_vector) != 1024:
        logger.error(
            f"[Milvus_Data_Build] request_id={request_id}, 向量生成异常: "
            f"seg_id: {seg_id}, "
            f"长度: {len(dense_vector) if isinstance(dense_vector, list) else 'not a list'}, "
            f"片段内容: {seg_content}")
        return {}

    data = {
        "doc_id": doc_id,
        "seg_id": seg_id,
        "seg_dense_vector": dense_vector,
        "seg_content": truncate_text(seg_content, max_length=60000),
        "seg_type": seg_type,
        "seg_page_idx": seg_page_idx,
        "created_at": current_time,
        "updated_at": current_time,
        "metadata": metadata if metadata else {}
    }

    return data


def _build_mysql_data(seg_content: str, seg_type: str, seg_len: int, seg_page_idx: int,
                      doc_id: str, current_time: str, seg_image_path: str = None, seg_caption: str = None,
                      seg_footnote: str = None) -> Dict[str, Any]:
    """
    构建 mysql 存储数据结构

    Args:
        seg_content: 分块内容,除存储外,还用来生成 seg_id 和 seg_dense_vector
        seg_image_path: 分块对应的图片地址, 提取出的表格图片或者文档中的图片存储路径
        seg_caption: 分块标题(表格标题/图片标题)
        seg_footnote: 分块脚注(表格脚注/图片脚注)
        seg_type: 分块类型
        seg_page_idx: 分块所属页码
        doc_id: 文档 ID
        current_time: 创建/更新时间, 格式为 ("%Y-%m-%d %H:%M:%S")

    Returns:
        Dict[str,Any]: 构建好的记录字典
    """

    # 数据验证
    seg_content = seg_content.strip()
    seg_id = generate_seg_id(seg_content)  # 片段 ID

    data = {
        "seg_id": seg_id,
        "seg_content": seg_content,
        "seg_image_path": seg_image_path if seg_image_path else '',
        "seg_caption": seg_caption if seg_caption else '',
        "seg_footnote": seg_footnote if seg_footnote else '',
        "seg_type": seg_type,
        "seg_len": seg_len,
        "seg_page_idx": seg_page_idx,
        "created_at": current_time,
        "updated_at": current_time,
        "doc_id": doc_id,
    }

    return data


def segment_text_content(doc_id: str, doc_process_path: str,
                         request_id: str = None) -> bool:
    """分块文本内容

    Args:
        doc_id: 文档ID
        doc_process_path: 聚合处理后的文档，格式为 dict[idx:[content]]
        request_id: 请求ID

    Returns:
        bool: 分块是否成功
    """
    start_time = time.time()
    logger.info(
        f"[文档切块] 开始处理文档, request_id={request_id}, doc_id={doc_id}, doc_process_path={doc_process_path}")

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 初始化分块器
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=GlobalConfig.SEGMENT_CONFIG.get("max_text_length", 500),
        chunk_overlap=100,
        length_function=len,
        separators=["\n\n", "\n", "。", "！", "？", "!", "?"]
    )
    logger.info(f"request_id={request_id}, 文本分块器初始化完成")

    # 初始化数据库操作实例
    chunk_op = ChunkOperation()
    flat_manager = FlatCollectionManager()
    es_op = ElasticsearchOperation()

    # 分批处理结果
    batch_size = GlobalConfig.SEGMENT_CONFIG["batch_size"]  # 每批处理的记录数
    milvus_batch = []  # 独立的 milvus 批次
    mysql_batch = []  # 独立的 mysql 批次

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

                # 文本元素处理
                if content["type"] == "text":

                    # 检查文本长度是否需要分块
                    text_content = content["text"].strip()

                    if not text_content:
                        logger.warning(f"[Chunker] request_id={request_id}, 跳过空文本块: '{text_content}'")
                        continue

                    # 根据固定长度切块
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
                            # 构建 milvus 数据存储
                            milvus_data = _build_milvus_data(
                                doc_id=doc_id,
                                seg_content=chunk,
                                seg_type='text',
                                seg_page_idx=int(page_idx) + 1,
                                current_time=current_time,
                                request_id=request_id
                            )
                            if milvus_data:
                                milvus_batch.append(milvus_data)

                            # 构建 MySQL 存储结果
                            mysql_data = _build_mysql_data(
                                seg_content=json.dumps(chunk, ensure_ascii=False),
                                seg_type='text',
                                seg_len=len(chunk),
                                seg_page_idx=int(page_idx) + 1,
                                doc_id=doc_id,
                                current_time=current_time,
                            )
                            if mysql_data:
                                mysql_batch.append(mysql_data)


                elif content["type"] == "table":
                    # 处理表格内容
                    logger.info(f"request_id={request_id}, 处理第 {page_idx} 页的表格内容...")

                    table_body = content.get('table_body', "").strip()
                    if not table_body:
                        logger.warning(f"request_id={request_id}, 表格内容为空: {content}")
                        continue

                    # 处理表格标题 - 可能是字符串或列表
                    table_caption = format_table_caption_footnote(content.get("table_caption", ""))
                    table_footnote = format_table_caption_footnote(content.get("table_footnote", ""))

                    # 线性化处理结果, 包含三种可能:
                    # 规则提取线性化(parser-linear), 模型输出线性化(llm-linear), 模型输出未线性化(llm_fallback)
                    table_linear_result: Dict[str, Any] = html_to_structured_linear(
                        table_body,
                        caption=table_caption
                    )
                    # 提取解析结果类型
                    table_type: str = table_linear_result['source']
                    # 提取解析结果
                    table_content = table_linear_result['content']
                    logger.debug(
                        f"[Chunker] request_id={request_id}, Table Linearize 完成, type: {table_type}, table_content:{table_content}")

                    # 将字典内容转为字符串, 字典按照 key 排序(非字典忽略排序),并禁止中文转义
                    table_text = json.dumps(table_content, ensure_ascii=False, sort_keys=True)
                    #

                    # 编码 html 结果存储到 mysql
                    escaped_html = escape_html_table(table_body)
                    # escaped_html_len = len(escaped_html) if escaped_html else 0

                    # TODO: 后续根据情况,可增加子块切分逻辑
                    # 线性化文本的切分: >3000, 按照分组切分, 若只有一个分组,则分组拆散后组合为多个子分组
                    # html 源结构的切分:>3000, 根据表格内的<tr>进行切分,最终应该为<table>表 1</table>,<table>表 2</table>

                    # 构建 milvus 数据存储
                    milvus_data = _build_milvus_data(
                        doc_id=doc_id,
                        seg_content=table_text,
                        seg_type=table_type,
                        seg_page_idx=int(page_idx) + 1,
                        current_time=current_time,
                        metadata={**table_linear_result['meta']},
                        request_id=request_id
                    )

                    milvus_batch.append(milvus_data)

                    mysql_data = _build_mysql_data(
                        seg_content=escaped_html,  # mysql 存储表格的源 HTML 格式(escape 编码后,避免字符异常)
                        seg_image_path=content.get("img_path", ""),
                        seg_caption=table_caption,
                        seg_footnote=table_footnote,
                        seg_type='table',
                        seg_len=len(escaped_html) if escaped_html else 0,
                        seg_page_idx=int(page_idx) + 1,
                        doc_id=doc_id,
                        current_time=current_time,
                    )
                    if mysql_data:
                        mysql_batch.append(mysql_data)



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

                    # 构建 milvus 数据存储
                    milvus_data = _build_milvus_data(
                        doc_id=doc_id,
                        seg_content=img_caption,
                        seg_type="image",
                        seg_page_idx=int(page_idx) + 1,
                        current_time=current_time,
                        request_id=request_id
                    )
                    if milvus_data:
                        milvus_batch.append(milvus_data)

                    mysql_data = _build_mysql_data(
                        seg_content=img_caption,  # 图片暂时使用图片标题
                        seg_image_path=content.get("img_path", ""),
                        seg_caption=img_caption,
                        seg_footnote=img_footnote,
                        seg_type='image',
                        seg_len=len(img_caption),
                        seg_page_idx=int(page_idx) + 1,
                        doc_id=doc_id,
                        current_time=current_time,
                    )
                    if mysql_data:
                        mysql_batch.append(mysql_data)

            # 当批次达到指定大小时，保存到数据库
            if len(milvus_batch) >= batch_size or len(mysql_batch) >= batch_size:
                # 分别保存各个数据库的批次
                save_batch_to_databases(milvus_batch, mysql_batch, chunk_op, flat_manager)
                total_records += len(mysql_batch)
                milvus_batch = []
                mysql_batch = []
                es_batch = []

        # 保存剩余的批次
        if milvus_batch or mysql_batch:
            save_batch_to_databases(milvus_batch, mysql_batch, chunk_op, flat_manager)
            total_records += len(mysql_batch)
            logger.info(
                f"request_id={request_id}, 已保存最后一批记录，Milvus:{len(milvus_batch)}，MySQL:{len(mysql_batch)}")

        duration = int((time.time() - start_time) * 1000)  # 转换为毫秒
        logger.info(f"[文档切块] 文档处理完成, request_id={request_id}, doc_id={doc_id}, "
                    f"总记录数={total_records}, 耗时={duration}ms")

        return True

    except Exception as e:
        logger.error(f"[文档处理失败] request_id={request_id}, doc_id={doc_id}, error={str(e)}")
        raise


def save_batch_to_databases(milvus_batch: List[Dict],
                            mysql_batch: List[Dict],
                            chunk_op,
                            flat_manager: FlatCollectionManager,
                            ) -> bool:
    """保存一批数据到各个数据库

    Args:
        milvus_batch: Milvus 数据批次
        mysql_batch: MySQL 数据批次
        chunk_op: 分MySQL 操作实例
        flat_manager: FLAT Collection 实例

    Returns:
        bool: 保存是否成功
    """
    try:
        # 1. 保存到 MySQL
        if mysql_batch:
            chunk_op.insert_chunks(mysql_batch)

        # 2. 保存到 Milvus
        if milvus_batch:
            flat_manager.insert_data(milvus_batch)

        return True

    except Exception as e:
        logger.error(f"保存批次数据失败: {str(e)}")
        return False


if __name__ == '__main__':
    # 初始化分块器
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        length_function=len,
        separators=["\n\n", "\n", "。", "！", "？", "!", "?"]
    )
    print(GlobalConfig.SEGMENT_CONFIG.get("max_text_length", 500))
    print(text_splitter.__dict__)
