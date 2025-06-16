#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试文档分块功能
"""
import sys
import json
from pathlib import Path

# 设置环境变量
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from src.core.document.content_chunker import segment_text_content
from src.utils.common.logger import logger

def test_document_chunk():
    """测试文档分块功能"""
    try:
        # 测试文档信息
        doc_id = "test_doc_001"
        document_name = "测试文档"
        doc_process_path = "datas/processed/test_doc.json"
        permission_ids = '{"departments": ["1"], "roles": [], "users": []}'
        
        # 创建测试文档内容
        test_content = {
            "0": [{
                "type": "text",
                "text": "这是第一页的文本内容。\n这是第一页的第二行。"
            }],
            "1": [{
                "type": "text",
                "text": "这是第二页的文本内容。\n这是第二页的第二行。"
            }],
            "2": [{
                "type": "table",
                "table_body": "<table><tr><td>测试表格</td></tr></table>",
                "table_caption": "表格标题",
                "table_footnote": "表格注释"
            }]
        }
        
        # 保存测试文档
        with open(doc_process_path, "w", encoding="utf-8") as f:
            json.dump(test_content, f, ensure_ascii=False, indent=2)
            
        # 执行分块
        result = segment_text_content(
            doc_id=doc_id,
            document_name=document_name,
            doc_process_path=doc_process_path,
            permission_ids=permission_ids
        )
        
        print(f"分块结果: {result}")
        
    except Exception as e:
        logger.error(f"测试失败: {str(e)}")
        raise

if __name__ == "__main__":
    test_document_chunk() 