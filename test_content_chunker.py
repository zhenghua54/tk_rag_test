import json
from src.core.document.content_chunker import segment_text_content

def test_segment_text_content():
    # 测试文档路径
    doc_process_path = "datas/processed/天宽服务质量体系_第1部分_1-22/天宽服务质量体系_第1部分_1-22_mineru_merged.json"
    
    # 测试参数
    doc_id = "162680e39129e7f6a7df0005160ac5fbb11d7c7fd1b65d7182e4ea8b2b258b26"
    document_name = "天宽服务质量体系_第1部分_1-22"
    permission_ids = '{"departments": ["1"], "roles": [], "users": []}'
    
    try:
        # 执行文档切块
        result = segment_text_content(
            doc_id=doc_id,
            document_name=document_name,
            doc_process_path=doc_process_path,
            permission_ids=permission_ids
        )
        
        print(f"文档切块结果: {result}")
        
    except Exception as e:
        print(f"文档切块失败: {str(e)}")

if __name__ == "__main__":
    test_segment_text_content() 