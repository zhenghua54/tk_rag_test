"""使用 LibreOffice 进行文件转换的模块"""
import os
import subprocess
import shutil
import tempfile
from typing import Optional, Tuple
from pathvalidate import sanitize_filename
from pathlib import Path

from src.api.error_codes import ErrorCode
from src.api.response import APIException
from src.utils.common.logger import logger
from config.settings import Config
from src.utils.doc_toolkit import get_doc_output_path
from src.utils.validator.file_validator import FileValidator

# # 添加新的导入
# import docx
# from reportlab.lib.pagesizes import letter
# from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
# from reportlab.lib.styles import getSampleStyleSheet


def check_system_requirements() -> Tuple[bool, str]:
    """
    检查系统环境要求

    Returns:
        Tuple[bool, str]: (是否满足要求, 错误信息)
    """

    # 检查 LibreOffice 是否安装
    if not os.path.exists(Config.PATHS["libreoffice_path"]):
        return False, f"LibreOffice 未安装或路径不正确: {Config.PATHS['libreoffice_path']}"
    else:
        logger.debug(f"LibreOffice 已安装: {Config.PATHS['libreoffice_path']}")

    # 检查中文字体
    try:
        # 检查高质量中文字体，优先使用思源系列字体
        chinese_fonts = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Noto Sans CJK
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",  # Noto Serif CJK
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",  # 备选路径
            "/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc",  # 备选路径
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # 文泉驿微米黑
            "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",  # 文泉驿正黑
        ]

        font_found = False
        found_font = None
        for font in chinese_fonts:
            if os.path.exists(font):
                font_found = True
                found_font = font
                break

        if not font_found:
            # 尝试使用 fc-list 命令检查字体
            try:
                result = subprocess.run(
                    ["fc-list", ":", "lang=zh"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if result.returncode == 0 and result.stdout.strip():
                    font_found = True
                    found_font = "通过 fc-list 检测到中文字体"
            except FileNotFoundError:
                pass

        if not font_found:
            return False, "未检测到中文字体，建议安装：\n" + \
                          "Ubuntu/Debian: sudo apt install fonts-noto-cjk\n" + \
                          "CentOS/RHEL: sudo yum install google-noto-cjk-fonts"
        else:
            logger.debug(f"已检测到中文字体: {found_font}")
        return True, ""

    except Exception as e:
        return False, f"检查系统环境时发生错误: {str(e)}"


# def docx_to_pdf_python(docx_path: str, output_path: str) -> str:
#     """
#     使用Python库将DOCX转换为PDF
#
#     Args:
#         docx_path (str): DOCX文件路径
#         output_path (str): PDF输出目录
#
#     Returns:
#         str: 生成的PDF文件路径
#     """
#     try:
#         logger.debug(f"尝试使用Python库将DOCX转换为PDF: {docx_path}")
#         # 确保输出目录存在
#         os.makedirs(output_path, exist_ok=True)
#
#         # 构建输出文件路径
#         docx_filename = Path(docx_path).stem
#         pdf_path = os.path.join(output_path, f"{docx_filename}.pdf")
#
#         # 读取DOCX文件
#         doc = docx.Document(docx_path)
#
#         # 创建PDF文档
#         pdf = SimpleDocTemplate(pdf_path, pagesize=letter)
#         styles = getSampleStyleSheet()
#         flowables = []
#
#         # 处理文档内容
#         for para in doc.paragraphs:
#             if para.text:
#                 p = Paragraph(para.text, styles['Normal'])
#                 flowables.append(p)
#                 flowables.append(Spacer(1, 12))
#
#         # 构建PDF
#         pdf.build(flowables)
#
#         logger.debug(f"使用Python库成功将DOCX转换为PDF: {pdf_path}")
#         return pdf_path
#     except Exception as e:
#         logger.error(f"使用Python库转换DOCX到PDF失败: {str(e)}")
#         raise APIException(ErrorCode.CONVERT_FAILED, str(e))


def libreoffice_convert_toolkit(office_doc_path: str, output_dir: Optional[str] = None) -> Optional[str]:
    """
    使用 LibreOffice 将文件转换为 PDF 格式

    Args:
        office_doc_path (str): 输入文件的完整路径
        output_dir (str, optional): 输出目录路径。如果不指定，则使用输入文件所在目录

    Returns:
        str: 转换后的 PDF 文件路径，如果转换失败则返回 None

    Raises:
        FileNotFoundError: 当输入文件不存在时
        ValueError: 当输入文件格式不支持时
    """
    try:
        # 检查系统环境
        is_ready, error_msg = check_system_requirements()
        if not is_ready:
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    except Exception as e:
        logger.error(f"检查系统环境时发生错误: {str(e)}")
        raise APIException(ErrorCode.ENVIRONMENT_DEFICIT, str(e))

    office_doc_path = Path(office_doc_path)
    # 如果未指定输出目录，使用输入文件所在目录
    output_dir = output_dir or office_doc_path.parent
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 检查文件名非法字符并替换，避免libreoffice转换失败
    out_path = FileValidator.validate_file_name(doc_path=str(office_doc_path.resolve()),is_replace_name=True)

    # 构建输出文件路径
    save_name = Path(out_path).stem # 获取文件名不带扩展名
    output_file = os.path.join(output_dir, f"{save_name}.pdf")
    logger.debug(f"输出文件路径: {output_file}")

    try:
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            # 复制文件到临时目录，使用英文文件名
            temp_input = os.path.join(temp_dir, f"input{office_doc_path.suffix}")
            shutil.copy2(office_doc_path, temp_input)
            logger.debug(f"创建临时文件: {temp_input}")

            # 构建 LibreOffice 命令
            cmd = [
                Config.PATHS["libreoffice_path"],
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', temp_dir,
                temp_input
            ]
            logger.debug(f"执行命令: {' '.join(cmd)}")

            # 执行转换命令
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=dict(os.environ, LANG='zh_CN.UTF-8')  # 设置环境变量确保中文支持
            )

            # 获取转换输出
            stdout, stderr = process.communicate()
            logger.debug(f"命令输出: {stdout.decode() if stdout else '无'}")
            if stderr:
                logger.error(f"命令错误输出: {stderr.decode()}")

            # 检查转换是否成功
            if process.returncode == 0:
                # 检查临时目录中的 PDF 文件
                temp_pdf = os.path.join(temp_dir, f"input.pdf")
                if os.path.exists(temp_pdf):
                    # 移动 PDF 文件到目标目录
                    shutil.move(temp_pdf, output_file)
                    logger.debug(f"文件 {os.path.basename(office_doc_path)} 转换成功，保存至: {output_file}")
                    return output_file
                else:
                    error_msg=f"转换命令成功但临时 PDF 文件不存在: {temp_pdf}"
                    logger.error(f"[转换失败]  error_code={ErrorCode.CONVERT_FAILED},error_msg={error_msg}")
                    raise APIException(ErrorCode.CONVERT_FAILED, error_msg)
            else:
                logger.error(f"[转换失败] doc_path={str(office_doc_path.resolve())}, error_code={ErrorCode.CONVERT_FAILED}, error_msg={stderr.decode()}")
                raise APIException(ErrorCode.CONVERT_FAILED, stderr.decode())

    except Exception as e:
        logger.error(f"[转换失败] error_code={ErrorCode.CONVERT_FAILED},error_msg={str(e)}")
        raise APIException(ErrorCode.CONVERT_FAILED, str(e))


def convert_office_file(office_doc_path: str):
    """转换 Office 文件, 返回转换后的PDF文件路径

    Args:
        office_doc_path (str): 要转换的office文件路径
    """
    # 获取输出路径
    output_path = get_doc_output_path(office_doc_path)
    output_path, output_image_path, doc_name = (output_path["output_path"],
                                                output_path["output_image_path"],
                                                output_path["doc_name"]
                                                )
    logger.debug(f"开始转换为 PDF 文件: {office_doc_path}, 输出路径: {output_path}")
    
    # 首先尝试使用LibreOffice转换
    try:
        pdf_path = libreoffice_convert_toolkit(office_doc_path, output_path)
        if pdf_path:  # 检查转换是否成功
            logger.debug(f"文件转换成功: {pdf_path}")
            return pdf_path
    except APIException as e:
        logger.error(f"Libreoffice转换失败 : {str(e)}")
        # # 如果是DOCX文件，尝试使用Python库进行转换
        # if Path(office_doc_path).suffix.lower() == '.docx':
        #     logger.info(f"LibreOffice转换失败，尝试使用Python库转换DOCX文件: {office_doc_path}")
        #     try:
        #         pdf_path = docx_to_pdf_python(office_doc_path, output_path)
        #         if pdf_path and os.path.exists(pdf_path):
        #             logger.debug(f"使用Python库转换成功: {pdf_path}")
        #             return pdf_path
        #     except Exception as python_e:
        #         logger.error(f"Python库转换也失败: {str(python_e)}")
        #         # 继续向上抛出原始异常
        #         raise e
        # else:
            # 非DOCX文件，直接抛出异常
            # raise
    
    return None
