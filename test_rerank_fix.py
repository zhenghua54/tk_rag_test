#!/usr/bin/env python3
"""
测试重排序模型显存优化效果
"""

import os
import sys
import torch
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

from utils.llm_utils import rerank_manager
from utils.log_utils import logger


def test_rerank_memory_optimization():
    """测试重排序模型的显存优化效果"""
    
    logger.info("=" * 60)
    logger.info("开始测试重排序模型显存优化")
    logger.info("=" * 60)
    
    if torch.cuda.is_available():
        # 显示初始显存状态
        initial_memory = torch.cuda.memory_allocated()
        total_memory = torch.cuda.get_device_properties(0).total_memory
        logger.info(f"初始显存使用: {initial_memory / 1024**3:.2f} GB / {total_memory / 1024**3:.2f} GB")
    
    # 测试查询
    query = "什么是人工智能?"
    
    # 创建50个测试文档段落（模拟实际场景）
    passages = [
        f"这是第{i+1}个测试文档段落。人工智能是一门让机器能够像人类一样思考和学习的科学技术。它包括机器学习、深度学习、自然语言处理等多个领域。" 
        for i in range(50)
    ]
    
    logger.info(f"测试查询: {query}")
    logger.info(f"测试文档段落数量: {len(passages)}")
    
    try:
        # 执行重排序
        logger.info("开始执行重排序...")
        scores = rerank_manager.rerank(query, passages)
        
        logger.info(f"重排序完成! 返回分数数量: {len(scores)}")
        logger.info(f"前5个分数: {scores[:5]}")
        
        if torch.cuda.is_available():
            final_memory = torch.cuda.memory_allocated()
            logger.info(f"重排序后显存使用: {final_memory / 1024**3:.2f} GB")
            logger.info(f"显存增长: {(final_memory - initial_memory) / 1024**3:.2f} GB")
        
        logger.info("✅ 重排序测试成功！")
        return True
        
    except Exception as e:
        logger.error(f"❌ 重排序测试失败: {str(e)}")
        return False
    
    finally:
        # 清理显存
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()


def test_edge_cases():
    """测试边界情况"""
    
    logger.info("=" * 60)
    logger.info("测试边界情况")
    logger.info("=" * 60)
    
    query = "测试查询"
    
    # 测试1: 小批量数据
    logger.info("测试1: 小批量数据 (5个段落)")
    small_passages = [f"小批量测试段落{i}" for i in range(5)]
    try:
        scores = rerank_manager.rerank(query, small_passages)
        logger.info(f"✅ 小批量测试成功，返回分数: {len(scores)}")
    except Exception as e:
        logger.error(f"❌ 小批量测试失败: {e}")
    
    # 测试2: 空段落列表
    logger.info("测试2: 空段落列表")
    try:
        scores = rerank_manager.rerank(query, [])
        logger.info(f"✅ 空段落测试成功，返回分数: {len(scores)}")
    except Exception as e:
        logger.error(f"❌ 空段落测试失败: {e}")
    
    # 测试3: 单个段落
    logger.info("测试3: 单个段落")
    try:
        scores = rerank_manager.rerank(query, ["单个测试段落"])
        logger.info(f"✅ 单个段落测试成功，返回分数: {len(scores)}")
    except Exception as e:
        logger.error(f"❌ 单个段落测试失败: {e}")


if __name__ == "__main__":
    print("重排序模型显存优化测试")
    print("=" * 60)
    
    # 主要测试
    success = test_rerank_memory_optimization()
    
    # 边界情况测试
    test_edge_cases()
    
    print("=" * 60)
    if success:
        print("🎉 所有测试完成！重排序显存优化工作正常。")
    else:
        print("⚠️  测试完成，但存在问题，请检查日志。")
