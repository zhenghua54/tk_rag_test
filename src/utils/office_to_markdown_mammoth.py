"""
office2md_mammoth.py

使用 mammoth 库将 docx 文件转换为 Markdown 格式文本，并保存为 .md 文件。
适用于结构清晰的 Word 文件，常用于语义分块前的格式标准化处理。
"""
import logging
import os

import mammoth

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def convert_docx_to_markdown(office_file_path: str) -> str:
    """
    使用 mammoth 将 docx 文件转换为 markdown 字符串

    Args:
        office_file_path (str): docx 文件路径

    Returns:
        str: 转换后的 markdown 文本内容
    """

    with open(office_file_path, "rb") as docx_file:
        result = mammoth.convert_to_markdown(docx_file)
        markdown_text = result.value
        logger.info(f"转换成功: {office_file_path} -> Markdown 字符数: {len(markdown_text)}")
        return markdown_text


def process_docx_file(office_file_path: str, doc_output_dir: str):
    """
    将 docx 文件转换为 markdown，并保存为 .md 文件

    Args:
        office_file_path (str): 输入的 docx 文件路径
        doc_output_dir (str): 输出的 markdown 文件路径

    Returns:
        bool: 是否成功处理并保存
    """
    # 读取 docx 文件并转换为 markdown 文本
    md_text = convert_docx_to_markdown(office_file_path)

    if md_text:
        # 创建输出目录（如果不存在）
        os.makedirs(os.path.dirname(doc_output_dir), exist_ok=True)
        # 将 markdown 文本写入文件
        with open(doc_output_dir, "w", encoding="utf-8") as f:
            f.write(md_text)
        logger.info(f"已保存 Markdown 文件: {doc_output_dir}")
        return True
    else:
        logger.error("Markdown 内容为空，未保存")
        return False


if __name__ == "__main__":
    # 该模块作为工具函数被其他模块调用（如 file2md），此处不直接执行处理逻辑
    pass  # 统一在 file2md 中调用
