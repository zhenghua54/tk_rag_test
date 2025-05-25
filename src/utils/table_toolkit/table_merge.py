"""处理被分页截断的表格

数据格式:
{
    "page_idx": 1,
    "content": [
        {
    'type': 'table',
    'img_path': '/home/wumingxing/tk_rag/datas/processed/天宽服务质量体系手册-V1.0 (定稿_打印
版)_20250225/images/1c140aec973ca598f712bd8c341772cd9dad83c72b2bafec65f797c8edd58c3a.jpg',
    'table_caption': [],
    'table_footnote': [],
    'table_body': '\n\n<html><body><table><tr><td rowspan="2">文件名称</td><td colspan="3" 
rowspan="2">服务作业指导书</td><td>文件编号</td><td>QES-002-2025</td></tr><tr><td>版本/次</td><td>A/1</td></tr><tr><td></td><td></td><td></td><td></td><td>实施日期</td><td>2025年
01月24日
</td></tr><tr><td>编制</td><td>质量与安全管理部</td><td>审核</td><td></td><td>批准</td><td>卢晓飞</td></tr></table></body></html>\n\n',
    'page_idx': 30
},
]

处理步骤:
1. 从page_idx = 1开始,遍历所有page_idx, 判断当前页面的第一个元素是否为表格
2. 判断该表格是否有 table_caption 字段
3. 若没有,则判断该表格是否为多列,且通过 BeautifulSoup + lxml 判断首行是否为合并单元格
4. 若为合并单元格,则将该表格第一行的文本作为表格标题,并更新表格数据
5. 若不是合并单元格,则判断上一个页面的最后一个元素是否为表格
6. 若为表格,则将两个表格转为 dataframe 结构,判断标题行是否重复(去除空格统一大小写后,通过余弦相似度判断),重复移除,不重复则合并
7. 如果 DataFrame 结构不匹配或合并失败，建议记录 warning 日志并跳过，而非 raise exception，避免中断整体流程。   
8. 合并后再转换为 html 格式,更新上一个page_idx中的 type 为"merged_table","table_body"为合并后的表格 html 内容,同时追加新字段"metadata",其值为两个表格的 table_body 字段和原始页码及索引,如:
{"metadata":{
    source_table_1: {
        page_idx: 1,
        table_body: 
    },
    source_table_2: {
        page_idx: 2,
        table_body: 
    }
}}
9. 从 json 中移除当前页面的表格
"""

"""处理被分页截断的表格"""
from bs4 import BeautifulSoup
import pandas as pd
from io import StringIO
from src.utils.common.similar_count import SimilarCount
from src.utils.common.logger import logger
from src.utils.json_toolkit.table_formatter import extract_key_fields

class TableMerge:
    def __init__(self):
        self.similar_count = SimilarCount()
        
    def _is_merged_cell(self, table_html: str) -> bool:
        """判断表格首行是否为合并单元格"""
        soup = BeautifulSoup(table_html, 'lxml')
        first_row = soup.find('tr')
        if not first_row:
            return False
            
        # 检查首行是否有合并单元格
        for cell in first_row.find_all(['td', 'th']):
            if cell.get('rowspan') or cell.get('colspan'):
                return True
        return False
        
    def _get_merged_title(self, table_html: str) -> str:
        """从合并单元格中提取标题"""
        soup = BeautifulSoup(table_html, 'lxml')
        first_row = soup.find('tr')
        if not first_row:
            return ""
            
        # 获取首行所有单元格文本
        texts = []
        for cell in first_row.find_all(['td', 'th']):
            text = cell.get_text(strip=True)
            if text:
                texts.append(text)
        return " ".join(texts)
        
    def _merge_tables(self, table1_df: pd.DataFrame, table2_df: pd.DataFrame) -> pd.DataFrame:
        """合并两个表格,处理重复标题行"""
        # 创建副本避免 SettingWithCopyWarning
        table1_df = table1_df.copy()
        table2_df = table2_df.copy()
        
        # 获取标题行并确保所有值都是字符串类型
        header1 = table1_df.iloc[0].astype(str).str.lower().str.strip()
        header2 = table2_df.iloc[0].astype(str).str.lower().str.strip()
        
        # 计算标题行相似度
        similarity = self.similar_count.get_similarity_to_others(
            " ".join(header1), 
            [" ".join(header2)]
        )[0]
        
        # 相似度大于阈值则移除重复标题
        if similarity > 0.95:
            table2_df = table2_df.iloc[1:].copy()
            
        # 合并表格前确保所有列的类型一致
        for col in table1_df.columns:
            if col in table2_df.columns:
                # 使用 .loc 进行赋值
                table1_df.loc[:, col] = table1_df[col].astype(str)
                table2_df.loc[:, col] = table2_df[col].astype(str)
            
        # 合并表格
        return pd.concat([table1_df, table2_df], ignore_index=True)
        
    def process_tables(self, content_list: list) -> list:
        """处理分页表格
        
        Args:
            content_list: 内容列表
            
        Returns:
            处理后的内容列表
        """
        i = 0
        while i < len(content_list):
            # 检查当前页是否有内容
            if not content_list[i].get('content'):
                i += 1
                continue
                
            # 提取第一个元素
            item = content_list[i]['content'][0]
            
            # 检查是否为表格
            if item['type'] != 'table':
                i += 1
                continue
                
            # 检查是否有标题
            if not item.get('table_caption'):
                # 检查是否为合并单元格
                if self._is_merged_cell(item['table_body']):
                    # 提取标题
                    title = self._get_merged_title(item['table_body'])
                    if title:
                        item['table_caption'] = [title]
                else:
                    if i > 0 and content_list[i-1].get('content'):
                        # 获取上一页的最后一个元素
                        last_item = content_list[i-1]['content'][-1]
                        # 检查上一页最后一个元素是否为表格
                        if last_item['type'] == 'table':
                            try:
                                # 转换为DataFrame
                                soup1 = BeautifulSoup(last_item['table_body'], 'lxml')
                                soup2 = BeautifulSoup(item['table_body'], 'lxml')
                                
                                # 使用 StringIO 包装 HTML 字符串
                                df1 = pd.read_html(StringIO(str(soup1)))[0]
                                df2 = pd.read_html(StringIO(str(soup2)))[0]
                                
                                # 合并表格
                                merged_df = self._merge_tables(df1, df2)
                                
                                # 转换为HTML
                                merged_html = merged_df.to_html(index=False)
                                
                                # 更新上一页最后一个元素的内容
                                last_item.update({
                                    'type': 'merged_table',
                                    'table_body': merged_html,
                                    'metadata': {
                                        'source_table_1': {
                                            'page_idx': last_item.get('page_idx'),
                                            'table_body': last_item['table_body']
                                        },
                                        'source_table_2': {
                                            'page_idx': item.get('page_idx'),
                                            'table_body': item['table_body']
                                        }
                                    }
                                })
                                
                                # 移除当前表格
                                content_list[i]['content'].pop(0)
                                continue
                                
                            except Exception as e:
                                logger.warning(f"合并表格失败: {str(e)}")
                            
            i += 1
            
        return content_list


if __name__ == "__main__":
    table_merge = TableMerge()
    json_file_path = "/home/wumingxing/tk_rag/datas/processed/天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225/天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225_content_list.json"
    content_list = parse_json_file(json_file_path)
    new_content_list = table_merge.process_tables(content_list)
    print(new_content_list)