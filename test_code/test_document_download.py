#!/usr/bin/env python3
"""测试远程文件下载和处理流程"""

import os
import sys
import requests
import logging
import time
from pathlib import Path

# 配置日志输出
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_download_file(url, save_path=None):
    """测试下载远程文件
    
    Args:
        url: 远程文件URL
        save_path: 保存路径，默认为当前目录
    
    Returns:
        本地文件路径
    """
    logger.info(f"开始测试下载文件: {url}")
    
    # 从URL获取文件名
    file_name = url.split('/')[-1]
    
    # 设置保存路径
    if save_path is None:
        save_path = os.path.join(os.getcwd(), file_name)
    else:
        save_path = os.path.join(save_path, file_name)
    
    # 确保目录存在
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    try:
        # 设置超时
        timeout = 30
        logger.info(f"下载超时设置: {timeout}秒")
        
        # 首先测试HEAD请求
        logger.info("测试HEAD请求...")
        head_response = requests.head(url, timeout=timeout)
        head_response.raise_for_status()
        
        # 打印头信息
        logger.info(f"HEAD请求成功，状态码: {head_response.status_code}")
        logger.info(f"内容类型: {head_response.headers.get('Content-Type')}")
        logger.info(f"内容长度: {head_response.headers.get('Content-Length', '未知')} 字节")
        
        # 开始下载
        logger.info(f"开始下载文件到: {save_path}")
        start_time = time.time()
        
        # 流式下载
        with requests.get(url, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            total_size = int(response.headers.get('Content-Length', 0))
            downloaded = 0
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            logger.info(f"下载进度: {percent:.2f}% ({downloaded}/{total_size} 字节)")
        
        # 检查文件是否存在和大小是否正确
        if os.path.exists(save_path):
            file_size = os.path.getsize(save_path)
            logger.info(f"文件已下载，大小: {file_size} 字节")
            if total_size > 0 and file_size != total_size:
                logger.warning(f"文件大小不匹配: 预期 {total_size}，实际 {file_size}")
        else:
            logger.error(f"文件下载失败: {save_path} 不存在")
            return None
        
        elapsed = time.time() - start_time
        logger.info(f"下载完成，耗时: {elapsed:.2f} 秒")
        
        return save_path
    except requests.exceptions.Timeout:
        logger.error(f"下载超时: {url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"下载请求异常: {e}")
        return None
    except Exception as e:
        logger.error(f"下载过程中发生异常: {e}")
        return None

def test_file_access(file_path):
    """测试文件访问
    
    Args:
        file_path: 文件路径
    
    Returns:
        是否可以访问
    """
    logger.info(f"测试文件访问: {file_path}")
    
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return False
        
        # 检查文件大小
        file_size = os.path.getsize(file_path)
        logger.info(f"文件大小: {file_size} 字节")
        
        # 尝试读取文件
        with open(file_path, 'rb') as f:
            # 只读取开头和结尾来验证文件可读
            start_bytes = f.read(1024)
            f.seek(max(0, file_size - 1024))
            end_bytes = f.read(1024)
        
        logger.info(f"文件读取成功，开头字节数: {len(start_bytes)}，结尾字节数: {len(end_bytes)}")
        return True
    except Exception as e:
        logger.error(f"测试文件访问时出错: {e}")
        return False

def test_document_processing(file_path):
    """测试文档处理流程，包括转换和解析
    
    Args:
        file_path: 本地文件路径
    """
    logger.info(f"测试文档处理流程: {file_path}")
    
    try:
        # 检查文件后缀
        file_ext = os.path.splitext(file_path)[1].lower()
        logger.info(f"文件类型: {file_ext}")
        
        # 1. 检查文件是否为.docx格式
        if file_ext == '.docx':
            logger.info("检测到Word文档，需要进行转换")
            
            # 检查LibreOffice是否可用
            libreoffice_path = "/usr/bin/libreoffice"
            if not os.path.exists(libreoffice_path):
                logger.error(f"LibreOffice不存在: {libreoffice_path}")
                return
            
            logger.info(f"LibreOffice已检测到: {libreoffice_path}")
            
            # 创建临时目录
            output_dir = os.path.join(os.path.dirname(file_path), "output")
            os.makedirs(output_dir, exist_ok=True)
            
            # 构建转换命令
            cmd = [
                libreoffice_path,
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', output_dir,
                file_path
            ]
            
            logger.info(f"执行转换命令: {' '.join(cmd)}")
            import subprocess
            
            # 执行转换
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                logger.info("转换成功")
                if stdout:
                    logger.info(f"命令输出: {stdout.decode()}")
                
                # 检查生成的PDF文件
                pdf_path = os.path.join(output_dir, os.path.splitext(os.path.basename(file_path))[0] + '.pdf')
                if os.path.exists(pdf_path):
                    logger.info(f"生成的PDF文件: {pdf_path}")
                    file_path = pdf_path  # 更新文件路径为PDF
                else:
                    logger.error(f"生成的PDF文件不存在: {pdf_path}")
                    return
            else:
                logger.error(f"转换失败，错误码: {process.returncode}")
                if stderr:
                    logger.error(f"错误输出: {stderr.decode()}")
                return
        elif file_ext != '.pdf':
            logger.warning(f"不支持的文件类型: {file_ext}，需要为.pdf或.docx")
            return
        
        # 2. 文档解析测试
        logger.info("测试文档内容提取...")
        
        try:
            # 简单检查PDF是否可以打开
            import fitz  # PyMuPDF
            with fitz.open(file_path) as doc:
                page_count = doc.page_count
                logger.info(f"文档页数: {page_count}")
                
                # 提取第一页文本
                if page_count > 0:
                    text = doc[0].get_text()
                    text_preview = text[:200] + "..." if len(text) > 200 else text
                    logger.info(f"第一页文本预览: {text_preview}")
        except ImportError:
            logger.error("缺少PyMuPDF库，无法进行PDF解析测试")
        except Exception as e:
            logger.error(f"PDF解析测试失败: {e}")
        
        logger.info("文档处理测试完成")
        
    except Exception as e:
        logger.error(f"文档处理测试失败: {e}")

def main():
    """主函数"""
    # 远程文件URL
    remote_url = "http://192.168.6.99:18101/cbm/api/v3/upload/2025-06-09/51e559d9cfec4ab0ac367cfd6354cd48.docx"
    
    # 测试远程文件下载
    local_file_path = test_download_file(remote_url)
    
    if not local_file_path:
        logger.error("文件下载失败，测试终止")
        return 1
    
    # 测试文件访问
    if not test_file_access(local_file_path):
        logger.error("文件访问测试失败，测试终止")
        return 1
    
    # 测试文档处理流程
    test_document_processing(local_file_path)
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 