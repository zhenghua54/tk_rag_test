"""使用 PyMuPDF 检查 pdf 文件结构, 避免 MinerU 解析崩溃"""

import json
import os
import re
import shutil
from pathlib import Path

import fitz
import requests

from config.global_config import GlobalConfig


def validate_file_normal(doc_path: str):
    """校验文档是否可正常打开"""
    abs_file_path = os.path.abspath(doc_path)
    file_ext = os.path.splitext(doc_path)[1].lower()

    try:
        # 1. 使用二进制模式验证文件可读性
        with open(abs_file_path, "rb") as f:
            f.read(1024)  # 只读取前1KB验证文件可读性

        # 2. 如果是PDF文件，额外进行结构验证
        if file_ext == ".pdf":
            with fitz.open(abs_file_path) as doc:
                if doc.is_encrypted:
                    raise ValueError("PDF文件已加密, 无法读取")
                if doc.page_count == 0:
                    raise ValueError("空文档")

    except Exception as e:
        raise ValueError(f"文件无法正常打开: {str(e)}") from e


# === 基础参数类型校验 ===
def validate_empty_param(value, param_name: str):
    """验证参数非空"""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        raise ValueError(f"{param_name} 不能为空")


def validate_param_type(value, expected_type: type, name: str):
    """验证参数类型"""
    if not isinstance(value, expected_type):
        raise TypeError(f"参数 `{name}` 应为 {expected_type.__name__} 类型")


def validate_empty_list(lst, name: str):
    """验证列表非空"""
    if not lst:
        raise TypeError(f"参数 `{name}` 不能为空列表")


# === ID 校验 ===
def validate_doc_id(value):
    """验证文档ID格式"""
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"非法的 doc_id: {value}")


def validate_seg_id(value):
    """验证分块ID格式"""
    if not isinstance(value, str) or not re.match(r"^[a-zA-Z0-9_-]+$", value) or not re.match(r"^[a-f0-9]{64}$", value):
        raise ValueError(f"非法的 seg_id: {value}")


def validate_permission_id(value):
    """验证部门ID格式"""
    if not isinstance(value, str) or not 1 <= len(value) <= 32:
        raise ValueError(f"非法的 permission_id: {value}")


def validate_permission_ids(value):
    """验证部门ID列表"""
    if value is None:
        return
    if isinstance(value, str):
        if not value.strip():
            return
        if 1 <= len(value) <= 32:
            return
    elif isinstance(value, list):
        if len(value) == 0:
            return
        for idx, v in enumerate(value):
            if not isinstance(v, str):
                raise ValueError(f"第 {idx} 个权限 ID 类型错误: {v}:{type(v)}")
            if not v.strip():
                continue  # 空字符串跳过

    elif isinstance(value, list) and len(value) == 0:
        pass
    else:
        raise ValueError(f"非法的 permission_id: {value}")


# === 表格内容校验 ===
def validate_html(value: str) -> bool:
    """
    校验字符串是否为 HTML 表格格式

    Args:
        value (str): 待校验的 HTML 字符串

    Returns:
        bool: 是否为有效的 HTML 表格
    """
    if not isinstance(value, str) or not value.strip():
        return False

    # 简单正则校验是否包含完整 <table> 标签结构
    pattern = re.compile(r"<table.*?>.*?</table>", re.IGNORECASE | re.DOTALL)
    match = pattern.search(value)
    return bool(match)


# === 文档路径相关 ===
def check_local_doc_exists(doc_path: str):
    """验证本地文档是否存在"""
    if not os.path.isfile(doc_path):
        raise ValueError(f"本地文件不存在: {doc_path}")


def check_http_doc_accessible(url: str):
    """验证 http 文档路径是否存在"""
    try:
        res = requests.head(url, timeout=3)
        if res.status_code != 200:
            raise ValueError(f"远程文档无法访问: {url}")
    except Exception as e:
        raise ValueError(f"远程文档访问异常: {url}") from e


def check_doc_path_length(doc_path: str):
    """检查文档路径长度是否超出 mysql 数据库字段要求"""
    if len(doc_path) > GlobalConfig.MYSQL_FIELD.get("max_path_len"):
        raise ValueError(f"路径长度超限: {len(doc_path)} > {GlobalConfig.MYSQL_FIELD.get('max_path_len')}")


# === 文档名校验 ===
def check_doc_name_chars(doc_name: str):
    """文件名称格式校验：统一平台无关型文件名清洗器"""
    if len(doc_name) > GlobalConfig.MYSQL_FIELD.get("max_name_len", 500):
        raise ValueError(f"文档名过长: {len(doc_name)} > {GlobalConfig.MYSQL_FIELD.get('max_name_len')}")
    if any(c in GlobalConfig.UNSUPPORTED_FILENAME_CHARS for c in doc_name):
        raise ValueError(f"文档名 {doc_name} 包含非法字符: {''.join(GlobalConfig.UNSUPPORTED_FILENAME_CHARS)}")


# === 文档扩展名 ===
def check_doc_ext(ext: str, doc_type: str):
    """文档格式校验"""
    allowed_ext = GlobalConfig.SUPPORTED_FILE_TYPES.get(doc_type, [])
    if ext not in allowed_ext:
        raise ValueError(
            f"不支持的文档扩展名: {ext}, 仅支持: {', '.join(GlobalConfig.SUPPORTED_FILE_TYPES.get(doc_type, []))}"
        )


# === 文档大小 ===
def check_doc_size(doc_path: str):
    """验证文件大小"""
    size_mb = os.path.getsize(doc_path) / (1024 * 1024)  # 50 * 1024 * 1024 = 52428800 字节
    if size_mb > GlobalConfig.FILE_MAX_SIZE:
        raise ValueError(f"文档大小超限: {size_mb:.2f}MB > {GlobalConfig.FILE_MAX_SIZE}MB")


# === JSON 格式校验 ===
def check_json_list_format(json_str: str):
    """验证 JSON 文件内容格式：应为非空的 [{}] 列表"""
    try:
        lst = json.loads(json_str)
        if not isinstance(lst, list):
            raise ValueError("JSON 不是列表格式")
        if not isinstance(lst[0], dict):
            raise ValueError("JSON 元素错误，应为字典格式")
    except Exception as e:
        raise ValueError("非法 JSON 格式") from e


# === 磁盘空间校验 ===
def check_disk_space_sufficient(doc_path: str):
    """检查存储空间是否足够"""
    file_size = os.path.getsize(doc_path)
    # 获取项目根目录所在磁盘的可用空间
    total, used, free = shutil.disk_usage(str(Path(__file__)))
    if free <= file_size * 4:  # 预留4倍空间作为缓冲, 需要确保后续文档的生成空间
        raise ValueError("磁盘剩余空间不足")


if __name__ == "__main__":
    pass
