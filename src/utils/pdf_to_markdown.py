"""
pdf2md.py

使用 MagicPDF 工具链将 PDF 文件解析为 Markdown 格式，支持文本和 OCR 模式，
并输出结构化图文内容到指定目录，用于后续语义切块与问答系统处理。
"""
import logging
import os

from codes.config import Config, get_doc_output_dir
from magic_pdf.config.enums import SupportedPdfParseMethod
from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_pdf(config, pdf_file_path: str):
    """
    处理PDF文件的主要函数

    Args:
        config (Config): 全局配置对象
        pdf_file_path (str): 待处理的 PDF 文件路径

    Returns:
        bool: 处理是否成功
    """
    try:
        # 获取当前 PDF 的输出路径配置
        output_paths = get_doc_output_dir(config, pdf_file_path)

        logger.info(f"开始处理文件: {pdf_file_path}")

        # 提取图片目录与 markdown 输出目录名称
        image_dir = str(os.path.basename(output_paths['output_image_path']))  # 图片目录名（用于插入图片引用）:images
        markdown_dir = str(os.path.dirname(output_paths['output_markdown_path']))  # markdown 目录名（用于输出 markdown 文件）

        # 初始化写入器（图像和 Markdown）
        image_writer = FileBasedDataWriter(image_dir)
        md_writer = FileBasedDataWriter(markdown_dir)

        # 读取 PDF 文件为字节流
        logger.info("正在读取PDF文件...")
        reader = FileBasedDataReader("")
        pdf_bytes = reader.read(pdf_file_path)

        # 构造 PDF 数据集对象
        logger.info("正在创建数据集实例...")
        ds = PymuDocDataset(pdf_bytes)

        # 判断是否为 OCR 类型，并调用相应模式处理
        if ds.classify() == SupportedPdfParseMethod.OCR:
            logger.info("使用OCR模式处理PDF...")
            infer_result = ds.apply(doc_analyze, ocr=True)
            pipe_result = infer_result.pipe_ocr_mode(image_writer)
        else:
            logger.info("使用文本模式处理PDF...")
            infer_result = ds.apply(doc_analyze, ocr=False)
            pipe_result = infer_result.pipe_txt_mode(image_writer)

        # 提取 Markdown 格式内容
        logger.info("正在生成并保存Markdown内容...")

        md_content = pipe_result.get_markdown(image_dir)  # 生成 Markdown 格式的文本（含图文结构）

        # 确保输出路径存在
        os.makedirs(os.path.dirname(output_paths['output_markdown_path']), exist_ok=True)
        os.makedirs(os.path.dirname(output_paths['output_image_path']), exist_ok=True)

        # 写入 Markdown 内容
        md_writer.write(
            output_paths['output_markdown_path'],
            md_content.encode("utf-8")
        )  # 手动写入生成的文本内容

        logger.info(f"文件处理完成，输出保存在: {output_paths['output_markdown_path']}")
        return True

    except Exception as e:
        logger.error(f"处理文件时发生错误: {str(e)}")
        return False


if __name__ == "__main__":
    config = Config()
    # 本模块供 file2md 调用使用，不直接执行处理逻辑
    pass  # 统一在 file2md 中调用
