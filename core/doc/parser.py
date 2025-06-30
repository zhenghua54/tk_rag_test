"""处理文档内容, 包括表格、图片、文本等"""
import json
import shutil
import time
import hashlib
import uuid

from pathlib import Path
from typing import Dict

from config.global_config import GlobalConfig
from databases.db_ops import update_record_by_doc_id
from error_codes import ErrorCode
from api.response import APIException
from utils.file_ops import mineru_toolkit, get_doc_output_path, libreoffice_convert_toolkit
# from databases.mysql.operations import FileInfoOperation
from utils.validators import check_local_doc_exists, check_doc_ext

from utils.log_utils import log_operation_success, log_operation_start, log_operation_error, logger, log_exception
from utils.validators import validate_param_type
from utils.file_ops import extract_table_summary
from utils.converters import convert_html_to_markdown


# === 填充标题并按页合并 ===
def process_doc_by_page(json_doc_path: str):
    """读取MinerU解析后的 JSON 文档, 填充表格和图片标题, 并按页合并内容

    Args:
        json_doc_path (str): MinerU 解析后的 json 文件路径
    """
    with open(json_doc_path, "r", encoding="utf-8") as f:
        json_content = json.load(f)

    doc_hash = hashlib.md5(json_doc_path.encode("utf-8")).hexdigest()
    temp_root = Path("page_cache")
    temp_dir = temp_root / f"{doc_hash}_{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 统计信息初始化
    table_total, table_cap, table_cap_up, table_cap_miss = 0, 0, 0, 0
    img_total, img_cap, img_cap_up, img_cap_miss = 0, 0, 0, 0

    # 定义初始化存储
    try:
        # 按页面分组处理内容
        current_page = None
        page_contents = []  # 当前页面的内容
        text_buffer = []  # 当前页面的文本缓冲区

        for idx, item in enumerate(json_content):
            page_idx = item.get("page_idx")

            # 如果遇到新页面, 保存上一页的内容
            if current_page is not None and current_page != page_idx:
                # 处理最后一页遗留的文本
                if text_buffer:
                    page_contents.append({
                        "type": "text",
                        "text": "\n".join(text_buffer),
                        "page_idx": current_page
                    })
                    text_buffer = []

                # 保存当前页内容
                if page_contents:
                    page_file = temp_dir / f"page_{current_page}.json"
                    with open(page_file, "w", encoding="utf-8") as pf:
                        json.dump(page_contents, pf, indent=2, ensure_ascii=False)
                    # processed_pages.add(current_page)
                    page_contents = []  # 清空当前页内容

            current_page = page_idx

            # 处理文本元素
            if item["type"] == "text":
                text_buffer.append(item["text"])
                # 如果下一个不是文本,或到末尾, 则保存当前文本
                if idx == len(json_content) - 1 or json_content[idx + 1]["type"] != "text":
                    if text_buffer:  # 有文本合并
                        page_contents.append({
                            "type": "text",
                            "text": "\n".join(text_buffer),
                            "page_idx": current_page
                        })
                        text_buffer = []

            # 提取表格元素
            elif item["type"] == "table":
                table_total += 1
                # 处理表格标题
                item["table_caption"] = "".join(item["table_caption"]) if isinstance(item["table_caption"], list) else \
                    item[
                        "table_caption"]

                # 通过 LLM 提取摘要信息（标题 + 内容摘要）
                markdown_table = convert_html_to_markdown(item["table_body"])
                table_summary = extract_table_summary(markdown_table)
                item["summary"] = table_summary["summary"]

                # 处理表格标题
                if not item["table_caption"].strip():
                    last_item = json_content[idx - 1] if idx > 0 else None
                    if last_item and last_item["type"] == "table":
                        caption = str(last_item.get("table_caption", "")[0]).strip()
                    elif last_item and last_item["type"] == "text" and len(last_item["text"]) < 100:
                        caption = last_item.get("text").strip()
                    else:
                        caption = table_summary["title"].strip()

                    if caption:
                        item["table_caption"] = caption
                        table_cap_up += 1
                    else:
                        table_cap_miss += 1
                else:
                    table_cap += 1

                # 保存修改后的表格元素
                page_contents.append(item)

            # 处理图片元素
            elif item["type"] == "image":
                img_total += 1
                # 处理标题为字符串
                item["img_caption"] = ", ".join(item["img_caption"]) if isinstance(item["img_caption"], list) else item[
                    "img_caption"]

                # 处理图片标题
                if not item["img_caption"].strip():
                    last_item = json_content[idx - 1] if idx > 0 else None
                    if last_item and last_item["type"] == "text" and len(last_item["text"]) < 100:
                        caption = last_item.get("text").strip()
                        if caption:
                            item["img_caption"] = caption
                            img_cap_up += 1
                    else:
                        img_cap_miss += 1
                else:
                    img_cap += 1

                # 保存修改后的图片元素
                page_contents.append(item)
            # logger.info(f"已写出 page_{current_page}.json, 内容数量: {len(page_contents)}")

        # 处理最后一页遗留的文本
        if current_page is not None:
            if text_buffer:
                page_contents.append({
                    "type": "text",
                    "text": "\n".join(text_buffer),
                    "page_idx": current_page
                })
                text_buffer = []

            if page_contents:
                page_file = temp_dir / f"page_{current_page}.json"
                try:
                    with open(page_file, "w", encoding="utf-8") as pf:
                        json.dump(page_contents, pf, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.error(f"最后一页写入失败: {page_file}, 错误: {str(e)}")
                    raise RuntimeError(f"最后一页写入失败: {page_file}, 错误: {str(e)}") from e

        log_operation_success("内容合并",
                              start_time=time.time(),
                              info=f"标题更新情况: 图片 {img_total} 张, 无需更新: {img_cap}, 已更新: {img_cap_up}, 缺少标题: {img_cap_miss} | "
                                   f"表格 {table_total} 张, 已有标题: {table_cap}, 已更新: {table_cap_up}, 缺少标题: {table_cap_miss}")

    except Exception as e:
        log_operation_error("处理异常", error_msg=str(e))
        raise

    # 合并页面
    try:
        # 合并所有缓存页
        log_operation_start("合并缓存页", start_time=time.time())
        merged = {}
        # 遍历临时目录中的所有页面文件，按页码顺序合并内容
        for page_file in sorted(temp_dir.glob("page_*.json"), key=lambda x: int(x.stem.split('_')[1])):
            if not page_file.exists():
                raise FileNotFoundError(f"找不到页面文件: {page_file}")
            page_idx = int(page_file.stem.split('_')[1])
            with open(page_file, "r", encoding="utf-8") as pf:
                # 读取每页的列表合并到 merged中
                merged[str(page_idx)] = json.load(pf)

        start_time = log_operation_start("处理缓存文件", start_time=time.time())
        # 保存合并后的文件
        save_path = Path(json_doc_path).parent / f"{Path(json_doc_path).stem}_merged.json"
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)

        try:
            shutil.rmtree(temp_root)
            log_operation_success("处理缓存文件", start_time=start_time)
        except Exception as e:
            log_operation_error("清理缓存文件",
                                error_code=ErrorCode.FILE_SOFT_DELETE_ERROR.value,
                                error_msg=str(e))
            raise ValueError(f"缓存清理失败, 缓存路径: {str(temp_root.resolve())}, 失败原因: {str(e)}")
        return str(save_path)

    except Exception as e:
        log_operation_error("合并异常", error_msg=str(e))
        raise APIException(ErrorCode.FILE_SAVE_FAILED, str(e))


# === 主入口函数（后台处理） ===
def process_doc_content(doc_path: str, doc_id: str = None) -> str:
    """处理文档内容:
    1. 非PDF文件先转换为PDF
    2. 使用MinerU解析 PDF 文档
    3. 填充表格和图片标题, 并按页合并内容, 写入json文件, 命名为 {json_doc_path}_merged.json
    4. 如果提供了 doc_id，则更新数据库中的处理状态

    Args:
        doc_path (str): 源文档路径
        doc_id (str, optional): 文档ID，如果提供则会更新数据库状态

    Returns:
        save_path (str): 处理后的文档路径
    """

    try:
        logger.info(f"开始处理文档: {doc_path}, doc_id={doc_id}")

        # 验证参数
        validate_param_type(doc_path, str, "源文档路径")  # 参数类型验证
        check_local_doc_exists(doc_path)  # 文件路径验证
        doc_path = Path(doc_path)

        # 获取文档的输出路径
        output_info: Dict[str, str] = get_doc_output_path(str(doc_path.resolve()))
        output_dir = output_info["output_path"]
        output_image_path = output_info["output_image_path"]
        doc_name = output_info["doc_name"]

        if doc_path.suffix == ".pdf":
            pdf_path = doc_path
        else:
            # 检查格式是否支持 libreoffice 转换
            check_doc_ext(doc_path.suffix, doc_type='libreoffice')
            # 送入 libreoffice 转换
            pdf_path = libreoffice_convert_toolkit(str(doc_path.resolve()), output_dir)

        # === 使用MinerU 解析 PDF 文档 ===
        process_result = None
        results = dict()

        try:
            logger.info(f"第一步: 解析文档, 工具: MinerU, pdf_path={pdf_path}")
            # json_path = mineru_toolkit(pdf_path, output_dir, output_image_path, doc_name)
            results = mineru_toolkit(pdf_path, output_dir, output_image_path, doc_name)
            process_result = True
        except Exception as e:
            logger.error(f"MinerU 解析失败, 失败原因: {str(e)}")
            process_result = False
            raise ValueError(f"MinerU 解析失败, 失败原因: {str(e)}") from e

        finally:  # 无论成功失败,都需要更新数据库记录
            # # 构建需要更新的字段
            # values = {
            #     "doc_output_dir": output_dir if process_result else None,
            #     "doc_json_path": results["json_path"] if process_result else None,
            #     "doc_spans_path": results["spans_path"] if process_result else None,
            #     "doc_layout_path": results["layout_path"] if process_result else None,
            #     "doc_images_path": output_image_path if process_result else None,
            #     "doc_pdf_path": pdf_path if process_result else None,
            #     "process_status": "parsed" if process_result else "parse_failed",
            # }
            if process_result:
                # 构建需要更新的字段
                values = {
                    "doc_output_dir": output_dir,
                    "doc_json_path": results["json_path"],
                    "doc_spans_path": results["spans_path"],
                    "doc_layout_path": results["layout_path"],
                    "doc_images_path": output_image_path,
                    "doc_pdf_path": pdf_path,
                    "process_status": "parsed",
                }
            else:
                # 构建需要更新的字段
                values = {
                    "process_status": "parse_failed",
                }

            logger.info(
                f"开始更新数据库记录, doc_id={doc_id}, 更新字段: {list(values.keys())}, process_status -> {values.get('process_status')}")
            update_record_by_doc_id(table_name=GlobalConfig.MYSQL_CONFIG["file_info_table"], doc_id=doc_id,
                                    kwargs=values)

        # === 页面合并 ===
        json_path = results["json_path"]
        try:
            # 合并页面内容
            logger.info(f"第二步: 按页合并元素, json_path={json_path}")
            save_path = process_doc_by_page(json_path)

            # 如果提供了 doc_id，更新数据库状态
            if doc_id:
                values = {
                    "doc_process_path": save_path,
                    "process_status": "merged"
                }
                logger.info(
                    f"开始更新数据库记录, doc_id={doc_id}, 更新字段: {list(values.keys())}, process_status -> {values.get('process_status')}")
                update_record_by_doc_id(table_name=GlobalConfig.MYSQL_CONFIG["file_info_table"], doc_id=doc_id,
                                        kwargs=values)
        except Exception as e:
            logger.error(f"合并元素失败, 失败原因: {str(e)}")
            values = {"process_status": "merge_failed"}
            logger.info(
                f"开始更新数据库记录, doc_id={doc_id}, 更新字段: {list(values.keys())}, process_status -> {values.get('process_status')}")
            update_record_by_doc_id(table_name=GlobalConfig.MYSQL_CONFIG["file_info_table"], doc_id=doc_id,
                                    kwargs=values)
            raise ValueError(f"合并元素失败, 失败原因: {str(e)}") from e

    except Exception as e:
        if doc_id:
            log_exception(f"文档处理失败", e)
        raise ValueError(f"文档处理失败, 失败原因: {str(e)}")

    logger.info("文档处理完成, 等待文档切块...")
    return save_path


if __name__ == '__main__':
    pass
