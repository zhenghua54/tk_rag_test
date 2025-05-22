import pandas as pd
from bs4 import BeautifulSoup
from rich import print


def html_table_to_dataframe(table_body_html: str) -> dict:
    """解析 html 格式的表格内容,方便摘要提取和规则处理

    Args:
        table_body_html (str): html 格式的 table 内容

    Returns:
        table_body_dict:
            table_df: DataFrame 对象
            table_md: Markdown 格式
            table_format_str: 结构化提取格式
    """

    # 使用 beautifulsoup 解析
    soup = BeautifulSoup(table_body_html, 'lxml')
    table = soup.find('table')

    # 解析表格为二维数组
    data = []
    for row in table.find_all('tr'):
        row_data = []
        for cell in row.find_all(['td', 'th']):
            # 获取单元格横向合并数量
            colspan = int(cell.get('colspan', 1))
            # 清除前后空白
            text = cell.get_text(strip=True)
            # 若 colspan >1, 则横向展开多列
            row_data.extend([text] * colspan)
        data.append(row_data)

    # 转换为dataframne
    table_df = pd.DataFrame(data)
    # 转换为markdown格式,方便 LLM 使用
    table_markdown = table_df.to_markdown(index=False)
    # 提取结构化文本,方便概要提取
    table_format_str = "\n".join([f"{row[0]}：{row[1]}" for _, row in table_df.iterrows() if len(row) > 1])

    # 合并字典
    table_body_dict = {
        "table_df": table_df,
        "table_md": table_markdown,
        "table_format_str": table_format_str,
    }

    return table_body_dict


if __name__ == '__main__':
    # 原始内容
    table_body = """
    '\n\n<html><body><table><tr><td></td><td></td><td></td><td></td><td></td><td></t
    d><td></td><td></td><td colspan="2"></td><td 
    colspan="2"></td><td></td></tr><tr><td>标记</td><td>处数</td><td>更改文件号</td>
    <td></td><td>签字</td><td>日期</td><td>标记</td><td>处数</td><td 
    colspan="2">更改文件号</td><td>签字</td><td>日期</td></tr><tr><td>编制/目</td><t
    d colspan="2">2023/5/12</td><td colspan="2">审核/日 见SGINB-H031 
    轴检</td><td>会签日</td><td colspan="2">见SGINB-H031销轴检验</td><td 
    colspan="2">批准/日</td><td>江峰2023/5/15</td><td></td></tr></table></body></htm
    l>\n\n'"""

    table_body_dict = html_table_to_dataframe(table_body)
    # print(table_body_dict['table_df'])
    # print(table_body_dict['table_md'])
    print(table_body_dict['table_format_str'])
