"""
JSON 文件解析工具
"""

import json
import os
from rich import print

def read_json_file(file_path: str) -> dict:
    """读取 JSON 文件

    Args:
        file_path (str): JSON 文件路径

    Returns:
        dict: JSON 文件内容
    """

    if not os.path.exists(str(file_path)):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    try:
        with open(str(file_path), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise ValueError(f"读取 JSON 文件失败: {e}")


def parse_json_content(json_content: str) -> dict:
    """解析 json 内容,按照 page_idx 进行合并

    Args:
        json_content (str): json 内容

    Returns:
        context_list (list[dict]): 按照 page_idx 进行合并的 json 内容, 格式为 [{page_idx,content}]
    """

    # 1. 将每页内容先进行拼接,[{page_idx:[content,content,content]},]
    context_list = []
    
    # 按 page_idx 分组存储内容
    page_contents = {}
    
    for item in json_content:
        # 获取页码
        page_idx = item["page_idx"]
        # 获取除了 page_idx 外的所有内容
        content = {k: v for k, v in item.items() if k != "page_idx"}
        
        # 将内容添加到对应页码的列表中
        if page_idx not in page_contents:
            page_contents[page_idx] = []
        page_contents[page_idx].append(content)
    
    # 转换为最终格式
    for page_idx, contents in page_contents.items():
        context_list.append({
            "page_idx": page_idx,
            "content": contents
        })

    return context_list


def parse_json_file(json_file_path: str) -> dict:
    """解析 json 内容,按照 page_idx 进行合并

    Args:
        json_file_path (str): json 文件路径

    Returns:
        context_list (list[dict]): 按照 page_idx 进行合并的 json 内容, 格式为 [{page_idx,content}]
    """
    json_content = read_json_file(json_file_path)
    context_list = parse_json_content(json_content)
    return context_list


def merge_header_footer(content_list: list[dict], header_list: list=None, footer_list: list=None) -> list:
    """将页眉 页脚合并到 content_list 中,并返回合并后的内容列表
    
    Args:
        content_list (list[dict]): 内容列表
        header_list (list): 页眉列表
        footer_list (list): 页脚列表

    Returns:
        merge_json_content (list): 合并后的内容列表
    """

    merge_json_content = [
        {"content": content_list},
        {"header": header_list},
        {"footer": footer_list}
    ]

    return merge_json_content




if __name__ == "__main__":
    # 1. 读取 JSON 文件
    json_content = read_json_file("/home/wumingxing/tk_rag/datas/processed/天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225/天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225_content_list.json")
    # for item in json_content:
    #     # if item["page_idx"] in range(30, 35):
    #     # if item["type"] == "table" and item["table_body"] == '服务作业指导书':
    #     if item["page_idx"] in range(30, 35) and item["type"] == "table":
    #         print(item)
    #         print("=" * 100,'\n')

    # 2. 解析 JSON 文件
    context_list = merge_json_content(json_content)
    print(context_list[0])
    print(len(context_list))

