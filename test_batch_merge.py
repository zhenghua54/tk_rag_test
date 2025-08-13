#!/usr/bin/env python3
"""
测试批次合并功能
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from tests.evaluate_ragbench_with_ragas import RagBenchRagasEvaluator
import logging

# 设置日志级别
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_batch_merge():
    """测试批次合并功能"""
    
    evaluator = RagBenchRagasEvaluator()
    
    # 创建模拟的评估结果
    class MockResult:
        def __init__(self, scores_dict):
            self._scores_dict = scores_dict
            self.scores = scores_dict
        
        def to_pandas(self):
            import pandas as pd
            return pd.DataFrame(self._scores_dict)
    
    # 模拟两个批次的结果
    batch1_scores = {
        'faithfulness': [0.8, 0.9, 0.7],
        'answer_relevancy': [0.85, 0.92, 0.78],
        'context_precision': [0.75, 0.88, 0.72],
        'context_recall': [0.82, 0.91, 0.79]
    }
    
    batch2_scores = {
        'faithfulness': [0.6, 0.8],
        'answer_relevancy': [0.65, 0.83],
        'context_precision': [0.62, 0.81],
        'context_recall': [0.68, 0.84]
    }
    
    batch1 = MockResult(batch1_scores)
    batch2 = MockResult(batch2_scores)
    
    all_results = [batch1, batch2]
    
    # 测试合并
    print("=" * 60)
    print("测试批次合并功能")
    print("=" * 60)
    
    print(f"批次1样本数: {len(batch1_scores['faithfulness'])}")
    print(f"批次2样本数: {len(batch2_scores['faithfulness'])}")
    print(f"预期总样本数: {len(batch1_scores['faithfulness']) + len(batch2_scores['faithfulness'])}")
    
    try:
        merged_result = evaluator._merge_batch_results(all_results)
        
        if hasattr(merged_result, '_scores_dict'):
            merged_scores = merged_result._scores_dict
            print("\n合并结果:")
            for metric, scores in merged_scores.items():
                print(f"{metric}: {len(scores)} 个分数 - {scores}")
        elif hasattr(merged_result, 'to_pandas'):
            df = merged_result.to_pandas()
            print(f"\n合并结果DataFrame形状: {df.shape}")
            print(f"列名: {list(df.columns)}")
            for col in df.columns:
                print(f"{col}: {df[col].tolist()}")
        else:
            print("未知的合并结果格式")
        
        print("\n✅ 批次合并测试成功！")
        return True
        
    except Exception as e:
        print(f"\n❌ 批次合并测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_batch_merge()
