#!/usr/bin/env python3
"""
快速查看Dify知识库列表

不等待用户输入，直接显示所有信息。
"""

import requests
import json

def quick_list_knowledge_bases():
    """快速列出知识库"""
    
    # 配置参数
    DIFY_BASE_URL = "http://192.168.31.205"
    DIFY_API_KEY = "dataset-L7pHf6iaAwImkw5601pv3N2u"
    
    print("🚀 快速查看Dify知识库")
    print("=" * 50)
    print(f"服务器地址: {DIFY_BASE_URL}")
    print(f"API密钥: {DIFY_API_KEY[:10]}...")
    print()
    
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 获取知识库列表 - 添加分页参数
    base_url = f"{DIFY_BASE_URL}/v1/datasets"
    
    # 尝试不同的查询参数组合
    test_urls = [
        f"{base_url}?page=1&limit=100",  # 官方文档格式
        f"{base_url}?page=1&limit=50",   # 较大限制
        f"{base_url}?page=1&limit=20",   # 默认限制
        f"{base_url}?include_all=true",  # 包含所有数据集
        base_url                          # 无参数
    ]
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n{i}️⃣ 测试请求 {i}: {url}")
        print("-" * 40)
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 请求成功!")
                
                # 显示分页信息
                total = data.get("total", 0)
                has_more = data.get("has_more", False)
                page = data.get("page", 1)
                limit = data.get("limit", 20)
                knowledge_bases = data.get("data", [])
                
                print(f"📊 分页信息:")
                print(f"   当前页: {page}")
                print(f"   每页数量: {limit}")
                print(f"   总数: {total}")
                print(f"   是否有更多: {has_more}")
                print(f"   当前页数量: {len(knowledge_bases)}")
                
                if knowledge_bases:
                    print(f"\n📚 知识库列表 (共{len(knowledge_bases)}个):")
                    print("=" * 80)
                    
                    for j, kb in enumerate(knowledge_bases, 1):
                        print(f"{j:2d}. 名称: {kb.get('name', 'N/A')}")
                        print(f"    ID: {kb.get('id', 'N/A')}")
                        print(f"    描述: {kb.get('description', 'N/A')}")
                        print(f"    权限: {kb.get('permission', 'N/A')}")
                        print(f"    数据源类型: {kb.get('data_source_type', 'N/A')}")
                        print(f"    索引技术: {kb.get('indexing_technique', 'N/A')}")
                        print(f"    应用数量: {kb.get('app_count', 'N/A')}")
                        print(f"    文档数量: {kb.get('document_count', 'N/A')}")
                        print(f"    词数: {kb.get('word_count', 'N/A')}")
                        print(f"    创建者: {kb.get('created_by', 'N/A')}")
                        print(f"    创建时间: {kb.get('created_at', 'N/A')}")
                        print(f"    更新者: {kb.get('updated_by', 'N/A')}")
                        print(f"    更新时间: {kb.get('updated_at', 'N/A')}")
                        print(f"    嵌入模型: {kb.get('embedding_model', 'N/A')}")
                        print(f"    嵌入模型提供商: {kb.get('embedding_model_provider', 'N/A')}")
                        print(f"    嵌入可用: {kb.get('embedding_available', 'N/A')}")
                        print("-" * 80)
                    
                    # 如果找到多个知识库，停止测试
                    if total > 1 or len(knowledge_bases) > 1:
                        print(f"\n🎯 找到多个知识库！停止测试")
                        break
                else:
                    print("\n📭 没有找到知识库")
                    
            else:
                print(f"❌ 请求失败: {response.status_code}")
                print(f"响应内容: {response.text[:200]}...")
                
        except Exception as e:
            print(f"❌ 错误: {e}")
        
        print()
    
    # 最终总结
    print("🎯 所有测试完成!")
    print("如果仍然只显示1个知识库，可能的原因:")
    print("1. API密钥权限限制")
    print("2. 工作空间隔离")
    print("3. 其他知识库在不同团队或用户下")
    print("4. 需要特定的查询参数")


if __name__ == "__main__":
    quick_list_knowledge_bases()
