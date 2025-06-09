"""处理文档内容, 包括表格、图片、文本等"""
import hashlib
import json
import os
import tempfile
import traceback
from collections import defaultdict

import diskcache
from rich import print
from pathlib import Path

from src.api.error_codes import ErrorCode
from src.api.response import APIException
from src.core.document.doc_convert import convert_office_file
from src.core.document.doc_parser import mineru_toolkit
from src.database.mysql.operations import FileInfoOperation
from src.utils.validator.content_validator import ContentValidator
from src.utils.validator.file_validator import FileValidator

from src.utils.common.logger import logger
from src.utils.validator.args_validator import ArgsValidator
from src.core.llm.extract_summary import extract_table_summary
from src.utils.table_toolkit import html_table_to_markdown

# 初始化摘要缓存
cache = diskcache.Cache()


def get_table_summary_cached(markdown_table: str) -> dict:
    # 使用表格的markdown格式哈希值作为缓存键
    key = f"summary_{hash(markdown_table)}"
    if key in cache:
        return cache[key]
    summary = extract_table_summary(markdown_table)
    cache[key] = summary
    return summary


def process_doc_by_page(json_doc_path: str):
    """读取MinerU解析后的 JSON 文档, 填充表格和图片标题, 并按页合并内容

    Args:
        json_doc_path (str): MinerU 解析后的 json 文件路径
    """
    with open(json_doc_path, "r", encoding="utf-8") as f:
        json_content = json.load(f)

    doc_hash = hashlib.md5(json_doc_path.encode("utf-8")).hexdigest()
    temp_dir = Path("page_cache") / doc_hash
    temp_dir.mkdir(parents=True, exist_ok=True)
    progress_file = temp_dir / "progress.json"

    if progress_file.exists():
        with open(progress_file, "r", encoding="utf-8") as pf:
            processed_pages = set(json.load(pf).get("processed_pages", []))

    # 统计信息初始化
    table_total, table_cap, table_cap_up, table_cap_miss = 0, 0, 0, 0
    img_total, img_cap, img_cap_up, img_cap_miss = 0, 0, 0, 0

    try:
        for idx, item in enumerate(json_content):
            # 获取页码
            page_idx = item.get("page_idx", idx)
            # 如果页码已经处理过，跳过
            if page_idx in processed_pages:
                continue

            caption = None  # 初始化标题
            last_item = json_content[idx - 1] if idx > 0 else None  # 指定上一个元素
            # 提取表格元素
            if item["type"] == "table":
                table_total += 1
                # 处理列表标题为字符串
                item["table_caption"] = "".join(item["table_caption"]) if isinstance(item["table_caption"], list) else \
                    item[
                        "table_caption"]

                # 通过 LLM 提取摘要信息（标题 + 内容摘要）
                markdown_table = html_table_to_markdown(item["table_body"])
                table_summary = extract_table_summary(markdown_table)

                # 更新内容摘要
                item["summary"] = table_summary["summary"]

                # 有标题
                if item["table_caption"].strip():
                    table_cap += 1

                # 没有标题
                else:
                    # 使用上个表格的标题
                    if last_item and last_item["type"] == "table":
                        caption = str(last_item.get("table_caption", "")[0]).strip()
                    # 使用上一个文本作为标题（短文本）
                    elif last_item and last_item["type"] == "content" and len(last_item["content"]) < 100:
                        caption = str(last_item.get("content", "")).strip()
                    else:
                        # 使用 LLM 生成的标题
                        caption = table_summary["title"].strip()

                    # 如果提取到标题进行更新
                    if caption:
                        # 处理列表作为标题的异常情况
                        item["table_caption"] = "".join(caption).strip() if isinstance(caption, list) else caption
                        table_cap_up += 1
                    else:
                        table_cap_miss += 1

            # 处理图片标题
            if item["type"] == "image":
                img_total += 1

                # 处理标题为字符串
                item["img_caption"] = ", ".join(item["img_caption"]) if isinstance(item["img_caption"], list) else item[
                    "img_caption"]

                # 如果图片标题存在
                if item["img_caption"].strip():
                    img_cap += 1
                else:
                    # 使用上一个文本作为标题（短文本）
                    if last_item and last_item["type"] == "content" and len(last_item["content"]) < 100:
                        caption = str(last_item.get("content", "")).strip()

                    if caption:
                        # 处理列表作为标题的异常情况
                        item["img_caption"] = "".join(caption).strip() if isinstance(caption, list) else caption
                        img_cap_up += 1
                    else:
                        img_cap_miss += 1

            # 每页处理完写入到缓存文件
            page_file = temp_dir / f"page_{page_idx}.json"
            with open(page_file, "w", encoding="utf-8") as pf:
                json.dump(item, pf, indent=2, ensure_ascii=False)
            processed_pages.add(page_idx)

            # 实时保存进度
            with open(progress_file, "w", encoding="utf-8") as pf:
                json.dump({"processed_pages": list(processed_pages)}, pf)

    except Exception as e:
        # 异常时,自动保存进度文件和已处理内容
        logger.error(f"处理异常: {str(e)},进度已保存到 {progress_file}")
        raise

    try:
        # 合并所有缓存页
        logger.debug("所有页内容汇总完成, 开始合并后的内容...")
        merged = []
        # 遍历临时目录中的所有页面文件，按页码顺序合并内容
        for page_file in sorted(temp_dir.glob("page_*.json"), key=lambda x: int(x.stem.split('_')[1])):
            with open(page_file, "r", encoding="utf-8") as pf:
                merged.append(json.load(pf))

        logger.debug("所有页内容汇总完成, 开始保存合并后的内容...")
        save_path = Path(json_doc_path).parent / f"{Path(json_doc_path).stem}_merged.json"
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        logger.debug(f"合并后的文档内容已保存到: {save_path}")
        return str(save_path)
    except Exception as e:
        logger.error(f"[文件保存失败] operation=合并处理文件， error_msg={str(e)}")
        raise APIException(ErrorCode.FILE_SAVE_FAILED, str(e))


# def fill_title(json_doc_path: str) -> list:
#     """处理 JSON 文件中的表格和图片标题
#
#     Args:
#         json_doc_path (str): MinerU 解析后的 json 文件
#
#     Returns:
#         list: 处理后的文档内容列表
#     """
#
#     # 统计信息初始化
#     table_total, table_cap, table_cap_up, table_cap_miss = 0, 0, 0, 0
#     img_total, img_cap, img_cap_up, img_cap_miss = 0, 0, 0, 0
#
#     try:
#         # 读取json文件
#         with open(json_doc_path, "r", encoding="utf-8") as json_f:
#             json_content = json.load(json_f)
#     except Exception as e:
#         logger.error(f"[文件读取失败] doc_path={json_doc_path}, error_msg={str(e)}")
#         raise APIException(ErrorCode.FILE_READ_FAILED, f"读取 JSON 文件失败: {str(e)}") from e
#
#     try:
#         # 更新表格的标题信息
#         for idx, item in enumerate(json_content):
#             caption = None  # 初始化标题
#             last_item = json_content[idx - 1] if idx > 0 else None  # 指定上一个元素
#
#             # 提取表格元素
#             if item["type"] == "table":
#                 table_total += 1
#
#                 # 处理列表标题为字符串
#                 item["table_caption"] = "".join(item["table_caption"]) if isinstance(item["table_caption"], list) else \
#                     item[
#                         "table_caption"]
#
#                 # 通过 LLM 提取摘要信息（标题 + 内容摘要）
#                 markdown_table = html_table_to_markdown(item["table_body"])
#                 table_summary = extract_table_summary(markdown_table)
#
#                 # 更新内容摘要
#                 item["summary"] = table_summary["summary"]
#
#                 # 有标题
#                 if item["table_caption"].strip():
#                     table_cap += 1
#
#                 # 没有标题
#                 else:
#                     # 使用上个表格的标题
#                     if last_item and last_item["type"] == "table":
#                         caption = str(last_item.get("table_caption", "")[0]).strip()
#                     # 使用上一个文本作为标题（短文本）
#                     elif last_item and last_item["type"] == "content" and len(last_item["content"]) < 100:
#                         caption = str(last_item.get("content", "")).strip()
#                     else:
#                         # 使用 LLM 生成的标题
#                         caption = table_summary["title"].strip()
#
#                     # 如果提取到标题进行更新
#                     if caption:
#                         # 处理列表作为标题的异常情况
#                         item["table_caption"] = "".join(caption).strip() if isinstance(caption, list) else caption
#                         table_cap_up += 1
#                     else:
#                         table_cap_miss += 1
#
#             # 处理图片标题
#             if item["type"] == "image":
#                 img_total += 1
#
#                 # 处理标题为字符串
#                 item["img_caption"] = ", ".join(item["img_caption"]) if isinstance(item["img_caption"], list) else item[
#                     "img_caption"]
#
#                 # 如果图片标题存在
#                 if item["img_caption"].strip():
#                     img_cap += 1
#                 else:
#                     # 使用上一个文本作为标题（短文本）
#                     if last_item and last_item["type"] == "content" and len(last_item["content"]) < 100:
#                         caption = str(last_item.get("content", "")).strip()
#
#                     if caption:
#                         # 处理列表作为标题的异常情况
#                         item["img_caption"] = "".join(caption).strip() if isinstance(caption, list) else caption
#                         img_cap_up += 1
#                     else:
#                         img_cap_miss += 1
#
#         # 输出统计信息
#         logger.debug(
#             f"图片标题处理完成: {img_total} 张, 无需更新: {img_cap}, 已更新: {img_cap_up}, 缺少标题: {img_cap_miss} | "
#             f"表格标题处理完成: {table_total} 张, 已有标题: {table_cap}, 已更新: {table_cap_up}, 缺少标题: {table_cap_miss}"
#         )
#         return json_content
#
#     except Exception as e:
#         raise APIException(ErrorCode.FILE_EXCEPTION, f"文档内容标题处理失败: {str(e)}") from e
#
#
# def merge_page_for_idx(json_doc_path: Path):
#     """解析 json 内容, 根据 page_idx 合并 content 元素
#
#     Args:
#         json_doc_path (Path): 处理后的 json 内容列表(MinerU -> 完善表格/图片标题)
#
#     Returns:
#         merge_page_contents (dict): 按照 page_idx 进行合并的 json 内容, 格式为 {page_idx:[content,content,content], ...}
#     """
#
#     try:
#         with open(file=json_doc_path, mode='r', encoding='utf-8') as f:
#             json_content = json.load(f)
#         ContentValidator.validate_json_file(json_content)
#     except json.JSONDecodeError as e:
#         raise APIException(ErrorCode.FILE_EXCEPTION, f"JSON 解析错误: {str(e)}")
#     except Exception as e:
#         logger.error(f"[文件读取失败] doc_path={json_doc_path}, error_msg={str(e)}")
#         raise APIException(ErrorCode.FILE_EXCEPTION, str(e)) from e
#
#     try:
#         temp_dir = tempfile.TemporaryDirectory()  # 创建临时目录
#         page_files = defaultdict(list)  # 初始化页面存储
#         text_list = []  # 临时存储文本段
#         tmp_idx = None  # 当前页码缓存
#
#         logger.debug("开始按页合并文档...")
#
#         for content in json_content:
#             # 获取当前页码
#             page_idx = content["page_idx"]
#
#             if tmp_idx is not None and page_idx != tmp_idx:
#                 logger.debug("翻页, 处理上一个内容页内容...")
#                 if text_list:
#                     page_files[tmp_idx].append({
#                         "type": "content",
#                         "content": "".join(text_list),
#                         "page_idx": tmp_idx
#                     })
#                     text_list = []
#                 # 保存当前页内容
#                 with open(f"{temp_dir.name}/page_{tmp_idx}.jsonl", "a", encoding="utf-8") as f:
#                     # 获取已合并完的页面内容
#                     for item in page_files[tmp_idx]:
#                         f.write(json.dumps(item, ensure_ascii=False) + "\n")
#                 # 清空已保存的页面内容
#                 page_files[tmp_idx] = []
#
#             # 更新当前页码
#             tmp_idx = page_idx
#             logger.debug(f"合并第 {tmp_idx} 页内容...")
#
#             # 处理同页内容
#             if content["type"] == "content":
#                 text_list.append(content["content"])
#             # 非文本类型，保存积累的文本后保存该元素
#             else:
#                 if text_list:
#                     page_files[page_idx].append({
#                         "type": "content",
#                         "content": "".join(text_list),
#                         "page_idx": page_idx
#                     })
#                     text_list = []
#                 page_files[page_idx].append(content)
#
#         # 处理最后一页累积的文本
#         if text_list:
#             logger.debug("处理最后一页遗留内容...")
#             page_files[tmp_idx].append({
#                 "type": "content",
#                 "content": "".join(text_list),
#                 "page_idx": tmp_idx
#             })
#         if tmp_idx is not None and page_files.get(tmp_idx):
#             with open(f"{temp_dir.name}/page_{tmp_idx}.jsonl", "a", encoding="utf-8") as f:
#                 # 获取最后一页的内容
#                 for item in page_files[tmp_idx]:
#                     f.write(json.dumps(item, ensure_ascii=False) + "\n")
#
#         # 汇总所有页
#         logger.debug("开始汇总所有页内容...")
#         result = defaultdict(list)
#         for f_name in os.listdir(temp_dir.name):
#             # 提取缓存文件的名称中的页码
#             page_idx = int(f_name.split('_')[1].split('.')[0])
#             with open(f"{temp_dir.name}/{f_name}", "r", encoding="utf-8") as f:
#                 for line in f:
#                     result[page_idx].append(json.loads(line))
#
#         logger.debug("所有页内容汇总完成, 开始保存合并后的内容...")
#         save_path = json_doc_path.parent / f"{json_content}_merged.json"
#         with open(save_path, "w", encoding="utf-8") as f:
#             json.dump(result, f, ensure_ascii=False, indent=2)
#         logger.debug(f"合并后的文档内容已保存到: {save_path}")
#
#     except Exception as e:
#         raise APIException(ErrorCode.FILE_EXCEPTION, f"文档内容合并失败: {str(e)}") from e

# 定义文档处理后台任务函数
def background_process_document(doc_path: str, doc_id: str):
    """后台处理文档内容

    Args:
        doc_path: 文档路径
        doc_id: 文档ID
    """
    try:
        logger.info(f"[开始后台处理文档] doc_id={doc_id}")
        # 调用文档处理方法
        save_path = process_doc_content(doc_path)
        # 更新处理结果
        logger.info(f"[文档处理完成] doc_id={doc_id}, result={save_path}")

        # 更新数据库
        with FileInfoOperation() as file_op:
            values = {
                "doc_process_path": save_path,
                "process_status": "completed"
            }
            file_op.update_by_doc_id(doc_id, values)

    except Exception as e:
        logger.error(f"[文档处理失败] doc_id={doc_id}, error={str(e)}")
        # 记录详细的错误堆栈
        logger.error(f"[错误详情] doc_id={doc_id}, error={traceback.format_exc()}")

        # 更新数据库状态为失败
        with FileInfoOperation() as file_op:
            values = {
                "process_status": "failed",
                "error_message": str(e)[:255]  # 限制错误信息长度
            }
            file_op.update_by_doc_id(doc_id, values)


# 入口函数
def process_doc_content(doc_path: str) -> str:
    """处理文档内容:
    1. 非PDF文件先转换为PDF
    2. 使用MinerU解析 PDF 文档
    2. 填充表格和图片标题, 并按页合并内容, 写入json文件, 命名为 {json_doc_path}_merged.json

    Args:
        doc_path (str): 源文档路径

    Returns:
        save_path (str): 处理后的文档路径
    """
    # 验证参数
    ArgsValidator.validate_type(doc_path, str, "pdf_doc_path")  # 参数类型验证
    FileValidator.validate_local_filepath_exist(doc_path)  # 文件路径验证
    FileValidator.validate_file_convert_ext(doc_path)

    doc_path = Path(doc_path)
    # 非PDF文件先转换
    pdf_path = convert_office_file(str(doc_path.resolve())) if doc_path.suffix != '.pdf' else str(doc_path)

    ContentValidator.validate_pdf_content_parse(pdf_path)  # 验证 PDF 文档内容解析

    # 使用MinerU 解析 PDF 文档
    out_info = mineru_toolkit(pdf_path)

    # 填充表格和图片标题并按页合并
    save_path = process_doc_by_page(out_info["json_path"])

    return save_path


if __name__ == '__main__':
    pass
