"""处理被分页截断的表格,备份暂时不用"""

from bs4 import BeautifulSoup
import pandas as pd
from io import StringIO
from src.utils.common.similar_count import SimilarCount
from src.utils.common.logger import logger
from src.utils.table_toolkit.table_formatter import extract_key_fields

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
        
        
        # 列数一致且标题内容相似,判断为重复标题
        if len(header1) == len(header2):
            similarity = self.similar_count.get_similarity_to_others(" ".join(header1), [" ".join(header2)])[0]
            if similarity > 0.999:
                # 保留第一个表格的标题行，删除第二个表格的标题行
                table2_df = table2_df.iloc[1:].copy()
        
        # 确保两表结构一致后再合并
        common_cols = table1_df.columns.intersection(table2_df.columns)
        for col in common_cols:
            table1_df.loc[:, col] = table1_df[col].astype(str)
            table2_df.loc[:, col] = table2_df[col].astype(str)
            
        # 合并表格，保持原始列名
        return pd.concat([table1_df, table2_df], ignore_index=False)
    
    
    # def merge_cross_page_tables(self, content_list: list) -> list:
        """处理分页表格
        
        Args:
            content_list: json格式的文档内容列表
            
        Returns:
            list: 处理完跨页表格后的内容列表
        """
        i = 0
        logger.info(f"开始处理跨页表格...")
        
        # 记录跨页表格信息
        cross_page_tables = []  # 存储跨页表格的页码信息
        success_merges = []     # 记录成功合并的页码
        failed_merges = []      # 记录合并失败的页码
        
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
            
            # 去除表格前后空格
            item['table_body'] = item['table_body'].strip()
                
            # 检查是否有标题
            if not item.get('table_caption'):
                # 检查是否为合并单元格
                if self._is_merged_cell(item['table_body']):
                    # 提取标题
                    title = self._get_merged_title(item['table_body'])
                    if title:
                        item['table_caption'] = [title]
                else:
                    # 向前查找可合并的表格
                    merge_target = None
                    merge_target_idx = None
                    
                    # 从当前页向前查找
                    for j in range(i-1, -1, -1):
                        if not content_list[j].get('content'):
                            continue
                            
                        last_item = content_list[j]['content'][-1]
                        if last_item['type'] in ['table', 'merged_table']:
                            merge_target = last_item
                            merge_target_idx = j
                            # 记录跨页表格信息
                            if j not in cross_page_tables:
                                cross_page_tables.append(j)
                            if i not in cross_page_tables:
                                cross_page_tables.append(i)
                            break
                    
                    if merge_target:
                        try:
                            # 转换为DataFrame
                            soup1 = BeautifulSoup(merge_target['table_body'], 'lxml')
                            soup2 = BeautifulSoup(item['table_body'], 'lxml')
                            
                            # 使用 StringIO 包装 HTML 字符串
                            df1 = pd.read_html(StringIO(str(soup1)))[0]
                            df2 = pd.read_html(StringIO(str(soup2)))[0]
                            
                            # 合并表格
                            merged_df = self._merge_tables(df1, df2)
                            
                            # 转换为HTML
                            merged_html = merged_df.to_html(index=False)
                            merged_html = f"<html><body>{merged_html}</body></html>"
                            
                            # 更新目标表格的内容
                            if merge_target['type'] == 'merged_table':
                                # 如果是已合并的表格,添加新的源表格信息
                                source_tables = merge_target['metadata'].get('source_tables', [])
                                
                                # 源表格增加页码信息
                                item['page_idx'] = i
                                source_tables.append(item)
                                merge_target['metadata']['source_tables'] = source_tables
                                
                                # 追加当前页的表格图片路径
                                merge_target['img_path'].append(item['img_path'])
                            else:
                                # 如果是新合并的表格,创建新的metadata
                                item['page_idx'] = i
                                last_item['page_idx'] = i
                                
                                merge_target.update({
                                    'type': 'merged_table',
                                    'img_path': [],
                                    'metadata': {
                                        'source_tables': [
                                            merge_target,
                                            item
                                        ]
                                    }
                                })
                                # 保存所有表格的原始图片路径
                                merge_target['img_path'].append(last_item['img_path'])
                                merge_target['img_path'].append(item['img_path'])
                                # 移除原有的
                                
                            # 更新表格脚注
                            merge_target['table_footnote'] += [footnote['table_footnote'] for footnote in merge_target['metadata']['source_tables'] if footnote.get('table_footnote')]
                            
                            # 更新表格内容
                            merge_target['table_body'] = merged_html
                            
                            # 记录成功合并的页码
                            if merge_target_idx not in success_merges:
                                success_merges.append(merge_target_idx)
                            if i not in success_merges:
                                success_merges.append(i)
                            
                            # 移除当前页面的当前表格(第一个元素)
                            content_list[i]['content'].pop(0)
                            continue
                            
                        except Exception as e:
                            logger.warning(f"合并表格失败: {str(e)}")
                            # 记录合并失败的页码
                            if merge_target_idx not in failed_merges:
                                failed_merges.append(merge_target_idx)
                            if i not in failed_merges:
                                failed_merges.append(i)
                            
            i += 1
        
        # 输出跨页表格处理结果
        logger.info(f"发现跨页表格 {len(cross_page_tables)} 页: {sorted(cross_page_tables)}")
        logger.info(f"成功合并 {len(success_merges)} 页: {sorted(success_merges)}")
        logger.info(f"合并失败 {len(failed_merges)} 页: {sorted(failed_merges)}")
            
        return content_list


if __name__ == "__main__":
    table_merge = TableMerge()
    json_file_path = "/home/wumingxing/tk_rag/datas/processed/天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225/天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225_content_list.json"
    content_list = parse_json_file(json_file_path)
    new_content_list = table_merge.process_tables(content_list)
    print(new_content_list)