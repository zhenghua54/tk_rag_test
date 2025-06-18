"""各类转换器（html2md、时间转换、大小转换等）"""
import pandas as pd
from bs4 import BeautifulSoup

from utils.log_utils import logger
from utils.validators import validate_html


# === 单位转换工具 ===
def convert_bytes(size: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB"]
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
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


if __name__ == '__main__':
    # print("=== 测试表格转Markdown ===")
    # markdown_table = convert_html_to_markdown(table_html)
    # print(f"Markdown表格：\n{markdown_table}")
    pass
