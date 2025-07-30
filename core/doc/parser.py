"""处理文档内容, 包括表格、图片、文本等"""

import hashlib
import json
import shutil
import threading
import time
import uuid
from pathlib import Path

from databases.mysql.operations import file_op
from utils.file_ops import get_doc_output_path, libreoffice_convert_toolkit, mineru_toolkit
from utils.log_utils import log_exception, logger
from utils.status_sync import sync_status_safely
from utils.validators import check_doc_ext, check_local_doc_exists, validate_param_type

# 简单缓存锁
cache_lock = threading.Lock()


def process_doc_by_page(json_doc_path: str):
    """读取MinerU解析后的 JSON 文档, 填充表格和图片标题, 并按页合并内容

    Args:
        json_doc_path (str): MinerU 解析后的 json 文件路径
    """

    start_time = time.time()
    logger.info(f"[页面处理] 开始处理, json_path={json_doc_path}")

    with open(json_doc_path, encoding="utf-8") as f:
        json_content = json.load(f)

    doc_hash = hashlib.md5(json_doc_path.encode("utf-8")).hexdigest()
    temp_dir = None

    # 使用锁保护缓存目录操作
    with cache_lock:
        # 为每个文档创建独立的缓存目录，避免并发冲突
        temp_root = Path("page_cache")
        temp_dir = temp_root / f"{doc_hash}_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"创建缓存目录: {temp_dir}")

    # 统计信息初始化
    table_total, table_cap, table_cap_up, table_cap_miss = 0, 0, 0, 0
    img_total, img_cap, img_cap_up, img_cap_miss = 0, 0, 0, 0

    # 定义常量
    max_title_len = 100

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
                    page_contents.append({"type": "text", "text": "\n".join(text_buffer), "page_idx": current_page})
                    text_buffer = []

                # 保存当前页内容
                if page_contents:
                    page_file = temp_dir / f"page_{current_page}.json"
                    with open(page_file, "w", encoding="utf-8") as pf:
                        json.dump(page_contents, pf, indent=2, ensure_ascii=False)
                    page_contents = []  # 清空当前页内容

            current_page = page_idx

            # 处理文本元素
            if item["type"] == "text":
                text_buffer.append(item["text"])
                # 如果下一个不是文本,或到末尾, 则保存当前文本
                if (idx == len(json_content) - 1 or json_content[idx + 1]["type"] != "text") and text_buffer:
                    page_contents.append({"type": "text", "text": "\n".join(text_buffer), "page_idx": current_page})
                    text_buffer = []

            # 提取表格元素
            elif item["type"] == "table":
                table_total += 1
                # 处理表格标题
                item["table_caption"] = (
                    "".join(item["table_caption"]) if isinstance(item["table_caption"], list) else item["table_caption"]
                )

                # 处理表格标题
                if not item["table_caption"].strip():
                    last_item = json_content[idx - 1] if idx > 0 else None
                    if last_item and last_item["type"] == "table":
                        # 修复：安全地处理 table_caption，避免索引越界
                        last_caption = last_item.get("table_caption", "")
                        if isinstance(last_caption, list) and len(last_caption) > 0:
                            caption = str(last_caption[0]).strip()
                        elif isinstance(last_caption, str) and last_caption.strip():
                            caption = last_caption.strip()
                        else:
                            caption = None

                    elif last_item and last_item["type"] == "text" and len(last_item["text"]) < max_title_len:
                        caption = last_item.get("text").strip()
                    else:
                        caption = None

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
                item["img_caption"] = (
                    ", ".join(item["img_caption"]) if isinstance(item["img_caption"], list) else item["img_caption"]
                )

                # 处理图片标题
                if not item["img_caption"].strip():
                    last_item = json_content[idx - 1] if idx > 0 else None
                    if last_item and last_item["type"] == "text" and len(last_item["text"]) < max_title_len:
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

        # 处理最后一页遗留的文本
        if current_page is not None:
            if text_buffer:
                page_contents.append({"type": "text", "text": "\n".join(text_buffer), "page_idx": current_page})
                text_buffer = []

            if page_contents:
                page_file = temp_dir / f"page_{current_page}.json"
                try:
                    with open(page_file, "w", encoding="utf-8") as pf:
                        json.dump(page_contents, pf, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.error(f"[页面处理] 最后一页写入失败, file={page_file}, error_msg={str(e)}")
                    raise RuntimeError(f"最后一页写入失败: {page_file}, 错误: {str(e)}") from e

        duration = int((time.time() - start_time) * 1000)
        logger.info(
            f"[页面处理] 内容合并完成, duration={duration}ms, 图片总数={img_total}, 无需更新={img_cap}, 已更新={img_cap_up}, 缺少标题={img_cap_miss}, 表格总数={table_total}, 已有标题={table_cap}, 已更新={table_cap_up}, 缺少标题={table_cap_miss}"
        )

    except Exception as e:
        logger.error(f"[页面处理失败] error_msg={str(e)}")
        raise

    # 合并页面
    try:
        # 合并所有缓存页
        logger.info("[页面合并] 开始合并缓存页")
        merged = {}
        # 遍历临时目录中的所有页面文件，按页码顺序合并内容
        for page_file in sorted(temp_dir.glob("page_*.json"), key=lambda x: int(x.stem.split("_")[1])):
            if not page_file.exists():
                raise FileNotFoundError(f"找不到页面文件: {page_file}")
            page_idx = int(page_file.stem.split("_")[1])
            with open(page_file, encoding="utf-8") as pf:
                # 读取每页的列表合并到 merged中
                merged[str(page_idx)] = json.load(pf)

        # 保存合并后的文件
        save_path = Path(json_doc_path).parent / f"{Path(json_doc_path).stem}_merged.json"
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)

        logger.info(f"[页面合并] 合并完成, 输出文件={save_path}")
        return str(save_path)

    except Exception as e:
        logger.error(f"[页面合并失败] error_msg={str(e)}")
        log_exception("页面合并异常", exc=e)
        raise ValueError(f"文件合并页面异常: {str(e)}") from e

    finally:
        # 清理缓存(锁保护)
        with cache_lock:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir)
                logger.debug(f"[页面处理] 删除缓存目录={temp_dir}")

            # 检查是否还有其他缓存目录(新任务在处理)
            temp_root = Path("page_cache")
            if temp_root.exists():
                sub_dirs = list(temp_root.iterdir())
                if not sub_dirs:
                    temp_root.rmdir()
                    logger.debug(f"[页面处理] 删除空的缓存根目录={temp_root}")


# === 主入口函数（后台处理） ===
def process_doc_content(doc_path: str, doc_id: str, request_id: str = None, callback_url: str | None = None) -> str:
    """处理文档内容:
    1. 非PDF文件先转换为PDF
    2. 使用MinerU解析 PDF 文档
    3. 填充表格和图片标题, 并按页合并内容, 写入json文件, 命名为 {json_doc_path}_merged.json
    4. 如果提供了 doc_id, 则更新数据库中的处理状态

    Args:
        doc_path (str): 源文档路径
        doc_id (str, optional): 文档ID, 如果提供则会更新数据库状态
        request_id (str, optional): 请求ID, 如果提供则会更新数据库状态
        callback_url (str, optional): 回调 URL, 为空时代表无需反馈文件状态

    Returns:
        save_path (str): 处理后的文档路径
    """
    start_time = time.time()
    logger.info(f"[文档处理] 开始, request_id={request_id}, doc_path={doc_path}, doc_id={doc_id}")

    try:
        # 验证参数
        validate_param_type(doc_path, str, "源文档路径")  # 参数类型验证
        check_local_doc_exists(doc_path)  # 文件路径验证
        doc_path = Path(doc_path)

        # 获取文档的输出路径
        output_info: dict[str, str] = get_doc_output_path(str(doc_path.resolve()))
        output_dir = output_info["output_path"]
        output_image_path = output_info["output_image_path"]
        doc_name = output_info["doc_name"]

        if doc_path.suffix == ".pdf":
            pdf_path = doc_path
        else:
            # 检查格式是否支持 libreoffice 转换
            check_doc_ext(doc_path.suffix, doc_type="libreoffice")
            # 送入 libreoffice 转换
            pdf_path = libreoffice_convert_toolkit(str(doc_path.resolve()), output_dir)

        # === 使用MinerU 解析 PDF 文档 ===
        process_result = None
        results = dict()

        try:
            logger.info(f"[文档解析] 开始解析, request_id={request_id}, 工具=MinerU, pdf_path={pdf_path}")
            results = mineru_toolkit(pdf_path, output_dir, output_image_path, doc_name)
            process_result = True
            logger.info(f"[文档解析] 解析成功, request_id={request_id}")
        except Exception as e:
            logger.error(f"[文档解析失败] request_id={request_id}, error_msg={str(e)}")
            process_result = False
            raise ValueError(f"MinerU 解析失败, 失败原因: {str(e)}") from e

        finally:  # 无论成功失败,都需要更新数据库记录
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

                if callback_url:
                    # 同步状态到外部系统
                    sync_status_safely(doc_id, "parsed", request_id, callback_url)

            else:
                # 构建需要更新的字段
                values = {"process_status": "parse_failed"}
                if callback_url:
                    # 同步状态到外部系统
                    sync_status_safely(doc_id, "parse_failed", request_id, callback_url)

            logger.info(
                f"[数据库更新] request_id={request_id}, doc_id={doc_id}, process_status={values.get('process_status')}"
            )
            file_op.update_by_doc_id(doc_id, values)

        # === 页面合并 ===
        json_path = results["json_path"]
        try:
            # 合并页面内容
            logger.info(f"[页面合并] 开始合并, request_id={request_id}, 源文件={json_path}")
            save_path = process_doc_by_page(json_path)
            logger.info(f"[页面合并] 合并完成, request_id={request_id}, 输出文件={save_path}")
        except Exception as e:
            logger.error(f"[页面合并失败] request_id={request_id}, error_msg={str(e)}")
            log_exception(f"request_id={request_id}, 合并元素异常", exc=e)
            logger.info(f"[数据库更新] request_id={request_id}, 合并失败, 更新状态为 merge_failed")

            if callback_url:
                # 同步状态到外部系统
                sync_status_safely(doc_id, "merge_failed", request_id, callback_url)

            file_op.update_by_doc_id(doc_id=doc_id, data={"process_status": "merge_failed"})
            raise ValueError(f"合并元素失败, 失败原因: {str(e)}") from e

        # 更新最终状态
        logger.info(f"[数据库更新] request_id={request_id}, doc_id={doc_id}, process_status=merged")

        if callback_url:
            # 同步状态到外部系统
            sync_status_safely(doc_id, "merged", request_id, callback_url)

        file_op.update_by_doc_id(doc_id=doc_id, data={"doc_process_path": save_path, "process_status": "merged"})

        duration = int((time.time() - start_time) * 1000)
        logger.info(f"[文档处理] 处理完成, request_id={request_id}, duration={duration}ms, 等待文档切块")
        return save_path

    except Exception as e:
        logger.error(f"[文档处理失败] request_id={request_id}, error_msg={str(e)}")
        log_exception(f"request_id={request_id}, 文档内容处理异常", exc=e)
        raise


if __name__ == "__main__":
    pass
