#!/usr/bin/env python3
"""
Dify API连接测试脚本

用于测试Dify平台API是否正常工作
"""

import asyncio
import aiohttp
import json

# Dify API配置
DIFY_API_KEY = "app-eCw9INTLaMi6O2foeSVibfy2"
DIFY_BASE_URL = "http://192.168.31.205"
DIFY_CHAT_ENDPOINT = "/v1/completion-messages"

async def test_dify_api():
    """测试Dify API连接"""
    print("开始测试Dify API连接...")
    
    # 构建请求URL
    url = f"{DIFY_BASE_URL}{DIFY_CHAT_ENDPOINT}"
    
    # 构建请求头
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 构建测试请求体
    test_prompt = "Hello, this is a test message. Please respond with a simple greeting."
    
    payload = {
        "inputs": {"query": test_prompt},
        "response_mode": "blocking",
        "user": "test_user_generic"
    }
    
    try:
        print(f"发送请求到: {url}")
        print(f"请求头: {headers}")
        print(f"请求体: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        # 发送请求
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                print(f"\n响应状态码: {response.status}")
                print(f"响应头: {dict(response.headers)}")
                
                if response.status == 200:
                    result = await response.json()
                    print(f"\n响应成功！")
                    print(f"响应内容: {json.dumps(result, indent=2, ensure_ascii=False)}")
                    
                    # 检查响应结构
                    if "answer" in result:
                        print(f"\n✅ API调用成功，获取到答案: {result['answer']}")
                    elif "message" in result:
                        print(f"\n✅ API调用成功，获取到消息: {result['message']}")
                    else:
                        print(f"\n⚠️ API调用成功，但响应格式可能不符合预期")
                        print(f"响应键: {list(result.keys())}")
                        
                else:
                    error_text = await response.text()
                    print(f"\n❌ API调用失败")
                    print(f"错误详情: {error_text}")
                    
    except Exception as e:
        print(f"\n❌ API调用异常: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主函数"""
    print("Dify API连接测试工具")
    print("="*50)
    
    # 运行API测试
    await test_dify_api()
    
    print("\n" + "="*50)
    print("测试完成！")

if __name__ == "__main__":
    asyncio.run(main())
