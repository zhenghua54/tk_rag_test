"""处理表格标题内容"""

json_file_path = "/home/wumingxing/tk_rag/datas/processed/天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225/天宽服务质量体系手册-V1.0 (定稿_打印版)_20250225_content_list.json"

content_list = parse_json_file(json_file_path)

# 遍历所有表格类型的片段,如果没有 table_caption 字段 : 首先检查表格第一行是否为一个合并单元格,其次若前一片段是text 则将该片段的文本作为表格标题, 