"""PDF/office 文件解析,返回 json 文件信息"""

import os

from magic_pdf.config.enums import SupportedPdfParseMethod
from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze


from src.utils.common.logger import logger
from src.utils.file.file_validator import assert_pdf_validity
from src.utils.file.doc_path import get_doc_output_path
from src.core.document.office_convert import convert_to_pdf



def parse_pdf_file(file_path: str) -> dict:
    """
    解析 PDF 文件, 返回 json 文件信息

    Args:
        file_path (str): PDF 文件路径

    Returns:
        json_path (str): json 文件的保存路径
        image_path (str): 图片的保存路径
        doc_name (str): 文档名称
        output_dir (str): 输出路径
    """
    
    # 校验文件是否存在
    if not os.path.exists(file_path):
        logger.error(f"文件 {file_path} 不存在")
        return False

    
    # 验证 PDF 文件结构是否合法
    valid_res, valid_content = is_pdf_valid(pdf_file_name)

    if not valid_res:
        logger.error(f"文件 {pdf_file_name} 结构不合法, {valid_content}")
        exit()

    # 获取输出路径
    output_dir = get_doc_output_path(pdf_file_name)
    output_path, image_path, doc_name = output_dir["output_path"], output_dir["output_image_path"], output_dir["doc_name"]


    # 初始化数据写入器，用于保存图片和 Markdown 文件
    image_writer, md_writer = FileBasedDataWriter(image_path), FileBasedDataWriter(output_path)

    # 读取 PDF 文件内容
    reader1 = FileBasedDataReader("")  # 初始化数据读取器
    pdf_bytes = reader1.read(pdf_file_name)  # 读取 PDF 文件的字节内容

    # 创建数据集实例并进行文档分析
    ds = PymuDocDataset(pdf_bytes)  # 使用读取的 PDF 字节创建数据集实例

    # 根据文档分类结果选择处理方式
    if ds.classify() == SupportedPdfParseMethod.OCR:  # 如果文档需要 OCR 处理
        logger.info(f"文档需要 OCR 处理")
        infer_result = ds.apply(doc_analyze, ocr=True)  # 应用自定义模型进行 OCR 分析
        pipe_result = infer_result.pipe_ocr_mode(image_writer)  # 进行 OCR 模式下的管道处理
    else:
        logger.info(f"文档不需要 OCR 处理")
        infer_result = ds.apply(doc_analyze, ocr=False)  # 否则进行普通文本分析
        pipe_result = infer_result.pipe_txt_mode(image_writer)  # 进行文本模式下的管道处理

    # 将内容列表保存为 JSON 文件
    json_path = os.path.join(output_path, f"{doc_name}_content_list.json")
    pipe_result.dump_content_list(md_writer, json_path, image_path)

    return {
        "json_path": json_path,
        "image_path": image_path,
        "doc_name": doc_name,
        "output_dir": output_dir
    }
    
def parse_office_file(file_path: str) -> dict:
    """
    解析 Office 文件, 返回 json 文件信息
    """
    if not os.path.exists(file_path):
        logger.error(f"文件 {file_path} 不存在")
        return None
    
    if os.path.splitext(file_path)[1] not in Config.SUPPORTED_FILE_TYPES["libreoffice"]:
        logger.error(f"暂不支持该格式文件,目前支持的格式为: {Config.SUPPORTED_FILE_TYPES['libreoffice']}")
        return None
    
    # 获取输出路径
    output_path = get_doc_output_path(file_path)
    output_path, output_image_path, doc_name = output_path["output_path"], output_path["output_image_path"], output_path["doc_name"]
    
    
    # 转换为 PDF
    logger.info(f"开始转换为 PDF")
    pdf_path = convert_to_pdf(
        file_path,
        output_path
    )
    if pdf_path:  # 检查转换是否成功
        logger.info(f"文件转换成功: {pdf_path}")
        return pdf_path
    else:
        logger.error(
            f"文件转换失败: {file_path}"
        )
        return None
    
    

if __name__ == "__main__":
    pdf_file_name = "/Users/jason/Library/CloudStorage/OneDrive-个人/项目/新届泵业/客户资料/知识问答案例/企业标准（约2300条）/规章制度及设计、采购、产品标准等（约1500条）/QSG A0303008-2024 新界泵业应届大学生培养及管理办法.pdf"  # 替换为实际的 PDF 文件路径

    parse_pdf(pdf_file_name)
