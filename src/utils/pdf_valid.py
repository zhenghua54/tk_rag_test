"""
PDF 文件合法性检查, 避免 MinerU 解析崩溃
1. 文件头检查
2. fitz 尝试打开
3. pdfminer.six 测提取文本测试
4. 使用 pdfcpu 检查 pdf 文件结构
"""

import os
import subprocess

import fitz  # PyMuPDF
from pdfminer.high_level import extract_text


def is_pdf_valid(path: str, check_pdfcpu: bool = True) -> tuple[bool, str]:
    """
    判断 PDF 文件是否合法（结构上可被解析），适用于送入 MinerU 前的预筛选。

    参数:
        path (str): PDF 文件路径
        check_pdfcpu (bool): 是否启用系统工具 pdfcpu 验证（可选）

    返回:
        (bool, str): 是否合法, 原因或 OK
    """
    # 0. 检查路径存在且为 PDF 文件
    if not os.path.isfile(path):
        return False, "File not found"

    if not path.lower().endswith(".pdf"):
        return False, "File extension not .pdf"

    # 1. 文件头检查
    try:
        with open(path, "rb") as f:
            header = f.read(5)
        if header != b"%PDF-":
            return False, "Invalid PDF header (not %PDF-)"
    except Exception as e:
        return False, f"Header read error: {e}"

    # 2. 使用 fitz 尝试打开（结构性检查）
    try:
        with fitz.open(path) as doc:
            _ = doc.page_count  # 触发内部结构检查
    except Exception as e:
        return False, f"fitz.open() failed: {e}"

    # 3. 使用 pdfminer 测试可读性（逻辑容错解析）
    try:
        _ = extract_text(path, maxpages=1)
    except Exception as e:
        return False, f"pdfminer extract failed: {e}"

    # 4. 系统 pdfcpu 结构检查（需要已安装 pdfcpu）
    if check_pdfcpu:
        try:
            result = subprocess.run(
                ["pdfcpu", "validate", path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            if b"validation ok" not in result.stdout:
                return False, "pdfcpu validation failed"
        except FileNotFoundError:
            return False, "pdfcpu not installed"

    return True, "OK"


def record_pdf_path(path):
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
