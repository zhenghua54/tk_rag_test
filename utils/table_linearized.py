"""表格转化：HTML） ➝ DataFrame ➝ Linearized（自然语言）
- HTML：mineru 解析后的表格原内容
- DataFrame：转换后的 df 对象，方便操作
- Linearized：线性化后的自然语言格式，更符合 LLM 理解
"""
from rich import print

# 全局补丁:修改 bs4 中 Python3.10 版本后不支持的 collections.Callable 为 collections.abc.Callable
# - 也可以去 bs4 源码中修改替换
import collections.abc

if not hasattr(collections, "Callable") and hasattr(collections.abc, "Callable"):
    collections.Callable = collections.abc.Callable

"""
优化后的 HTML 表格线性化模块：
- 提供更合理的去重策略
- 完善按职责结构输出逻辑
- 提供 DataFrame 线性化方案
- 支持 rowspan 跨行合并解析
- 输出结构化 JSON 数据用于向量或摘要生成
"""
from bs4 import BeautifulSoup
import pandas as pd
from html_table_extractor.extractor import Extractor
from typing import List, Dict, Any, Optional
from itertools import groupby

# 1. HTML ➝ matrix（包含 rowspan/colspan 解析）
def html_to_matrix(html: str) -> List[List[str]]:
    soup = BeautifulSoup(html, "html.parser")
    table_html = soup.find("table")
    if table_html is None:
        raise ValueError("未找到 table 元素")
    extractor = Extractor(str(table_html))
    extractor.parse()
    return extractor.return_list()

# 2. 去除冗余列（相邻列内容重复）
def compress_row_diff(row: List[str]) -> List[str]:
    result = []
    prev = None
    for cell in row:
        clean = cell.strip()
        if clean != prev:
            result.append(clean)
        prev = clean
    return result

# 3. 清洗矩阵内容
def clean_matrix(matrix: List[List[str]]) -> List[List[str]]:
    def clean_cell(cell: str) -> str:
        return " ".join(line.strip() for line in cell.splitlines() if line.strip())
    return [[clean_cell(cell) for cell in row] for row in matrix]

# 4. 按行线性化
def linearize_by_row(matrix: List[List[str]], caption: Optional[str] = None) -> str:
    lines = [caption, "表格逐行内容如下："] if caption else ["表格逐行内容如下："]
    for i, row in enumerate(matrix):
        row = compress_row_diff(row)
        parts = [f"第{i + 1}行第{j + 1}列“{cell}”" for j, cell in enumerate(row) if cell]
        if parts:
            lines.append("，".join(parts) + "。")
    return "\n".join(lines)

# 5. 按段落结构线性化（岗位职责结构识别）
def linearize_by_section(matrix: list[list[str]], caption: str = None) -> str:
    # 提取 header 和内容
    header, rows = matrix[0], matrix[1:]

    # 记录当前条目的结构：{序号 -> 所有行}
    entries = {}
    for row in rows:
        row_clean = [cell.strip() for cell in row]
        if not any(row_clean):
            continue
        num = row_clean[0]
        if num and num.isdigit():
            entries[num] = [row_clean]
        elif num in entries:
            entries[num].append(row_clean)

    lines = [caption, "表格职责概况："] if caption else ["表格职责概况："]
    for num, group in entries.items():
        merged = "；".join(
            cell.strip() for row in group for cell in row[1:] if cell.strip()
        )
        lines.append(f"{num}：{merged}。")
    return "\n".join(lines)

# 6. 提取元信息
def extract_table_metadata(matrix: List[List[str]]) -> Dict[str, Any]:
    """增加结构元信息输出"""
    return {
        "rows": len(matrix),
        "cols": max(len(r) for r in matrix),
        "header": matrix[0] if matrix else [],
    }

# 7. pandas DataFrame ➝ JSON ➝ linear text（稳定结构）
def matrix_to_df(matrix: List[List[str]]) -> pd.DataFrame:
    max_len = max(len(row) for row in matrix)
    return pd.DataFrame([row + [""] * (max_len - len(row)) for row in matrix])

def df_to_json_records(df: pd.DataFrame) -> List[Dict[str, str]]:
    records = []
    columns = df.columns.tolist()
    for _, row in df.iterrows():
        record = {columns[i]: row[i] for i in range(len(columns)) if row[i] and isinstance(row[i], str)}
        records.append(record)
    return records

def json_to_linear_text(json_list: List[Dict[str, str]]) -> str:
    result = []
    for i, row in enumerate(json_list):
        line = f"第{i + 1}行：" + "；".join([f"{k}：{v}" for k, v in row.items()])
        result.append(line)
    return "\n".join(result)

# 8. 主函数封装

def html_to_all_outputs(html: str, caption: Optional[str] = None) -> Dict[str, Any]:
    mat = clean_matrix(html_to_matrix(html))
    df = matrix_to_df(mat)
    json_records = df_to_json_records(df)
    return {
        "meta": extract_table_metadata(mat),
        "by_row": linearize_by_row(mat, caption),
        "by_section": linearize_by_section(mat, caption),
        "json": json_records,
        "json_linear": json_to_linear_text(json_records),
    }


if __name__ == '__main__':
    html_table = """
    \n\n<html><body><table><tr><td colspan=\"6\">、闵位信息</td></tr><tr><td colspan=\"2\">部门名称</td><td colspan=\"2\">综合办</td><td>二级机构</td><td></td></tr><tr><td colspan=\"2\">岗位名称</td><td colspan=\"2\">综合办副主任</td><td>岗位序列</td><td>管理序列</td></tr><tr><td colspan=\"6\">二、岗位职责</td></tr><tr><td>序号</td><td>职能模 块</td><td colspan=\"3\"></td><td>主要职责</td></tr><tr><td>1</td><td>文秘管 理</td><td colspan=\"3\">协助部门负责人起草、修订集团章程； 工作计划、工作总结、工作报告等； 批、印发通知等文件资料，并做好文件归档。</td><td>协助部门负责人起草集团董事会、党委、总经理办公会的相关文件、 协助部门负责人以董事会、党委、总经理办公会的名义，审核、呈</td></tr><tr><td>2</td><td>会务管 理</td><td colspan=\"3\">题工作会的会务管理与服务工作； 档； 协助部门负责人督办办公会议议定事项的落实，组织安排公司其他重</td><td>协助部门负责人办理公司董事会、党委会、总经理办公会及总经理专 协助做好董事会、党委会、总经理办公会会议准备工作(包括议题收集 与审核、会议通知等），撰写会议记录纪要、决议，并上报、下发、存</td></tr><tr><td>3</td><td>综合行 政管理</td><td colspan=\"3\">要会议，并对会议决议事项执行情况进行监督落实， 管理； 发放工作； 协助管理集团行政外包或承包机构； 协助管理对外公共关系工作和重大公关活动的协调；</td><td>协助管理集团工商营业执照的变更登记、年检及证书的保管、使用和 协助管理总部办公用品及其他固定资产的计划、购置、登记、保管、 协助管理责集团总部办公区域相关行政办公资源的调配及维护工作；</td></tr><tr><td>4</td><td>安全环 保管理</td><td colspan=\"3\">协助部门负责人做好内部外协调与联络、接待事项。 全集团安全环保管理体系； 案；</td><td>协助部门负责人贯彻执行国家安全生产法律法规、政策方针，建立健 协助部门负责人建立集团安全环保管理制度，并组织执行； 协助部门负责人编制集团安全环保应急处置预案，并组织演练； 协助部门负责人监督、指导下属企业建立安全环保制度和相应处置方</td></tr></table></body></html>\n\n
    """
    soup = BeautifulSoup(html_table, "html.parser")
    result = html_to_all_outputs(html_table, caption="综合办公室副主任")
    print(result)
    print("-" * 20)
    print(result['by_row'])
    print("-" * 20)
    print(result['by_section'])
    print("-" * 20)
