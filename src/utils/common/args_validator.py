"""参数校验工具类"""
import os.path
from typing import Any, List, Union
from bs4 import BeautifulSoup


class Validator:
    @staticmethod
    def validate_not_empty(value: Any, param_name: str) -> None:
        """验证参数非空
        
        Args:
            value: 要验证的值
            param_name: 参数名称
            
        Raises:
            ValueError: 当参数为空时抛出
        """
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError(f"{param_name} 不能为空")

    @staticmethod
    def validate_type(value: Any, expected_type: Union[type, tuple], param_name: str) -> None:
        """验证参数类型
        
        Args:
            value: 要验证的值
            expected_type: 期望的类型
            param_name: 参数名称
            
        Raises:
            TypeError: 当参数类型不匹配时抛出
        """
        if not isinstance(value, expected_type):
            raise TypeError(f"{param_name} 必须是 {expected_type} 类型")

    @staticmethod
    def validate_list_not_empty(value: List, param_name: str) -> None:
        """验证列表非空
        
        Args:
            value: 要验证的列表
            param_name: 参数名称
            
        Raises:
            ValueError: 当列表为空时抛出
        """
        if not isinstance(value, list):
            raise TypeError(f"{param_name} 必须是列表类型")
        if len(value) == 0:
            raise ValueError(f"{param_name} 列表不能为空")

    @staticmethod
    def validate_doc_id(doc_id: str) -> None:
        """验证文档ID格式
        
        Args:
            doc_id: 文档ID
            
        Raises:
            ValueError: 当文档ID格式不正确时抛出
        """
        Validator.validate_not_empty(doc_id, "doc_id")
        Validator.validate_type(doc_id, str, "doc_id")
        if len(doc_id) != 64:
            raise ValueError("doc_id 必须是64位哈希值字符串")

    @staticmethod
    def validate_segment_id(segment_id: str) -> None:
        """验证分段ID格式
        
        Args:
            segment_id: 分段ID
            
        Raises:
            ValueError: 当分段ID格式不正确时抛出
        """
        Validator.validate_not_empty(segment_id, "segment_id")
        Validator.validate_type(segment_id, str, "segment_id")
        if len(segment_id) != 64:
            raise ValueError("segment_id 必须是64位哈希值字符串")

    @staticmethod
    def validate_department_id(department_id: str) -> None:
        """验证部门ID格式
        
        Args:
            department_id: 部门ID
            
        Raises:
            ValueError: 当部门ID格式不正确时抛出
        """
        Validator.validate_not_empty(department_id, "department_id")
        Validator.validate_type(department_id, str, "department_id")

    @staticmethod
    def validate_html_table(html: str) -> None:
        """验证 HTML 表格格式
        
        Args:
            html: HTML 表格字符串
            
        Raises:
            ValueError: 当 HTML 格式不正确时抛出
        """
        Validator.validate_not_empty(html, "html")
        Validator.validate_type(html, str, "html")

        # 检查基本的 HTML 结构
        if not html.strip().startswith('<table'):
            raise ValueError("HTML 必须以 <table> 标签开始")

        if not html.strip().endswith('</table>'):
            raise ValueError("HTML 必须以 </table> 标签结束")

        # 检查表格标签的完整性
        if html.count('<table') != html.count('</table>'):
            raise ValueError("表格标签不匹配")

        if html.count('<tr') != html.count('</tr>'):
            raise ValueError("行标签不匹配")

        if html.count('<td') != html.count('</td>'):
            raise ValueError("单元格标签不匹配")

        # 检查表格属性的合法性
        soup = BeautifulSoup(html, 'lxml')
        table = soup.find('table')

        if not table:
            raise ValueError("未找到表格标签")

        # 检查 colspan 和 rowspan 属性
        for cell in table.find_all(['td', 'th']):
            # 检查 colspan
            colspan = cell.get('colspan')
            if colspan:
                try:
                    colspan = int(colspan)
                    if colspan < 1:
                        raise ValueError(f"colspan 值必须大于 0: {colspan}")
                except ValueError:
                    raise ValueError(f"colspan 必须是整数: {colspan}")

            # 检查 rowspan
            rowspan = cell.get('rowspan')
            if rowspan:
                try:
                    rowspan = int(rowspan)
                    if rowspan < 1:
                        raise ValueError(f"rowspan 值必须大于 0: {rowspan}")
                except ValueError:
                    raise ValueError(f"rowspan 必须是整数: {rowspan}")

    @staticmethod
    def validate_file(file_path: str) -> None:
        """验证文件路径是否存在

        Args:
            file_path
        """
        Validator.validate_not_empty(file_path, "file_path")
        Validator.validate_type(file_path, str, "file_path")
        if not os.path.isfile(file_path):
            raise ValueError(f"文件不存在: {file_path}")