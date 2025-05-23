"""
表格格式化工具
"""

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


def extract_key_fields(segment):
    """从 HTML 表格中提取关键字段
    
    Args:
        segment: 文档片段
    
    Returns:
        str: 关键字段文本
    """
    # 使用 BeautifulSoup 解析 HTML
    soup = BeautifulSoup(segment, 'lxml')
    
    # 提取所有 td 文本
    tds = soup.find_all('td')
    texts = [td.get_text().strip() for td in tds]
    
    # 过滤空文本
    texts = [t for t in texts if t]
    
    return ' '.join(texts)

if __name__ == '__main__':
    # 测试提取表格内容后相似度计算
    table_body = [
            """'\n\n<html><body><table><tr><td rowspan="2">文件名称</td><td colspan="3" 
    rowspan="2">服务作业指导书</td><td>文件编号</td><td>QES-002-2025</td></tr><tr><td>版本/次</td><td>A/1</td></tr><tr><td></td><td></td><td></td><td></td><td>实施日期</td><td>2025年01月24日
    </td></tr><tr><td>编制</td><td>质量与安全管理部</td><td>审核</td><td></td><td>批准</td><td>卢晓飞</td></tr></table></body></html>\n\n'""",
            """'\n\n<html><body><table><tr><td rowspan="2">文件名称</td><td colspan="3" 
    rowspan="2">服务作业指导书</td><td>文件编号</td><td>QES-002-2025</td></tr><tr><td>版本/次</td><td>A/1</td></tr><tr><td></td><td></td><td></td><td></td><td>实施日期</td><td>2025年01月24日
    </td></tr><tr><td>编制</td><td>质量与安全管理部</td><td>审核</td><td></td><td>批准</td><td>卢晓飞</td></tr></table></body></html>\n\n'""",
            """'\n\n<html><body><table><tr><td rowspan="2" colspan="3">文件名称</td><td 
    rowspan="2"></td><td>文件编号</td><td>QES-002-2025</td></tr><tr><td>版本/次</td><td>A/1</td></tr><tr><td>编制</td><td>质量与安全管理部</td><td>审核</td><td></td><td>实施日期 
    批准</td><td>2025年01月24日 卢晓飞</td></tr></table></body></html>\n\n'""",
        ]

    
    from config import Config
    # 加载本地模型
    model = SentenceTransformer(Config.MODEL_PATHS['embedding'])

    score_list = []
    for item in table_body:
        table_content = extract_key_fields(item)

        # 获取文本的向量表示
        embeddings = model.encode([table_content])

        # 追加
        score_list.append({
            "table_content": table_content,
            "embedding": embeddings
        })

    # 计算余弦相似度
    similarity = cosine_similarity(score_list[0]["embedding"], score_list[1]["embedding"])

    print(f"格式化文本相似度分数: {similarity}")

