#!/usr/bin/env python3
"""
测试RAGAS评估脚本的调试版本
"""

import asyncio
import sys
sys.path.append('.')

from tests.evaluate_ragbench_with_ragas import RagBenchRagasEvaluator

async def test_evaluation():
    """测试评估功能"""
    evaluator = RagBenchRagasEvaluator()
    
    print("开始测试RAGAS评估（带调试信息）...")
    
    # 运行一个小样本测试
    await evaluator.run_complete_evaluation(
        task_name="emanual", 
        split="test", 
        sample_size=2
    )
    
    print("测试完成！")

if __name__ == "__main__":
    asyncio.run(test_evaluation())
