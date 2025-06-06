"""表格内容处理"""
import os
import sys

import pandas as pd
from bs4 import BeautifulSoup

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)
from src.utils.common.args_validator import ArgsValidator
from src.utils.common.logger import logger


def html_table_to_markdown(table_html: str) -> str:
    """将 HTML 表格转换为 Markdown 格式

    Args:
        table_html (str): HTML 表格字符串

    Returns:
        str: Markdown 格式的表格
    """
    # 参数验证
    ArgsValidator.validity_not_empty(table_html, "table_html")
    ArgsValidator.validity_type(table_html, str, "table_html")

    logger.info("开始转换表格（html -> markdown）...")
    soup = BeautifulSoup(table_html, "lxml")
    table = soup.find("table")
    if not table:
        return ""

    # 解析为二维列表（按渲染位置展开 col_span/rowspan）
    grid = []
    max_cols = 0
    row_spans = {}  # 记录每个列的 rowspan 状态

    for row_idx, row in enumerate(table.find_all("tr")):
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

    logger.info("markdown 格式表格转换完成！")

    # 转为 markdown
    return df.to_markdown(index=False)


if __name__ == "__main__":
    pass
