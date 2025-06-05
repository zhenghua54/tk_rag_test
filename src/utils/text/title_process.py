"""最终文档内容处理模块"""
import json
from rich import print
from src.utils.common.args_validator import Validator

from src.utils.common.logger import logger
from src.core.llm.extract_summary import extract_table_summary
from src.utils.text.table_process import html_table_to_markdown


def fill_title(file_path: str) -> list:
    """处理 JSON 文件中的表格和图片标题

    Args:
        file_path (str): MinerU 解析后的 json 文件

    Returns:
        list: 处理后的文档内容列表
    """
    # 参数校验
    Validator.validata_json_file(file_path)

    # 统计信息初始化
    table_total, table_cap, table_cap_up, table_cap_miss = 0, 0, 0, 0
    img_total, img_cap, img_cap_up, img_cap_miss = 0, 0, 0, 0

    # 读取文件
    with open(file_path, "r", encoding="utf-8") as f:
        doc_content = json.load(f)

    # 更新表格的标题信息
    for idx, item in enumerate(doc_content):
        caption = None  # 初始化标题
        last_item = doc_content[idx - 1] if idx > 0 else None  # 指定上一个元素

        # 提取表格元素
        if item["type"] == "table":
            table_total += 1

            # 处理列表标题为字符串
            item["table_caption"] = "".join(item["table_caption"]) if isinstance(item["table_caption"], list) else item[
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
                elif last_item and last_item["type"] == "text" and len(last_item["text"]) < 100:
                    caption = str(last_item.get("text", "")).strip()
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
                if last_item and last_item["type"] == "text" and len(last_item["text"]) < 100:
                    caption = str(last_item.get("text", "")).strip()

                if caption:
                    # 处理列表作为标题的异常情况
                    item["img_caption"] = "".join(caption).strip() if isinstance(caption, list) else caption
                    img_cap_up += 1
                else:
                    img_cap_miss += 1

    # 输出统计信息
    logger.info(
        f"图片标题处理完成: {img_total} 张, 无需更新: {img_cap}, 已更新: {img_cap_up}, 缺少标题: {img_cap_miss} | "
        f"表格标题处理完成: {table_total} 张, 已有标题: {table_cap}, 已更新: {table_cap_up}, 缺少标题: {table_cap_miss}"
    )
    return doc_content


if __name__ == '__main__':
    doc_content = "/home/wumingxing/tk_rag/datas/processed/天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225/test_data.json"

    merge_page_res = fill_title(doc_content)
    print(merge_page_res)
