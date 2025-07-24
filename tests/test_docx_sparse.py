# 测试 docx 文档的解析

from docx import Document

doc_path = "/Users/jason/Desktop/20250723测试数据（严禁外发）/总则/中国移动通信集团浙江有限公司杭州分公司DICT项目管理办法（2025版）-普通商密/附件1：中国移动杭州分公司ICT项目管理办法（2025版）.docx"

doc = Document(doc_path)

for paragraph in doc.element.body.iter():
    print(paragraph.text)
    print("-" * 100)
