"""获取文件相关的路径信息"""

import os

from config.settings import Config


def get_doc_output_path(doc_path: str) -> dict:
    """
    获取文档的输出目录

    Args:
        doc_path (str): 源文档的路径

    Returns:
        dict: 包含以下字段的字典：
            - output_path (str): 该文档的输出根目录
            - output_image_path (str): markdown 的图片文件目录
    """
    # 获取文档的绝对路径
    doc_path = os.path.abspath(doc_path)

    # 提取文档名（去除扩展名）
    doc_name = os.path.splitext(os.path.basename(doc_path))[0]

    # 项目文件处理输出目录
    output_data_dir = Config.PATHS["processed_data"]

    # 根据文件名称,在输出目录下构建自己的输出子目录
    output_path = os.path.join(output_data_dir, doc_name)
    output_image_path = os.path.join(output_path, "images")

    return {
        "output_path": output_path,
        "output_image_path": output_image_path,
        "doc_name": doc_name,
    }


# def get_translated_doc_output_path(doc_path: str) -> dict:
#     """
#     获取转换为 PDF 后的文档的输出目录
#     """
#     doc_path = os.path.abspath(doc_path)

#     # 项目文件处理输出目录
#     output_data_dir = Config.PATHS["translated_data"]

#     return {
#         "output_data_dir": output_data_dir,
#     }


if __name__ == "__main__":
    get_doc_output_path(
        "/Users/jason/Library/CloudStorage/OneDrive-个人/项目/新届泵业/客户资料/知识问答案例/企业标准（约2300条）/规章制度及设计、采购、产品标准等（约1500条）/QSG A0303008-2024 新界泵业应届大学生培养及管理办法.pdf")
