"""各类转换器（html2md、时间转换、大小转换等）"""

import os
from urllib.parse import quote

import pandas as pd
from bs4 import BeautifulSoup

from config.global_config import GlobalConfig
from utils.log_utils import logger
from utils.validators import validate_html


# === 单位转换工具 ===
def convert_bytes(size: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB"]
    index = 0
    convert_size = 1024
    while size >= convert_size and index < len(units) - 1:
        size /= convert_size
        index += 1
    return f"{size:.2f} {units[index]}"


# === 内容转换 ===
def convert_html_to_markdown(html: str) -> str:
    """将 HTML 表格转换为 Markdown 格式

    Args:
        html: HTML 表格字符串

    Returns:
        str: Markdown 格式的表格
    """
    if not validate_html(html):
        return html
    else:
        # logger.info("开始转换表格（html -> markdown）...")
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        if not table:
            return ""

        # 解析为二维列表（按渲染位置展开 col_span/rowspan）
        grid = []
        max_cols = 0
        row_spans = {}  # 记录每个列的 rowspan 状态

        for _, row in enumerate(table.find_all("tr")):
            row_data = []
            col_idx = 0

            # 处理当前行的 rowspan
            for col_idx in range(max_cols):
                if col_idx in row_spans and row_spans[col_idx] > 0:
                    row_data.append(row_spans[col_idx])
                    row_spans[col_idx] -= 1
                else:
                    row_data.append("")

            # 处理当前行的单元格
            cells = row.find_all(["td", "th"])
            for cell in cells:
                # 跳过已经被 rowspan 占用的列
                while col_idx < len(row_data) and row_data[col_idx] != "":
                    col_idx += 1

                colspan = int(cell.get("colspan", "1"))
                rowspan = int(cell.get("rowspan", "1"))
                text = cell.get_text(strip=True)

                # 处理 colspan
                for i in range(colspan):
                    if col_idx + i >= len(row_data):
                        row_data.append(text)
                    else:
                        row_data[col_idx + i] = text

                # 处理 rowspan
                if rowspan > 1:
                    for i in range(colspan):
                        row_spans[col_idx + i] = rowspan - 1

                col_idx += colspan

            max_cols = max(max_cols, len(row_data))
            grid.append(row_data)

        # 规范化所有行的长度
        for i in range(len(grid)):
            if len(grid[i]) < max_cols:
                grid[i].extend([""] * (max_cols - len(grid[i])))

        # 构造 DataFrame
        df = pd.DataFrame(grid)

        # 如果首行可能是 header，则设为表头
        if len(df) > 1:
            df.columns = df.iloc[0]
            df = df[1:]
            df.reset_index(drop=True, inplace=True)

        logger.debug(f"[表格转换] 完成, 表格大小={len(df)}行x{len(df.columns)}列")

        # 转为 markdown
        return df.to_markdown(index=False)


# === 路径转换 ===
def local_path_to_url(local_path: str) -> str:
    """将本路路径转换为 http url 地址"""
    # 转换源文档地址
    if GlobalConfig.PATHS["origin_data"] in local_path:
        rel_path = os.path.relpath(local_path, GlobalConfig.PATHS["origin_data"])
        # return f"http://192.168.5.199:8000/static/raw/{quote(rel_path)}"
        return f"/static/raw/{quote(rel_path)}"
    # 转换输出文档地址
    elif GlobalConfig.PATHS["processed_data"] in local_path:
        rel_path = os.path.relpath(local_path, GlobalConfig.PATHS["processed_data"])
        # return f"http://192.168.5.199:8000/static/processed/{quote(rel_path)}"
        return f"/static/processed/{quote(rel_path)}"
    else:
        raise ValueError("不支持的路径, 未注册的路径地址")


def normalize_permission_ids(permission_ids) -> list[str]:
    """
    规范化权限 ID 输入，支持 None、空字符串、空列表、字符串列表等情况。

    Args:
        permission_ids: 接口接收到的权限 ID 字段

    Returns:
        - None / 空字符串 → [""]（无权限）
        - 字符串 → ["deptA"]
        - 列表 → None 转换为 ""，保留 ""，去除多余空白，返回原始顺序
    """

    # None -> 空字符串
    if permission_ids is None:
        return [""]

    # 空字符串或空白字符
    if isinstance(permission_ids, str):
        cleaned = permission_ids.strip()
        return [cleaned, ""] if cleaned else [""]

    # 空列表或 [''] 视为公开权限
    if isinstance(permission_ids, list):
        cleaned_list = list()
        for pid in permission_ids:
            if pid is None:
                pid = ""
            if not isinstance(pid, str):
                raise ValueError(f"权限 ID 应为字符串, 但收到: {pid}({type(pid)})")
            cleaned_list.append(pid.strip())

        # 添加空权限(支持公开文档查询)
        cleaned_list.append("")

        # 去重
        cleaned_list = list(set(cleaned_list))

        return cleaned_list if cleaned_list else [""]

    raise ValueError(f"不支持的权限 ID 类型: {type(permission_ids)}")


# # 用法示例：
# normalized_permission_ids = normalize_permission_ids(permission_ids)


if __name__ == "__main__":
    # 测试权限转换
    print(normalize_permission_ids(None))  # [""]

    print(normalize_permission_ids("deptA"))  # ["deptA"]
    print(normalize_permission_ids("   "))  # [""]

    print(normalize_permission_ids(["deptA", "  ", "deptB"]))  # ["deptA", "", "deptB"]
    print(normalize_permission_ids(["  "]))  # [""]
    print(normalize_permission_ids([]))  # [""]
    print(normalize_permission_ids(["deptA", None, "deptB"]))  # ["deptA", "deptB"]

    print(normalize_permission_ids(["deptA", None, "deptB", "deptB", "", "       ", "deptA"]))  # ["deptA", "deptB"]
