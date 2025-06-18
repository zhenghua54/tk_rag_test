#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试RAG聊天API接口
"""
import sys
import json
import uuid
import requests
from pathlib import Path

# 设置环境变量
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from config.global_config import GlobalConfig

def test_rag_api():
    """测试RAG聊天API接口"""
    try:
        # API接口地址
        api_url = 'http://localhost:8000/api/v1/chat/rag_chat'
        
        # 测试查询列表
        test_cases = [
            {
                "query": "发行人是什么?",
                "permission_ids": None,  # 不带权限过滤
                "session_id": str(uuid.uuid4()),
                "timeout": 30
            },
            {
                "query": "发行人是什么?",
                "permission_ids": "2",  # 带权限过滤
                "session_id": str(uuid.uuid4()),
                "timeout": 30
            },
            {
                "query": "公司的竞争优势有哪些?",
                "permission_ids": "1",
                "session_id": str(uuid.uuid4()),
                "timeout": 30
            }
        ]
        
        # 测试每个查询
        for i, test_case in enumerate(test_cases):
            print(f"\n\n===== 测试用例 {i+1} =====")
            print(f"查询: '{test_case['query']}'")
            print(f"权限ID: '{test_case['permission_ids']}'")
            print(f"会话ID: '{test_case['session_id']}'")
            
            # 去除None值，因为API不接受null值
            payload = {k: v for k, v in test_case.items() if v is not None}
            
            # 添加自定义的请求ID头
            custom_request_id = str(uuid.uuid4())
            headers = {
                'X-Request-ID': custom_request_id,
                'Content-Type': 'application/json'
            }
            
            # 发送请求
            response = requests.post(api_url, json=payload, headers=headers)
            
            # 输出结果
            print(f"\n状态码: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"\n--- 响应结果 ---")
                print(json.dumps(result, ensure_ascii=False, indent=2))
                
                if result.get("code") == 0:
                    data = result.get("data", {})
                    print(f"\n--- 生成回答 ---")
                    print(f"回答: {data.get('answer')}")
                    print(f"请求ID: {result.get('request_id')}")
                    
                    print(f"\n--- 源文档信息 ---")
                    for j, source in enumerate(data.get("metadata", [])):
                        print(f"\n源文档 {j+1}:")
                        print(f"  文档ID: {source.get('doc_id')}")
                        print(f"  片段ID: {source.get('seg_id')}")
                        print(f"  文档URL: {source.get('doc_http_url')}")
                        print(f"  相关度分数: {source.get('score')}")
                        print(f"  原始分数: {source.get('original_score')}")
                        print(f"  页码索引: {source.get('seg_page_idx')}")
                        print(f"  文档图片路径: {source.get('doc_images_path')}")
                        print(f"  创建时间: {source.get('doc_created_at')}")
                        print(f"  更新时间: {source.get('doc_updated_at')}")
                else:
                    print(f"错误: {result.get('message')}")
            else:
                print(f"请求失败: {response.text}")
                
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_rag_api() 