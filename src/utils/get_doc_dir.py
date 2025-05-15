"""获取文件相关的路径信息"""

import os
import sys

sys.path.append("/Users/jason/PycharmProjects/tk_rag")

from config import Config


def get_doc_output_dir(doc_path: str) -> dict:
    """
    获取文档的输出目录

    Args:
        doc_path (str): 文档的完整路径

    Returns:
        dict: 包含以下字段的字典：
            - output_path (str): 该文档的输出根目录
            - output_markdown_path (str): 解析后的 markdown 文件目录
            - output_image_path (str): markdown 的图片文件目录
            - output_json_path (str): 解析后的 json 文件目录
    """
    # 提取文档名（去除扩展名）
    doc_name = os.path.splitext(os.path.basename(doc_path))[0]

    # 项目文件处理输出目录
    output_data_dir = Config.PATHS["processed_data"]

    # 根据文件名称,在输出目录下构建自己的输出子目录
    output_path = os.path.join(output_data_dir, doc_name)
    output_markdown_path = os.path.join(output_path, f"{doc_name}.md") 
    output_image_path = os.path.join(output_path, "images")
    output_json_path = os.path.join(output_path, f"{doc_name}.json") 

    return {
        "output_path": output_path,
        "output_markdown_path": output_markdown_path,
        "output_image_path": output_image_path,
        "output_json_path": output_json_path,
    }
