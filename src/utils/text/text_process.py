"""文档内容处理模块"""
from src.utils.common.args_validator import Validator


def merge_page_content(content_list: list) -> dict[str:list]:
    """解析 json 内容,按照 page_idx 进行合并

    Args:
        content_list (list): json 内容列表

    Returns:
        merge_page_contents (dict): 按照 page_idx 进行合并的 json 内容, 格式为 {page_idx:[content,content,content], ...}
    """
    # 参数校验
    Validator.validate_type(content_list, list, "content_list")
    Validator.validate_list_not_empty(content_list, "content_list")


    # 按 page_idx 分组存储内容:
    merge_page_contents = dict()

    for content in content_list:
        # 获取页码
        page_idx = content["page_idx"]
        # 获取除了 page_idx 外的所有内容
        content = {k: v for k, v in content.items() if k != "page_idx"}

        # 将内容添加到对应页码的列表中
        if page_idx not in merge_page_contents:
            merge_page_contents[page_idx] = []
        merge_page_contents[page_idx].append(content)

    return merge_page_contents