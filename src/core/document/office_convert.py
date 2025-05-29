"""
使用 LibreOffice 进行文件转换的模块
支持将 Office 文档(Word, PPT)转换为 PDF 格式
"""


import os
import subprocess
import shutil
import tempfile
from typing import Optional, Tuple
from pathvalidate import sanitize_filename

from src.utils.common.logger import logger
from config.settings import Config


def check_system_requirements() -> Tuple[bool, str]:
    """
    检查系统环境要求
    
    Returns:
        Tuple[bool, str]: (是否满足要求, 错误信息)
    """
    
    LIBREOFFICE_PATH = "/usr/bin/libreoffice"
    
    # 检查 LibreOffice 是否安装
    if not os.path.exists(LIBREOFFICE_PATH):
        return False, f"LibreOffice 未安装或路径不正确: {LIBREOFFICE_PATH}"
    else:
        logger.info(f"LibreOffice 已安装: {LIBREOFFICE_PATH}")
    
    # 检查中文字体
    try:
        # 检查高质量中文字体，优先使用思源系列字体
        chinese_fonts = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Noto Sans CJK
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",  # Noto Serif CJK
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",   # 备选路径
            "/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc",  # 备选路径
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",          # 文泉驿微米黑
            "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",              # 文泉驿正黑
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
            logger.info(f"已检测到中文字体: {found_font}")
        return True, ""
        
    except Exception as e:
        return False, f"检查系统环境时发生错误: {str(e)}"


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
    # 检查系统环境
    is_ready, error_msg = check_system_requirements()
    if not is_ready:
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    
    # 确保输入文件路径是字符串类型
    input_file = str(input_file)
    
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        logger.error(f"输入文件不存在: {input_file}")
        raise FileNotFoundError(f"输入文件不存在: {input_file}")

    # 获取文件扩展名
    file_ext = os.path.splitext(input_file)[1].lower()
    
    if file_ext not in Config.SUPPORTED_FILE_TYPES['libreoffice']:
        logger.error(f"不支持的文件格式: {file_ext}")
        raise ValueError(f"不支持的文件格式: {file_ext}")

    # 如果未指定输出目录，使用输入文件所在目录
    if output_dir is None:
        output_dir = os.path.dirname(input_file)
    
    # 确保输出目录是字符串类型
    output_dir = str(output_dir)
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"输出目录: {output_dir}")

    # 获取原始文件名并清理
    original_filename = os.path.splitext(os.path.basename(input_file))[0]
    cleaned_filename = sanitize_filename(original_filename)
    
    # 构建输出文件路径
    output_file = os.path.join(output_dir, f"{cleaned_filename}.pdf")
    logger.info(f"输出文件路径: {output_file}")

    try:
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            # 复制文件到临时目录，使用英文文件名
            temp_input = os.path.join(temp_dir, f"input{file_ext}")
            shutil.copy2(input_file, temp_input)
            logger.info(f"创建临时文件: {temp_input}")

            # 构建 LibreOffice 命令
            cmd = [
                LIBREOFFICE_PATH,
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', temp_dir,
                temp_input
            ]
            logger.info(f"执行命令: {' '.join(cmd)}")

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
                logger.warning(f"命令错误输出: {stderr.decode()}")

            # 检查转换是否成功
            if process.returncode == 0:
                # 检查临时目录中的 PDF 文件
                temp_pdf = os.path.join(temp_dir, f"input.pdf")
                if os.path.exists(temp_pdf):
                    # 移动 PDF 文件到目标目录
                    shutil.move(temp_pdf, output_file)
                    logger.info(f"文件 {os.path.basename(input_file)} 转换成功，保存至: {output_file}")
                    return output_file
                else:
                    logger.error(f"转换命令成功但临时 PDF 文件不存在: {temp_pdf}")
                    return None
            else:
                logger.error(f"文件 {os.path.basename(input_file)} 转换失败: {stderr.decode()}")
                return None

    except Exception as e:
        logger.error(f"转换过程中发生错误: {str(e)}")
        return None


if __name__ == "__main__":
    # 测试代码
    test_file = "/home/wumingxing/tk_rag/datas/raw/1_1_竞争情况（天宽科技）.docx"
    try:
        pdf_path = convert_to_pdf(test_file)
        if pdf_path:
            print(f"转换成功，PDF 文件保存在: {pdf_path}")
        else:
            print("转换失败")
    except Exception as e:
        print(f"发生错误: {str(e)}")
