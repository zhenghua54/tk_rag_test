"""
MinerU 官方 API 修改, 调整输出可选项和路径
"""

import os

from magic_pdf.config.enums import SupportedPdfParseMethod
from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze


from src.utils.common.logger import logger
from src.utils.common.pdf_validator import is_pdf_valid
from src.utils.document_path import get_doc_output_path



def parse_pdf(pdf_file_name: str) -> dict:
    """
    解析 PDF 文件, 返回markdown 和 json 文件的保存路径

    Args:
        pdf_file_name (str): PDF 文件路径

    Returns:
        output_markdown_path (str): markdown 文件的保存路径
        output_json_list_path (str): json 文件的保存路径
        output_image_path (str): 图片的保存路径
    """
    # 1. 验证 PDF 文件结构是否合法
    valid_res, valid_content = is_pdf_valid(pdf_file_name)

    if not valid_res:
        logger.error(f"文件 {pdf_file_name} 结构不合法, {valid_content}")
        exit()

    # 2. 获取输出路径
    output_path = get_doc_output_path(pdf_file_name)
    output_path, output_image_path, doc_name = output_path["output_path"], output_path["output_image_path"], output_path["doc_name"]


    # 3. 初始化数据写入器，用于保存图片和 Markdown 文件
    image_writer, md_writer = FileBasedDataWriter(output_image_path), FileBasedDataWriter(output_path)

    # 4. 读取 PDF 文件内容
    reader1 = FileBasedDataReader("")  # 初始化数据读取器
    pdf_bytes = reader1.read(pdf_file_name)  # 读取 PDF 文件的字节内容

    # 5. 创建数据集实例并进行文档分析
    ds = PymuDocDataset(pdf_bytes)  # 使用读取的 PDF 字节创建数据集实例

    # 6. 根据文档分类结果选择处理方式
    if ds.classify() == SupportedPdfParseMethod.OCR:  # 如果文档需要 OCR 处理
        logger.info(f"文档需要 OCR 处理")
        infer_result = ds.apply(doc_analyze, ocr=True)  # 应用自定义模型进行 OCR 分析
        pipe_result = infer_result.pipe_ocr_mode(image_writer)  # 进行 OCR 模式下的管道处理
    else:
        logger.info(f"文档不需要 OCR 处理")
        infer_result = ds.apply(doc_analyze, ocr=False)  # 否则进行普通文本分析
        pipe_result = infer_result.pipe_txt_mode(image_writer)  # 进行文本模式下的管道处理

    # 7. 获取 Markdown 内容
    md_content = pipe_result.get_markdown(output_image_path)

    # 8. 将 Markdown 内容保存到文件中
    markdown_save_path = os.path.join(output_path, f"{doc_name}.md")
    pipe_result.dump_md(md_writer, markdown_save_path, output_image_path)

    # 9. 将内容列表保存为 JSON 文件
    content_list_save_path = os.path.join(output_path, f"{doc_name}_content_list.json")
    pipe_result.dump_content_list(md_writer, content_list_save_path, output_image_path)

    return {
        "output_markdown_path": markdown_save_path,
        "output_json_list_path": content_list_save_path,
        "output_image_path":output_image_path
    }

if __name__ == "__main__":
    pdf_file_name = "/Users/jason/Library/CloudStorage/OneDrive-个人/项目/新届泵业/客户资料/知识问答案例/企业标准（约2300条）/规章制度及设计、采购、产品标准等（约1500条）/QSG A0303008-2024 新界泵业应届大学生培养及管理办法.pdf"  # 替换为实际的 PDF 文件路径

    parse_pdf(pdf_file_name)
