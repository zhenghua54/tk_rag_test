#!/usr/bin/env python3
"""
简化的RAGAS评估测试脚本
只测试RAGAS评估功能，不依赖外部组件
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, List

# 添加项目路径
sys.path.append('.')

from utils.log_utils import logger

class SimpleRagasEvaluator:
    """简化的RAGAS评估器"""
    
    def __init__(self):
        """初始化评估器"""
        logger.info("简化RAGAS评估器初始化完成")
    
    def _test_api_connection(self, api_key: str, base_url: str) -> bool:
        """测试API连接"""
        try:
            logger.info("测试API连接...")
            import requests
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            test_data = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 10
            }
            
            response = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=test_data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("API连接测试成功")
                return True
            else:
                logger.error(f"API连接测试失败: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"API连接测试异常: {e}")
            return False

    def _custom_ragas_evaluation(self, data: Dict[str, List]) -> Dict[str, float]:
        """使用自定义系统提示词的RAGAS评估方法"""
        try:
            logger.info("使用自定义RAGAS评估方法...")
            
            # 检查配置
            logger.info("开始导入必要的模块...")
            
            from openai import OpenAI
            import re
            
            logger.info("模块导入成功，开始初始化LLM...")
            
            # 初始化LLM
            logger.info("正在初始化OpenAI客户端...")
            
            # 从环境变量获取API配置，如果没有则使用默认值
            api_key = os.getenv("OPENAI_API_KEY", "sk-qMm27ouwcmuadceBPLufcntEaB5fgtxJWc6Wn7LHkfxjfGu2")
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.fe8.cn/v1")
            
            logger.info(f"API密钥来源: {'环境变量' if os.getenv('OPENAI_API_KEY') else '默认值'}")
            logger.info(f"API基础URL来源: {'环境变量' if os.getenv('OPENAI_BASE_URL') else '默认值'}")
            
            logger.info(f"使用API密钥: {api_key[:10]}...{api_key[-4:]}")
            logger.info(f"使用API基础URL: {base_url}")
            
            # 测试API连接
            if not self._test_api_connection(api_key, base_url):
                logger.error("API连接测试失败，跳过自定义评估")
                return self._simple_evaluation(data)
            
            # 使用官方openai库
            client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
            logger.info("OpenAI客户端初始化完成")
            
            total_questions = len(data["question"])
            logger.info(f"开始评估，总问题数: {total_questions}")
            if total_questions == 0:
                logger.warning("没有找到问题数据，返回空结果")
                return {}
            
            # 存储所有评估分数
            all_scores = {
                "faithfulness": [],
                "answer_relevancy": [],
                "context_precision": [],
                "context_recall": []
            }
            logger.info("评估分数存储结构初始化完成")
            
            for i in range(total_questions):
                logger.info(f"开始处理第 {i+1}/{total_questions} 个问题...")
                question = data["question"][i]
                answer = data["answer"][i]
                contexts = data["contexts"][i]
                ground_truth = data["ground_truth"][i]
                
                logger.debug(f"问题: {question[:100]}...")
                logger.debug(f"答案: {answer[:100]}...")
                logger.debug(f"上下文数量: {len(contexts) if contexts else 0}")
                
                # 准备上下文文本
                context_text = "\n".join(contexts) if contexts else ""
                logger.debug(f"上下文文本长度: {len(context_text)}")
                
                # 构建评估提示词
                logger.info("开始构建评估提示词...")
                try:
                    prompt = self._build_evaluation_prompt(question, answer, context_text)
                    logger.info("评估提示词构建成功")
                    logger.debug(f"提示词长度: {len(prompt)}")
                except Exception as e:
                    logger.error(f"构建评估提示词失败: {e}")
                    raise e
                
                try:
                    # 调用LLM进行评估
                    logger.info(f"开始调用LLM进行评估...")
                    logger.debug(f"发送给LLM的提示词: {prompt[:200]}...")
                    
                    # 使用官方openai库调用
                    chat_completion = client.chat.completions.create(
                        messages=[
                            {
                                "role": "user",
                                "content": prompt,
                            }
                        ],
                        model="gpt-4o-mini",
                        max_tokens=1000,
                        temperature=0
                    )
                    
                    evaluation_text = chat_completion.choices[0].message.content
                    logger.info(f"LLM响应成功，响应长度: {len(evaluation_text)}")
                    logger.debug(f"LLM响应内容: {evaluation_text[:200]}...")
                    
                    # 解析评估结果
                    logger.info("开始解析评估结果...")
                    scores = self._parse_evaluation_response(evaluation_text)
                    logger.info(f"解析完成，分数: {scores}")
                    
                    # 添加到总分数中
                    for metric, score in scores.items():
                        if metric in all_scores:
                            all_scores[metric].append(score)
                    
                    logger.debug(f"问题 {i+1} 评估完成: {scores}")
                    
                except Exception as e:
                    logger.warning(f"问题 {i+1} 评估失败: {e}")
                    logger.error(f"详细错误信息: {str(e)}")
                    import traceback
                    logger.error(f"错误堆栈: {traceback.format_exc()}")
                    
                    # 检查是否是API密钥问题
                    error_str = str(e).lower()
                    if "key" in error_str and ("invalid" in error_str or "check" in error_str):
                        logger.error("检测到API密钥问题，请检查以下配置：")
                        logger.error("1. 设置环境变量 OPENAI_API_KEY 为有效的API密钥")
                        logger.error("2. 设置环境变量 OPENAI_BASE_URL 为正确的API端点")
                        logger.error("3. 确保API密钥有足够的配额和权限")
                        logger.error("示例: export OPENAI_API_KEY='your-valid-api-key'")
                        logger.error("示例: export OPENAI_BASE_URL='https://api.openai.com/v1'")
                    
                    # 使用默认分数
                    for metric in all_scores:
                        all_scores[metric].append(0.5)
            
            # 计算平均分数
            results = {}
            for metric, scores in all_scores.items():
                if scores:
                    results[metric] = sum(scores) / len(scores)
                else:
                    results[metric] = 0.0
            
            logger.info("自定义RAGAS评估完成")
            return results
            
        except Exception as e:
            logger.error(f"自定义RAGAS评估失败: {e}")
            return self._simple_evaluation(data)

    def _build_evaluation_prompt(self, question: str, answer: str, context: str) -> str:
        """构建评估提示词"""
        prompt = f"""You are an expert language model evaluator for RAG (Retrieval-Augmented Generation) systems.

Your task is to evaluate the quality of RAG system responses based on the following criteria:

## Evaluation Criteria:

### 1. Faithfulness (忠实性)
Determine whether the answer is **faithful to the provided context**, i.e., whether it is directly supported by any statement(s) in the context.

**Scoring:**
- **1.0 (Excellent)**: Answer is completely faithful to the context, all claims are directly supported
- **0.7 (Good)**: Answer is mostly faithful, with minor unsupported claims
- **0.4 (Fair)**: Answer is partially faithful, some claims lack support
- **0.0 (Poor)**: Answer contains significant unsupported claims or contradicts context

### 2. Answer Relevancy (答案相关性)
Assess whether the answer is relevant to the user's question.

**Scoring:**
- **1.0 (Excellent)**: Answer directly addresses the question completely
- **0.7 (Good)**: Answer addresses most aspects of the question
- **0.4 (Fair)**: Answer partially addresses the question
- **0.0 (Poor)**: Answer is irrelevant or doesn't address the question

### 3. Context Precision (上下文精确性)
Evaluate whether the retrieved context is precise and relevant to the question.

**Scoring:**
- **1.0 (Excellent)**: All context passages are highly relevant to the question
- **0.7 (Good)**: Most context passages are relevant
- **0.4 (Fair)**: Some context passages are relevant
- **0.0 (Poor)**: Context passages are mostly irrelevant

### 4. Context Recall (上下文召回性)
Assess whether the context contains sufficient information to answer the question.

**Scoring:**
- **1.0 (Excellent)**: Context contains all necessary information
- **0.7 (Good)**: Context contains most necessary information
- **0.4 (Fair)**: Context contains some necessary information
- **0.0 (Poor)**: Context lacks essential information

## Input Format:
- **Question**: {question}
- **Answer**: {answer}
- **Context**: {context}

## Output Format:
Provide scores for each metric (0.0 to 1.0) and brief justification:

**Faithfulness**: [score] - [justification]
**Answer Relevancy**: [score] - [justification]  
**Context Precision**: [score] - [justification]
**Context Recall**: [score] - [justification]

## Important Guidelines:
1. Only consider information from the provided context
2. Do not make assumptions or use external knowledge
3. Be objective and consistent in scoring
4. Provide clear justification for each score
5. If context is empty or answer is empty, score appropriately (usually 0.0)"""
        
        return prompt

    def _parse_evaluation_response(self, response_text: str) -> Dict[str, float]:
        """解析LLM的评估响应"""
        try:
            scores = {}
            
            # 使用正则表达式提取分数
            patterns = {
                "faithfulness": r"Faithfulness[:\s]*([0-9]*\.?[0-9]+)",
                "answer_relevancy": r"Answer Relevancy[:\s]*([0-9]*\.?[0-9]+)",
                "context_precision": r"Context Precision[:\s]*([0-9]*\.?[0-9]+)",
                "context_recall": r"Context Recall[:\s]*([0-9]*\.?[0-9]+)"
            }
            
            for metric, pattern in patterns.items():
                match = re.search(pattern, response_text, re.IGNORECASE)
                if match:
                    try:
                        score = float(match.group(1))
                        # 确保分数在0-1范围内
                        score = max(0.0, min(1.0, score))
                        scores[metric] = score
                    except ValueError:
                        scores[metric] = 0.5
                else:
                    scores[metric] = 0.5
            
            return scores
            
        except Exception as e:
            logger.error(f"解析评估响应失败: {e}")
            return {
                "faithfulness": 0.5,
                "answer_relevancy": 0.5,
                "context_precision": 0.5,
                "context_recall": 0.5
            }

    def _simple_evaluation(self, data: Dict[str, List]) -> Dict[str, float]:
        """简化的评估方法"""
        try:
            logger.info("使用简化评估方法...")
            
            total_questions = len(data["question"])
            if total_questions == 0:
                return {}
            
            # 简单的基于规则的评估
            faithfulness_scores = []
            answer_relevancy_scores = []
            context_precision_scores = []
            context_recall_scores = []
            
            for i in range(total_questions):
                question = data["question"][i]
                answer = data["answer"][i]
                contexts = data["contexts"][i]
                ground_truth = data["ground_truth"][i]
                
                # 简单的评分规则
                # 1. Faithfulness: 检查答案是否包含在上下文中
                faithfulness = 0.5  # 默认中等分数
                if answer and contexts:
                    context_text = " ".join(contexts)
                    # 简单的关键词匹配
                    answer_words = set(answer.lower().split())
                    context_words = set(context_text.lower().split())
                    overlap = len(answer_words.intersection(context_words))
                    if len(answer_words) > 0:
                        faithfulness = min(1.0, overlap / len(answer_words))
                
                # 2. Answer Relevancy: 检查答案长度和内容
                relevancy = 0.5
                if answer and len(answer.strip()) > 10:
                    relevancy = 0.8
                elif answer and len(answer.strip()) > 5:
                    relevancy = 0.6
                
                # 3. Context Precision: 检查上下文是否相关
                precision = 0.5
                if contexts and any(len(ctx.strip()) > 20 for ctx in contexts):
                    precision = 0.7
                
                # 4. Context Recall: 检查是否有上下文
                recall = 0.5
                if contexts and any(len(ctx.strip()) > 10 for ctx in contexts):
                    recall = 0.8
                
                faithfulness_scores.append(faithfulness)
                answer_relevancy_scores.append(relevancy)
                context_precision_scores.append(precision)
                context_recall_scores.append(recall)
            
            # 计算平均分数
            results = {
                "faithfulness": sum(faithfulness_scores) / len(faithfulness_scores),
                "answer_relevancy": sum(answer_relevancy_scores) / len(answer_relevancy_scores),
                "context_precision": sum(context_precision_scores) / len(context_precision_scores),
                "context_recall": sum(context_recall_scores) / len(context_recall_scores)
            }
            
            logger.info("简化评估完成")
            return results
            
        except Exception as e:
            logger.error(f"简化评估失败: {e}")
            return {}

    def run_evaluation(self, evaluation_data: Dict[str, List]) -> Dict[str, float]:
        """运行评估"""
        try:
            logger.info(f"开始RAGAS评估...")
            logger.info(f"评估数据统计: 问题数={len(evaluation_data.get('question', []))}")
            
            # 过滤掉空答案和空上下文的数据
            filtered_data = {
                "question": [],
                "contexts": [],
                "answer": [],
                "ground_truth": []
            }
            
            for i in range(len(evaluation_data.get("question", []))):
                question = evaluation_data["question"][i]
                answer = evaluation_data["answer"][i]
                contexts = evaluation_data["contexts"][i]
                ground_truth = evaluation_data["ground_truth"][i]
                
                # 过滤条件：问题不为空，答案不为空，上下文不为空
                if (question and answer and contexts and 
                    any(ctx.strip() for ctx in contexts if ctx)):
                    filtered_data["question"].append(question)
                    filtered_data["contexts"].append(contexts)
                    filtered_data["answer"].append(answer)
                    filtered_data["ground_truth"].append(ground_truth)
            
            logger.info(f"过滤后数据统计: 问题数={len(filtered_data['question'])}")
            
            if len(filtered_data["question"]) == 0:
                logger.warning("过滤后没有有效数据，返回空结果")
                return {}
            
            # 执行自定义评估
            import time
            start_time = time.time()
            
            evaluation_results = self._custom_ragas_evaluation(filtered_data)
            evaluation_time = time.time() - start_time
            logger.info(f"评估完成，耗时: {evaluation_time:.2f}秒")
            
            return evaluation_results
            
        except Exception as e:
            logger.error(f"RAGAS评估失败: {e}")
            import traceback
            traceback.print_exc()
            return {}

def main():
    """主函数"""
    print("简化RAGAS评估测试")
    print("=" * 60)
    
    # 创建测试数据
    test_data = {
        "question": [
            "什么是人工智能？",
            "机器学习的应用领域有哪些？"
        ],
        "contexts": [
            ["人工智能是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。"],
            ["机器学习在医疗、金融、交通、教育等领域有广泛应用。"]
        ],
        "answer": [
            "人工智能是计算机科学的一个分支，致力于创建智能系统。",
            "机器学习在医疗、金融、交通、教育等领域有广泛应用。"
        ],
        "ground_truth": [
            "人工智能是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。",
            "机器学习在医疗、金融、交通、教育等领域有广泛应用。"
        ]
    }
    
    # 创建评估器
    evaluator = SimpleRagasEvaluator()
    
    # 运行评估
    results = evaluator.run_evaluation(test_data)
    
    # 打印结果
    print("\n" + "=" * 60)
    print("评估结果")
    print("=" * 60)
    
    for metric, score in results.items():
        print(f"{metric:25}: {score:.4f}")
    
    print("=" * 60)

if __name__ == "__main__":
    main()


