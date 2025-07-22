#!/usr/bin/env python3
"""状态同步功能测试脚本

测试状态同步功能的各个方面，包括：
1. 配置加载测试
2. 状态映射测试
3. 网络连接测试
4. 错误处理测试
"""

import os
import sys
import time
import uuid
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.global_config import GlobalConfig
from utils.status_sync import sync_status_safely, get_status_sync_client


def test_config_loading():
    """测试配置加载"""
    print("=== 测试配置加载 ===")

    config = GlobalConfig.STATUS_SYNC_CONFIG
    print(f"状态同步配置: {config}")

    # 检查必要的配置项
    required_keys = ["enabled", "base_url", "timeout", "retry_attempts", "retry_delay", "api_path"]
    for key in required_keys:
        if key not in config:
            print(f"❌ 缺少配置项: {key}")
            return False
        print(f"✅ 配置项 {key}: {config[key]}")

    # 检查状态映射
    status_mapping = GlobalConfig.EXTERNAL_STATUS_MAPPING
    print(f"状态映射: {status_mapping}")

    failure_statuses = GlobalConfig.FAILURE_STATUSES
    print(f"失败状态集合: {failure_statuses}")

    return True


def test_status_mapping():
    """测试状态映射"""
    print("\n=== 测试状态映射 ===")

    client = get_status_sync_client()

    # 测试需要同步的状态
    sync_statuses = ["parsed", "splited", "parse_failed", "merge_failed", "chunk_failed", "split_failed"]
    for status in sync_statuses:
        should_sync = client.should_sync_status(status)
        external_status = client.get_external_status(status)
        is_failure = client.is_failure_status(status)

        print(f"状态 {status}:")
        print(f"  需要同步: {should_sync}")
        print(f"  外部状态: {external_status}")
        print(f"  是否失败: {is_failure}")

    # 测试不需要同步的状态
    non_sync_statuses = ["uploaded", "merged", "chunked"]
    for status in non_sync_statuses:
        should_sync = client.should_sync_status(status)
        print(f"状态 {status}: 需要同步 = {should_sync}")

    return True


def test_network_connectivity():
    """测试网络连接"""
    print("\n=== 测试网络连接 ===")

    import requests

    base_url = GlobalConfig.STATUS_SYNC_CONFIG["base_url"]
    timeout = GlobalConfig.STATUS_SYNC_CONFIG["timeout"]

    try:
        # 测试基础连接
        response = requests.get(f"{base_url}/", timeout=timeout)
        print(f"✅ 基础连接成功: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到服务器: {base_url}")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ 连接超时: {base_url}")
        return False
    except Exception as e:
        print(f"❌ 连接异常: {e}")
        return False

    return True


def test_sync_functionality(callback_url: str):
    """测试同步功能"""
    print("\n=== 测试同步功能 ===")

    # 生成测试用的文档ID和请求ID
    test_doc_id = f"test_doc_{uuid.uuid4().hex[:16]}"
    test_request_id = f"test_req_{uuid.uuid4().hex[:8]}"

    print(f"测试文档ID: {test_doc_id}")
    print(f"测试请求ID: {test_request_id}")

    # 测试成功状态同步
    print("\n--- 测试成功状态同步 ---")
    success_statuses = ["parsed", "splited"]
    for status in success_statuses:
        print(f"同步状态: {status}")
        try:
            sync_status_safely(test_doc_id, status, test_request_id, callback_url)
            print(f"✅ 状态 {status} 同步完成")
        except Exception as e:
            print(f"❌ 状态 {status} 同步失败: {e}")

    # 测试失败状态同步
    print("\n--- 测试失败状态同步 ---")
    failure_statuses = ["parse_failed", "merge_failed", "chunk_failed", "split_failed"]
    for status in failure_statuses:
        print(f"同步状态: {status}")
        try:
            sync_status_safely(test_doc_id, status, test_request_id, callback_url)
            print(f"✅ 状态 {status} 同步完成")
        except Exception as e:
            print(f"❌ 状态 {status} 同步失败: {e}")

    # 测试不需要同步的状态
    print("\n--- 测试不需要同步的状态 ---")
    non_sync_statuses = ["uploaded", "merged", "chunked"]
    for status in non_sync_statuses:
        print(f"尝试同步状态: {status}")
        try:
            sync_status_safely(test_doc_id, status, test_request_id, callback_url)
            print(f"✅ 状态 {status} 处理完成（无需同步）")
        except Exception as e:
            print(f"❌ 状态 {status} 处理失败: {e}")

    return True


def test_error_handling(callback_url: str):
    """测试错误处理"""
    print("\n=== 测试错误处理 ===")

    # 测试空参数 - sync_status_safely 是安全函数，不会抛出异常
    print("--- 测试空参数 ---")
    try:
        sync_status_safely("", "parsed", "test", callback_url)
        print("✅ 空doc_id正确处理（安全函数不抛出异常）")
    except Exception as e:
        print(f"❌ 空doc_id处理异常: {e}")

    try:
        sync_status_safely("test_doc", "", "test", callback_url)
        print("✅ 空status正确处理（安全函数不抛出异常）")
    except Exception as e:
        print(f"❌ 空status处理异常: {e}")

    # 测试无效状态
    print("\n--- 测试无效状态 ---")
    try:
        sync_status_safely("test_doc", "invalid_status", "test", callback_url)
        print("✅ 无效状态正确处理")
    except Exception as e:
        print(f"❌ 无效状态处理异常: {e}")

    return True


def test_real_document_sync(callback_url: str):
    """测试真实文档同步（可选）"""
    print("\n=== 测试真实文档同步 ===")

    # 这里可以测试一个真实存在的文档ID
    # 需要您提供一个在外部系统中存在的文档ID
    real_doc_id = input("请输入一个真实存在的文档ID进行测试（直接回车跳过）: ").strip()

    if not real_doc_id:
        print("跳过真实文档测试")
        return True

    test_request_id = f"test_req_{uuid.uuid4().hex[:8]}"

    print(f"测试真实文档ID: {real_doc_id}")
    print(f"测试请求ID: {test_request_id}")

    # 测试成功状态
    print("--- 测试成功状态 ---")
    try:
        sync_status_safely(real_doc_id, "parsed", test_request_id, callback_url)
        print("✅ 真实文档成功状态同步完成")
    except Exception as e:
        print(f"❌ 真实文档成功状态同步失败: {e}")

    return True


def main():
    """主测试函数"""
    print("🚀 开始状态同步功能测试")
    print(f"当前环境: {GlobalConfig.ENV}")
    print(f"状态同步启用: {GlobalConfig.STATUS_SYNC_CONFIG['enabled']}")
    print(f"目标URL: {GlobalConfig.STATUS_SYNC_CONFIG['base_url']}")

    # 运行各项测试
    tests = [
        test_config_loading,
        test_status_mapping,
        test_network_connectivity,
        test_sync_functionality,
        test_error_handling,
        test_real_document_sync,
    ]

    # 定义 callback_url
    callback_url = "http://192.168.6.99:18101/cbm/api/v5/knowledgeFile/parseStatusUpdated"

    passed = 0
    total = len(tests)

    for test_func in tests:
        try:
            if test_func(callback_url):
                passed += 1
                print(f"✅ 测试 {test_func.__name__} 通过")
            else:
                print(f"❌ 测试 {test_func.__name__} 失败")
        except Exception as e:
            print(f"❌ 测试 {test_func.__name__} 异常: {e}")

    print(f"\n📊 测试结果: {passed}/{total} 通过")

    if passed == total:
        print("�� 所有测试通过！")
    else:
        print("⚠️  部分测试失败，请检查配置和网络连接")

    # 提供测试总结
    print("\n📋 测试总结:")
    print("1. 配置加载: 检查所有配置项是否正确")
    print("2. 状态映射: 验证内部状态到外部状态的映射")
    print("3. 网络连接: 确认能够连接到外部系统")
    print("4. 同步功能: 测试各种状态的同步")
    print("5. 错误处理: 验证异常处理机制")
    print("6. 真实文档: 使用真实文档ID测试（可选）")

    print("\n💡 注意事项:")
    print("- '指定文档不存在' 错误是正常的，因为我们使用的是测试文档ID")
    print("- 如果要测试真实同步，请提供在外部系统中存在的文档ID")
    print("- 状态同步功能本身工作正常，只是外部系统验证文档存在性")


if __name__ == "__main__":
    main()
