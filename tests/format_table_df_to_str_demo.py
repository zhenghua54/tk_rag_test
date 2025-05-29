def format_table_for_str(table_df: pd.DataFrame) -> str:
    """
    将HTML表格格式化为适合embedding的字符串格式
    
    Args:
        table_df (pd.DataFrame): 表格DataFrame
        
    Returns:
        str: 格式化后的表格字符串
    """
    try:
        if table_df.empty:
            return ""
        
        # 获取表头（第一行作为列名）
        if len(table_df) > 0:
            headers = []
            first_row = table_df.iloc[0]
            for col_idx, value in enumerate(first_row):
                if pd.notna(value) and str(value).strip() and str(value).strip() != 'NaN':
                    headers.append(str(value).strip())
                else:
                    headers.append(f"列{col_idx+1}")
            
            # 处理数据行
            formatted_rows = []
            for row_idx in range(1, len(table_df)):  # 从第二行开始
                row = table_df.iloc[row_idx]
                row_items = []
                
                for col_idx, value in enumerate(row):
                    if pd.notna(value) and str(value).strip() and str(value).strip() != 'NaN':
                        header_name = headers[col_idx] if col_idx < len(headers) else f"列{col_idx+1}"
                        row_items.append(f"{header_name}:{str(value).strip()}")
                
                if row_items:  # 只添加非空行
                    formatted_rows.append(" | ".join(row_items))
            
            # 组合结果 - 更简洁的格式
            result_lines = []
            if headers:
                # 表格标题行
                result_lines.append("表格标题: " + " | ".join(headers))
                result_lines.append("---")
            
            # 数据行
            for i, row_content in enumerate(formatted_rows, 1):
                result_lines.append(f"第{i}行: {row_content}")
            
            return "\n".join(result_lines)
        
    except Exception as e:
        print(f"表格格式化出错: {e}")
        return ""
    
    return ""