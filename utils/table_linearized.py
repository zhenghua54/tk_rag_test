"""表格转化：HTML） ➝ DataFrame ➝ Linearized（自然语言）
- HTML：mineru 解析后的表格原内容
- DataFrame：转换后的 df 对象，方便操作
- Linearized：线性化后的自然语言格式，更符合 LLM 理解
"""
from bs4 import BeautifulSoup
import pandas as pd

from rich import print


def html_to_linearized_text(html: str, table_caption: str = None) -> str:
    """将 HTML 表格转换为线性化自然语言文本（适用于向量生成、摘要、模型上下文）。

    Args:
        html (str): HTML 表格字符串
        table_caption (str, optional): 表格标题或说明性描述

    Returns:
        str: 线性化自然语言描述, 可作为 RAG 上下文, 生成 Embedding或摘要输入
    """

    # 初始化 soup
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    print(table)

    # 提取所有表格行
    rows = table.find_all("tr")
    table_data = []
    max_cols = 0
    print(rows)

    for row in rows:
        cells = row.find_all(["td", "th"])
        row_data = [cell.get_text(strip=True) for cell in cells]
        # row_data_1 = [cell.get_text(separator="\n",strip=True) for cell in cells]
        print(row_data)
        max_cols = max(max_cols, len(row_data))
        table_data.append(row_data)

    # 补全短行
    table_data = [row + [""] * (max_cols - len(row)) for row in table_data]
    df = pd.DataFrame(table_data, columns=table_caption)
    df.columns = [f"列{i + 1}" for i in range(max_cols)]

    # 转换为线性化自然语言
    lines = []
    if table_caption:
        lines.append(f"{table_caption}\n")
    lines.append("表格内容如下:")
    for i, row in df.iterrows():
        cells = [f"{col}为“{row[col]}”" for col in df.columns if str(row[col]).strip()]
        if cells:
            lines.append(f"第{i + 1}行：" + "，".join(cells) + "。")

    return "\n".join(lines)

if __name__ == '__main__':
    html_table = """
    \n\n<html><body><table><tr><td colspan=\"6\">、闵位信息</td></tr><tr><td colspan=\"2\">部门名称</td><td colspan=\"2\">综合办</td><td>二级机构</td><td></td></tr><tr><td colspan=\"2\">岗位名称</td><td colspan=\"2\">综合办副主任</td><td>岗位序列</td><td>管理序列</td></tr><tr><td colspan=\"6\">二、岗位职责</td></tr><tr><td>序号</td><td>职能模 块</td><td colspan=\"3\"></td><td>主要职责</td></tr><tr><td>1</td><td>文秘管 理</td><td colspan=\"3\">协助部门负责人起草、修订集团章程； 工作计划、工作总结、工作报告等； 批、印发通知等文件资料，并做好文件归档。</td><td>协助部门负责人起草集团董事会、党委、总经理办公会的相关文件、 协助部门负责人以董事会、党委、总经理办公会的名义，审核、呈</td></tr><tr><td>2</td><td>会务管 理</td><td colspan=\"3\">题工作会的会务管理与服务工作； 档； 协助部门负责人督办办公会议议定事项的落实，组织安排公司其他重</td><td>协助部门负责人办理公司董事会、党委会、总经理办公会及总经理专 协助做好董事会、党委会、总经理办公会会议准备工作(包括议题收集 与审核、会议通知等），撰写会议记录纪要、决议，并上报、下发、存</td></tr><tr><td>3</td><td>综合行 政管理</td><td colspan=\"3\">要会议，并对会议决议事项执行情况进行监督落实， 管理； 发放工作； 协助管理集团行政外包或承包机构； 协助管理对外公共关系工作和重大公关活动的协调；</td><td>协助管理集团工商营业执照的变更登记、年检及证书的保管、使用和 协助管理总部办公用品及其他固定资产的计划、购置、登记、保管、 协助管理责集团总部办公区域相关行政办公资源的调配及维护工作；</td></tr><tr><td>4</td><td>安全环 保管理</td><td colspan=\"3\">协助部门负责人做好内部外协调与联络、接待事项。 全集团安全环保管理体系； 案；</td><td>协助部门负责人贯彻执行国家安全生产法律法规、政策方针，建立健 协助部门负责人建立集团安全环保管理制度，并组织执行； 协助部门负责人编制集团安全环保应急处置预案，并组织演练； 协助部门负责人监督、指导下属企业建立安全环保制度和相应处置方</td></tr></table></body></html>\n\n
    """
    print(html_to_linearized_text(html_table, table_caption="综合办公室副主任"))
