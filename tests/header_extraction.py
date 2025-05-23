"""页眉提取"""
from src.utils.json_toolkit.parser import parse_json_content
from src.utils.common.table_formatter import extract_key_fields
from src.utils.common.similar_count import SimilarCount

from rich import print


def remove_header(content_list: list[dict]) -> list:
    """从 content_list 中删除页眉"""
    header_list = []
    for item in content_list:
        header_list.append(item["content"][0])
        item["content"].pop(0)
    return header_list



def check_header_exist(content_list: list[dict]) -> list:
    """ 判断页眉存在与否,并返回平均相似度
    
    Args:
        content_list (list[dict]): 内容列表

    Returns:
        average_similarity (float): 平均相似度
    """

    # 提取每页第一个元素,并提取关键字
    header_key_list = []
    header_page_idx = []
    for item in content_list[8:]:
        # 获取第一个元素
        first_content = item['content'][0]
        # 根据目前的文档,仅存在表格页眉,因此仅提取表格页眉
        if first_content['type'] == 'table':
            table_content = extract_key_fields(first_content['table_body']) 
            header_key_list.append(table_content)
            header_page_idx.append(item["page_idx"])

    # 计算相似度
    similar_count = SimilarCount()
    similar_list = similar_count.get_similarity_to_others(header_key_list[0], header_key_list[1:])

    # 计算平均相似度
    avg_similarity = sum(similar_list) / len(similar_list)

    similarity_list = {
        "similarity_list": similar_list,
        "avg_similarity": avg_similarity
    }

    # 返回平均相似度
    return similarity_list

if __name__ == "__main__":
    json_file_path = "/home/wumingxing/tk_rag/datas/processed/天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225/天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225_content_list.json"
    content_list = parse_json_content(json_file_path)
    avg_similarity = check_header_exist(content_list)
    print(avg_similarity)