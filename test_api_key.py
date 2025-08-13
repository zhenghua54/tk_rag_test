#!/usr/bin/env python3
"""
简单的API密钥测试脚本
用于验证OpenAI API密钥是否有效
"""

import os
import requests
import json
from datetime import datetime


def test_with_openai_library():
    """使用官方openai库测试API密钥"""
    print("\n" + "=" * 60)
    print("使用官方openai库测试API密钥")
    print("=" * 60)
    
    try:
        from openai import OpenAI
        
        # 获取API配置
        api_key = "sk-qMm27ouwcmuadceBPLufcntEaB5fgtxJWc6Wn7LHkfxjfGu2"
        base_url = "https://api.fe8.cn/v1"
        
        print("正在初始化OpenAI客户端...")
        
        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        print("正在发送测试消息...")
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": "请回复'Hello from OpenAI Library'来测试连接",
                }
            ],
            model="gpt-4o-mini",  # 使用更通用的模型
            max_tokens=50,
            temperature=0
        )
        
        print("✅ OpenAI库测试成功!")
        print(f"回复内容: {chat_completion.choices[0].message.content}")
        print(f"模型: {chat_completion.model}")
        print(f"使用token数: {chat_completion.usage.total_tokens if chat_completion.usage else 'unknown'}")
        
    except Exception as e:
        print(f"❌ OpenAI库测试失败: {e}")
        print("详细错误信息:")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    
    # 测试2: 使用官方openai库
    test_with_openai_library()
    
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
