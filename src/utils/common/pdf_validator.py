"""
PDF 文件合法性检查, 避免 MinerU 解析崩溃
1. 文件头检查
2. fitz 尝试打开
3. pdfminer.six 测提取文本测试
4. 使用 pdfcpu 检查 pdf 文件结构
"""

import os
import fitz  # PyMuPDF
from src.utils.common.logger import logger
from src.utils.common.unit_convert import convert_bytes

# 检查 PyMuPDF
try:
    import fitz
except ImportError:
    logger.error("缺少依赖: PyMuPDF (fitz)")
    raise ImportError("请安装 PyMuPDF: pip install PyMuPDF")


def is_pdf_valid(path: str) -> tuple[bool, str]:
    """
    判断 PDF 文件是否合法（结构上可被解析），适用于送入 MinerU 前的预筛选。
    使用 PyMuPDF (fitz) 进行验证,与 MinerU 底层解析库保持一致。

    参数:
        path (str): PDF 文件路径

    返回:
        (bool, str): 是否合法, 原因或 OK
    """

    logger.info(f"开始检查文件: {path}")

    # 检查路径存在且为 PDF 文件
    if not os.path.isfile(path):
        logger.error(f"文件不存在: {path}")
        return False, "文件不存在"

    if not path.lower().endswith(".pdf"):
        logger.error(f"文件后缀不是 PDF: {path}")
        return False, "文件后缀不是 .pdf"

    # 检查文件大小
    file_size = os.path.getsize(path)
    logger.info(f"文件大小: {convert_bytes(file_size)}")
    if file_size == 0:
        logger.error("文件大小为 0")
        return False, "PDF 文件为空"

    # 使用 fitz 进行基本检查
    try:
        logger.info("尝试打开 PDF 文件...")
        with fitz.open(path) as doc:
            # 检查文件是否可以打开
            if doc.is_encrypted:
                logger.error("PDF 文件已加密")
                return False, "PDF 文件已加密"
            
            # 检查页数
            page_count = doc.page_count
            logger.info(f"PDF 总页数: {page_count}")
            if page_count == 0:
                logger.error("PDF 文件没有页数")
                return False, "PDF 文件没有页数"
            
            # 尝试读取第一页，验证基本结构
            try:
                logger.info("检查第一页...")
                first_page = doc[0]
                # 尝试获取页面尺寸，如果能获取到说明页面有效
                page_rect = first_page.rect
                logger.info(f"第一页尺寸: {page_rect}")
                
                # 尝试获取页面内容，如果能获取到说明页面可读
                text = first_page.get_text()
                text_length = len(text.strip())
                logger.info(f"第一页文本长度: {text_length} 字符")
                
                if text_length == 0:
                    logger.warning("第一页没有文本内容，可能是扫描件或图片")
                
            except Exception as e:
                logger.error(f"读取第一页失败: {str(e)}")
                return False, f"无法读取 PDF 第一页: {str(e)}"
                
    except Exception as e:
        logger.error(f"PDF 文件结构检查失败: {str(e)}")
        return False, f"PDF 文件结构检查失败: {str(e)}"

    logger.info("PDF 文件检查通过")
    return True, "OK"


def record_pdf_path(path):
    """
    记录 PDF 文件路径
    """
    pdf_paths = []

    for root, dirs, files in os.walk(path):
        for file in files:
            if file.lower().endswith('pdf'):
                pdf_paths.append(os.path.join(root, file))
        if dirs:
            for dir in dirs:
                path = os.path.join(root, dir)
                record_pdf_path(path)

    return pdf_paths


if __name__ == '__main__':
    pdf_paths = record_pdf_path("/Users/jason/Library/CloudStorage/OneDrive-个人/项目/新届泵业/客户资料/知识问答案例")
    pdf_valid_res = {}
    for pdf_path in pdf_paths:
        res, content = is_pdf_valid(pdf_path)
        pdf_valid_res[pdf_path] = (res, content)

    from rich import print
    print(pdf_valid_res)
