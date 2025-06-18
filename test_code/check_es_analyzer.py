#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查ES的分词情况
"""
import sys
from pathlib import Path

# 设置环境变量
root_path = Path(__file__).resolve().parent
sys.path.append(str(root_path))

from elasticsearch import Elasticsearch
from config.global_config import GlobalConfig


def check_es_analyzer():
    """检查ES的分词情况"""
    try:
        # 创建ES客户端
        es_username = GlobalConfig.ES_CONFIG.get('username', '')
        es_password = GlobalConfig.ES_CONFIG.get('password', '')
        
        # 创建ES客户端配置
        es_params = {
            "hosts": GlobalConfig.ES_CONFIG['host'],
            "request_timeout": GlobalConfig.ES_CONFIG["timeout"],
            "verify_certs": GlobalConfig.ES_CONFIG.get('verify_certs', False)
        }
        
        # 添加认证信息
        if es_username and es_password:
            es_params["basic_auth"] = (es_username, es_password)
        
        client = Elasticsearch(**es_params)
        index_name = GlobalConfig.ES_CONFIG["index_name"]
        
        # 要测试的文本列表
        test_texts = [
            "发行人",
            "发行人是什么",
            "竞争",
            "公司",
            "公司成立于",
            "AI",
            "发行人在行业中的竞争情况"
        ]
        
        print("\n===== ES分词器测试 =====")
        
        # 获取索引设置，查看分词器配置
        index_settings = client.indices.get_settings(index=index_name)
        print("\n索引设置:")
        print(str(index_settings))
        
        # 获取索引映射
        index_mappings = client.indices.get_mapping(index=index_name)
        print("\n索引映射:")
        print(str(index_mappings))
        
        # 测试每个文本的分词结果
        for text in test_texts:
            print(f"\n\n===== 文本: '{text}' 的分词结果 =====")
            
            # 使用索引的默认分词器
            analyze_result = client.indices.analyze(
                index=index_name,
                body={
                    "text": text,
                    "analyzer": "ik_max_word"  # 使用ik_max_word分词器
                }
            )
            
            print("IK_MAX_WORD分词结果:")
            tokens = [token["token"] for token in analyze_result["tokens"]]
            print(f"分词数量: {len(tokens)}")
            print(f"分词结果: {', '.join(tokens)}")
            
            # 使用标准分词器进行对比
            analyze_result = client.indices.analyze(
                index=index_name,
                body={
                    "text": text,
                    "analyzer": "standard"  # 使用标准分词器
                }
            )
            
            print("\nSTANDARD分词结果:")
            tokens = [token["token"] for token in analyze_result["tokens"]]
            print(f"分词数量: {len(tokens)}")
            print(f"分词结果: {', '.join(tokens)}")
            
    except Exception as e:
        print(f"检查ES分词器失败: {e}")

if __name__ == "__main__":
    check_es_analyzer() 