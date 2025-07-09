"""表格线性化模块 - 优化版本"""
import re
from typing import Dict, Any, Optional

from bs4 import BeautifulSoup

from utils.log_utils import logger


def html_to_linear_text(html: str, caption: Optional[str] = None, use_llm_enhance: bool = False) -> str:
    """HTML表格转linear文本 - 优化版本
    
    Args:
        html: HTML表格字符串
        caption: 表格标题
        use_llm_enhance: 是否使用LLM增强（可选）
        
    Returns:
        str: 线性化文本
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            return f"{caption or '表格'}：内容为空。"

        # 解析表格结构
        rows = []
        for tr in table.find_all("tr"):
            row = []
            for cell in tr.find_all(["td", "th"]):
                colspan = int(cell.get("colspan", "1"))
                text = cell.get_text(strip=True)
                row.extend([text] * colspan)
            if row:  # 只添加非空行
                rows.append(row)

        if not rows:
            return f"{caption or '表格'}：内容为空。"

        # 标准化行长度
        max_cols = max(len(row) for row in rows)
        normalized_rows = []
        for row in rows:
            normalized_row = row + [""] * (max_cols - len(row))
            normalized_rows.append(normalized_row)

        # 生成linear文本
        lines = []
        if caption:
            lines.append(f"{caption}：")

        for i, row in enumerate(normalized_rows):
            # 过滤空单元格，保留有意义的列名
            non_empty_cells = []
            for j, cell in enumerate(row):
                if cell.strip():
                    # 智能列名处理
                    if j == 0 and cell.strip().isdigit():
                        # 序号列
                        non_empty_cells.append(f"第{cell.strip()}项")
                    else:
                        non_empty_cells.append(f"第{j + 1}列'{cell.strip()}'")

                if non_empty_cells:
                    lines.append(f"第{i + 1}行：{'，'.join(non_empty_cells)}。")

            linear_text = "\n".join(lines)

            # 可选的LLM增强（仅在需要时使用）
            if use_llm_enhance and len(linear_text) > 1000:
                try:
                    from utils.llm_utils import llm_manager
                    enhanced_text = llm_manager.invoke(
                        prompt=f"请优化以下表格的线性化文本，使其更简洁清晰：\n\n{linear_text}",
                        temperature=0.3,
                        max_tokens=2000,
                        invoke_type="表格文本优化"
                    )
                    return enhanced_text.strip()
                except Exception as e:
                    logger.warning(f"LLM增强失败，使用原始文本: {str(e)}")
                    return linear_text

            return linear_text

    except Exception as e:
        logger.error(f"表格线性化失败: {str(e)}")
        # 降级处理：返回原始HTML的文本内容
        text_content = re.sub(r'<[^>]+>', '', html).strip()
        return f"{caption or '表格'}：{text_content}" if text_content else f"{caption or '表格'}：内容解析失败。"


def html_to_all_outputs(html: str, caption: Optional[str] = None) -> Dict[str, Any]:
    """保持向后兼容的接口"""
    linear_text = html_to_linear_text(html, caption)
    return {
        "json_linear": linear_text,
        "by_row": linear_text,  # 简化处理
        "meta": {"rows": 0, "cols": 0, "header": []},  # 简化元信息
    }
