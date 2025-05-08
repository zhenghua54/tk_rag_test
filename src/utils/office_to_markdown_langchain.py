"""
office2md_langchain.py

使用 LangChain 的 Unstructured 文档加载器将 .docx 和 .pptx 文件加载为 Document 对象，
并将内容转换为标准化的 Markdown 格式，便于后续语义切块和 RAG 系统处理。
"""

import logging
# 标准库导入
import os
import sys

from codes.config import Config
# LangChain 社区文档加载器（支持 Word 和 PPT）
from langchain_community.document_loaders import (
    Docx2txtLoader,
    UnstructuredExcelLoader,
    UnstructuredPowerPointLoader,
)

# 添加项目根目录到 Python 路径，确保本地模块可导入
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# 设置日志格式与级别
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_documents(file_path):
    """
    根据文件扩展名选择合适的 LangChain 文档加载器，并返回文档对象列表。

    支持的文件类型包括：
        - .docx：使用 UnstructuredWordDocumentLoader 加载
        - .pptx：使用 UnstructuredPowerPointLoader 加载

    Args:
        file_path (str): 要加载的文件路径

    Returns:
        list[Document] | bool: 返回包含文档内容的 Document 对象列表，若不支持文件类型则返回 False
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".docx":
        loader = UnstructuredWordDocumentLoader(file_path)
    elif ext == ".pptx":
        loader = UnstructuredPowerPointLoader(file_path)
    else:
        logger.error(f"不支持的文件类型: {ext}")
        return False

    logger.info(f"使用 {loader.__class__.__name__} 加载文件: {file_path}")
    return loader.load()


def save_docs_to_markdown(docs, output_markdown_file):
    """
    将 LangChain 的 Document 列表保存为 Markdown 文件，供后续 chunk 使用。

    Args:
        docs (list): Document 对象列表
        output_markdown_file (str): 输出 markdown 文件路径
    """

    with open(output_markdown_file, "w", encoding="utf-8") as f:
        for i, doc in enumerate(docs):
            f.write(f"## Chunk {i + 1}\n\n")
            f.write(doc.page_content.strip() + "\n\n")
            for k, v in doc.metadata.items():
                f.write(f"*{k}: {v}*\n")
            f.write("\n---\n\n")
    logger.info(f"已保存 Markdown 文件: {output_markdown_file}")


def process_file_to_md(input_file, output_markdown_path):
    """
    主处理函数：将支持的 office 文件加载后保存为 markdown 格式。

    Args:
        input_file (str): 输入的文件路径
        output_markdown_path (str): 输出的 markdown 文件路径

    Returns:
        bool: 处理是否成功
    """

    docs = load_documents(input_file)
    if docs:
        # 若文档成功加载，则创建输出目录并保存为 markdown 文件
        os.makedirs(os.path.dirname(output_markdown_path), exist_ok=True)
        output_markdown_file = os.path.join(os.path.dirname(output_markdown_path),
                                            os.path.basename(input_file).replace(os.path.splitext(input_file)[1],
                                                                                 ".md"))
        save_docs_to_markdown(docs, output_markdown_file)
        return True
    else:
        logger.error("文档加载失败，未保存 Markdown")
        return False


if __name__ == "__main__":
    from config import Config

    config = Config()

    # 示例入口：将指定 pptx 文件转换为 markdown 文件，适用于测试运行
    input_file = "/Users/jason/Library/Mobile Documents/com~apple~CloudDocs/PycharmProjects/tk_rag_demo/datas/origin_data/组织过程资产平台需求规格说明书.docx"
    process_file_to_md(input_file, config.output_data_dir)
