"""
使用 LibreOffice 进行文件转换的模块
支持将 Office 文档转换为 PDF 格式
"""

import sys

sys.path.append("/Users/jason/PycharmProjects/tk_rag")
import os
import platform
import subprocess
from typing import Optional
from src.utils.get_logger import logger

# 获取系统类型
SYSTEM = platform.system()

# 根据系统类型设置 LibreOffice 可执行文件路径
if SYSTEM == "Darwin":  # macOS
    LIBREOFFICE_PATH = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
else:  # Linux 和 Windows
    LIBREOFFICE_PATH = "soffice"

def convert_to_pdf(input_file: str, output_dir: Optional[str] = None) -> Optional[str]:
    """
    使用 LibreOffice 将文件转换为 PDF 格式

    Args:
        input_file (str): 输入文件的完整路径
        output_dir (str, optional): 输出目录路径。如果不指定，则使用输入文件所在目录

    Returns:
        str: 转换后的 PDF 文件路径，如果转换失败则返回 None

    Raises:
        FileNotFoundError: 当输入文件不存在时
        ValueError: 当输入文件格式不支持时
    """
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"输入文件不存在: {input_file}")

    # 检查 LibreOffice 是否安装
    if not os.path.exists(LIBREOFFICE_PATH):
        raise FileNotFoundError(f"LibreOffice 未安装或路径不正确: {LIBREOFFICE_PATH}")

    # 获取文件扩展名
    file_ext = os.path.splitext(input_file)[1].lower()
    supported_extensions = ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']
    
    if file_ext not in supported_extensions:
        raise ValueError(f"不支持的文件格式: {file_ext}")

    # 如果未指定输出目录，使用输入文件所在目录
    if output_dir is None:
        output_dir = os.path.dirname(input_file)
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 构建输出文件路径
    output_file = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(input_file))[0]}.pdf")

    try:
        # 构建 LibreOffice 命令
        # --headless: 无界面模式
        # --convert-to pdf: 转换为 PDF
        # --outdir: 输出目录
        cmd = [
            LIBREOFFICE_PATH,
            '--headless',
            '--convert-to', 'pdf',
            '--outdir', output_dir,
            input_file
        ]

        # 执行转换命令
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        # 获取转换输出
        stdout, stderr = process.communicate()

        # 检查转换是否成功
        # 检查转换命令的返回码
        if process.returncode == 0:
            # 转换成功，记录日志并返回输出文件路径
            logger.info(f"文件 {os.path.basename(input_file)} 转换成功，保存至: {output_file}")
            if stdout:
                # 记录详细的转换输出信息
                logger.debug(f"转换输出: {stdout.decode()}")
            return output_file
        else:
            # 转换失败，记录错误信息
            logger.error(f"文件 {os.path.basename(input_file)} 转换失败: {stderr.decode()}")
            if stdout:
                # 记录转换过程中的输出信息
                logger.error(f"转换输出: {stdout.decode()}")
            return None

    except Exception as e:
        logger.error(f"转换过程中发生错误: {str(e)}")
        return None


if __name__ == "__main__":
    # 测试代码
    test_file = "/Users/jason/Documents/技术方案大纲（参考）.docx"
    try:
        pdf_path = convert_to_pdf(test_file)
        if pdf_path:
            print(f"转换成功，PDF 文件保存在: {pdf_path}")
        else:
            print("转换失败")
    except Exception as e:
        print(f"发生错误: {str(e)}")
