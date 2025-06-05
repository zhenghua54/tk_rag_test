"""处理文档内容, 包括表格、图片、文本等"""
import json
import os
import sys
from collections import defaultdict
from rich import print

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

from src.utils.common.logger import logger
from src.utils.common.args_validator import Validator


def merge_page(doc_content: list) -> dict[str:list]:
    """解析 json 内容, 根据 page_idx 合并 text 元素

    Args:
        doc_content (list): MinerU 解析后的 json 内容列表

    Returns:
        merge_page_contents (dict): 按照 page_idx 进行合并的 json 内容, 格式为 {page_idx:[content,content,content], ...}
    """
    # 参数校验
    Validator.validate_type(doc_content, list, "doc_content")
    Validator.validate_list_not_empty(doc_content, "doc_content")

    merge_page_contents = defaultdict(list)  # 初始化页面存储
    text_list = []  # 临时存储文本段
    tmp_idx = None  # 当前页码缓存

    logger.info("开始按页合并文档...")

    for content in doc_content:
        # 获取当前页码
        page_idx = content["page_idx"]

        if tmp_idx is not None and page_idx != tmp_idx:
            if text_list:
                merge_page_contents[tmp_idx].append({
                    "type": "text",
                    "text": "".join(text_list),
                    "page_idx": tmp_idx
                })
                text_list = []

        # 更新当前页码
        tmp_idx = page_idx

        # 处理同页内容
        if content["type"] == "text":
            text_list.append(content["text"])
        # 非文本类型，保存积累的文本后保存该元素
        else:
            if text_list:
                merge_page_contents[page_idx].append({
                    "type": "text",
                    "text": "".join(text_list),
                    "page_idx": page_idx
                })
                text_list = []
            merge_page_contents[page_idx].append(content)

    # 处理最后一页累积的文本
    if text_list:
        merge_page_contents[tmp_idx].append({
            "type": "text",
            "text": "".join(text_list),
            "page_idx": tmp_idx
        })

    logger.info("文档按页合并完成，合并后的格式为: {page_idx:[page_content], }")
    return merge_page_contents

if __name__ == '__main__':
    file_path = "/home/wumingxing/tk_rag/datas/processed/天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225/test_title_data.json"
    with open(file_path, "r", encoding="utf-8") as f:
        doc_content = json.load(f)
    merge_page_contents = merge_page(doc_content)
    print(merge_page_contents)