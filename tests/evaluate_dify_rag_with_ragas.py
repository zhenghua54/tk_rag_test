#!/usr/bin/env python3
"""
Dify平台RAG系统在RagBench数据集上的RAGAS评估脚本

测试流程：
1. 从本地ragbench数据集加载数据
2. 使用Dify平台API对query进行检索和生成
3. 用RAGAS框架评估生成效果
"""

import os
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Set, Any
import asyncio
import threading
import time
from datetime import datetime
import logging
import requests
import aiohttp

# 初始化日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# RAGAS相关导入
try:
    from datasets import Dataset, load_dataset
    from ragas import evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    )
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from langchain_openai import ChatOpenAI
    from langchain_community.embeddings import HuggingFaceEmbeddings
except ImportError as e:
    print(f"请先安装RAGAS: pip install ragas datasets langchain-openai langchain-community")
    exit(1)

# 项目相关导入
import sys
sys.path.append('.')
from config.global_config import GlobalConfig

class DifyRagasEvaluator:
    """Dify平台RAG系统RAGAS评估器"""
    
    # 单例模式 - 避免重复创建LLM和embedding实例
    _llm_instance = None
    _embeddings_instance = None
    _lock = threading.Lock()
    
    # Dify API配置
    DIFY_API_KEYS = {
        "delucionqa": "app-m0biWuFrhVjiPPHGLrLxB0TY",
        "hagrid": "app-2cqZVWtdv3vQU0xwiVNdoKVS",
        "msmarco": "app-oYx9Is8g5u3cIKPI1lGFisy7",
        "techqa": "app-HlQof1oQkLMbLE2ryiaglmC3",
        "emanual": "app-eCw9INTLaMi6O2foeSVibfy2",
        "hotpotqa": "app-MI3YAMr3no9G5j2KpNMbX5yl",
        "tatqa": "app-mr7MFpU37QhL2U51TALF8RIP"
    }
    DIFY_API_KEY = None  # 将在运行时根据选择的数据集动态设置
    DIFY_BASE_URL = "http://192.168.31.205"  # 本地Dify实例URL
    DIFY_CHAT_ENDPOINT = "/v1/completion-messages"  # 标准API端点
    
    # 平台限制配置
    RPM_LIMIT = 1000  # 每分钟请求数限制
    TPM_LIMIT = 5000000  # 每分钟token数限制
    BATCH_SIZE = 20  # 每批处理样本数（基于RPM限制调整）
    BATCH_DELAY = 1.2  # 批次间延迟（秒），确保不超过RPM限制
    
    def __init__(self):
        """初始化评估器"""
        self.results_path = Path("evaluation_results")
        self.results_path.mkdir(exist_ok=True)
        
        # 本地数据集路径
        self.datasets_path = Path("data/ragbench")
        
        # 支持的数据集列表（基于本地文件夹）
        self.available_datasets = [
            "covidqa", "cuad", "delucionqa", "emanual", "expertqa",
            "finqa", "hagrid", "hotpotqa", "msmarco", "pubmedqa", 
            "tatqa", "techqa"
        ]
        
        # 限流计数器
        self._request_count = 0
        self._token_count = 0
        self._last_reset_time = time.time()
        
        # 系统提示词(不再需要在脚本中定义，应在Dify平台配置)
        # self.system_prompt = """..."""
        
        logger.info("Dify RAGAS评估器初始化完成")
    
    def load_ragbench_subset(self, task_name: str = "covidqa", split: str = "test", sample_size: int = 10) -> Dataset:
        """
        从本地加载ragbench中的一个子数据集
        
        Args:
            task_name: 任务名称
            split: 数据集分割 (train, validation, test)
            sample_size: 样本数量
            
        Returns:
            加载的数据集
        """
        try:
            # 构建数据集路径
            dataset_path = self.datasets_path / task_name
            if not dataset_path.exists():
                raise FileNotFoundError(f"数据集路径不存在: {dataset_path}")
            
            # 查找对应的parquet文件
            parquet_file = dataset_path / f"{split}-00000-of-00001.parquet"
            if not parquet_file.exists():
                raise FileNotFoundError(f"数据集文件不存在: {parquet_file}")
            
            # 读取parquet文件
            df = pd.read_parquet(parquet_file)
            logger.info(f"成功加载 {len(df)} 个样本 from {task_name}/{split}")
            
            # 限制样本数量
            if sample_size and sample_size < len(df):
                df = df.head(sample_size)
                logger.info(f"限制样本数量为: {sample_size}")
            
            # 转换为Dataset格式
            dataset_dict = {
                "question": df["question"].tolist(),
                "documents": df["documents"].tolist(),
                "response": df["response"].tolist(),
                "id": df["id"].tolist() if "id" in df.columns else [f"{task_name}_{i}" for i in range(len(df))]
            }
            
            # 确保documents字段是正确的格式
            for i, docs in enumerate(dataset_dict["documents"]):
                if isinstance(docs, str):
                    dataset_dict["documents"][i] = [docs]
                elif hasattr(docs, '__iter__') and not isinstance(docs, str):
                    # 处理numpy数组、pandas Series等可迭代对象
                    try:
                        dataset_dict["documents"][i] = list(docs)
                    except:
                        dataset_dict["documents"][i] = [str(docs)]
                else:
                    dataset_dict["documents"][i] = [str(docs)] if docs else []
            
            dataset = Dataset.from_dict(dataset_dict)
            logger.info(f"成功创建Dataset，包含 {len(dataset)} 个样本")
            return dataset

        except Exception as e:
            logger.error(f"加载数据集失败: {e}")
            raise

    def get_ragas_llm(self):
        """
        配置RAGAS所需的LLM（单例模式）
        
        Returns:
            配置好的LLM
        """
        if self._llm_instance is None:
            with self._lock:
                if self._llm_instance is None:
                    try:
                        api_key = os.getenv("OPENAI_API_KEY", "sk-qMm27ouwcmuadceBPLufcntEaB5fgtxJWc6Wn7LHkfxjfGu2")
                        base_url = os.getenv("OPENAI_BASE_URL", "https://api.fe8.cn/v1")
                        model=os.getenv("OPENAI_DIFY_MODEL", "Qwen/Qwen2.5-72B-Instruct")

                        # 创建带有系统提示词的LLM实例，添加更智能的限流和重试机制
                        llm = LangchainLLMWrapper(
                            ChatOpenAI(
                                model=model,
                                api_key=api_key,
                                base_url=base_url,
                                temperature=0,
                                max_tokens=1000,
                                request_timeout=300,  # 进一步增加超时时间
                                max_retries=10,  # 增加重试次数
                            )
                        )
                        self._llm_instance = llm
                        logger.info("成功配置RAGAS LLM（单例模式）")
                    except Exception as e:
                        logger.warning(f"无法配置LLM，使用默认设置: {e}")
                        self._llm_instance = None
        
        return self._llm_instance
    
    def get_ragas_embeddings(self):
        """
        配置RAGAS所需的本地embedding模型（单例模式）
        
        Returns:
            配置好的embedding模型
        """
        if self._embeddings_instance is None:
            with self._lock:
                if self._embeddings_instance is None:
                    try:
                        # 使用本地的bge-m3模型
                        embedding_model = HuggingFaceEmbeddings(
                            model_name=GlobalConfig.MODEL_PATHS.get("embedding"),
                            model_kwargs={'device': GlobalConfig.DEVICE},
                            encode_kwargs={'normalize_embeddings': True}
                        )
                        
                        # 包装为RAGAS兼容的格式
                        ragas_embeddings = LangchainEmbeddingsWrapper(embedding_model)
                        self._embeddings_instance = ragas_embeddings
                        logger.info("成功配置RAGAS本地embedding模型（单例模式）")
                    except Exception as e:
                        logger.warning(f"无法配置本地embedding模型，使用默认设置: {e}")
                        self._embeddings_instance = None
        
        return self._embeddings_instance
    
    def _check_rate_limit(self):
        """检查并管理限流"""
        current_time = time.time()
        
        # 每分钟重置计数器
        if current_time - self._last_reset_time >= 60:
            self._request_count = 0
            self._token_count = 0
            self._last_reset_time = current_time
        
        # 检查RPM限制
        if self._request_count >= self.RPM_LIMIT:
            wait_time = 60 - (current_time - self._last_reset_time)
            if wait_time > 0:
                logger.warning(f"RPM限制达到，等待 {wait_time:.1f} 秒...")
                time.sleep(wait_time)
                self._request_count = 0
                self._token_count = 0
                self._last_reset_time = time.time()
        
        # 检查TPM限制（粗略估算）
        if self._token_count >= self.TPM_LIMIT:
            wait_time = 60 - (current_time - self._last_reset_time)
            if wait_time > 0:
                logger.warning(f"TPM限制达到，等待 {wait_time:.1f} 秒...")
                time.sleep(wait_time)
                self._request_count = 0
                self._token_count = 0
                self._last_reset_time = time.time()
    
    def _update_rate_limit_counters(self, estimated_tokens=1000):
        """更新限流计数器"""
        self._request_count += 1
        self._token_count += estimated_tokens
    
    async def call_dify_api(self, question: str, user_id: str) -> Dict[str, Any]:
        """
        调用Dify API进行RAG问答(只发送问题)
        
        Args:
            question: 用户问题
            user_id: 用户ID
            
        Returns:
            Dify API响应结果
        """
        try:
            # 检查限流
            self._check_rate_limit()
            
            # 构建请求URL
            url = f"{self.DIFY_BASE_URL}{self.DIFY_CHAT_ENDPOINT}"
            
            # 构建请求头
            headers = {
                "Authorization": f"Bearer {self.DIFY_API_KEY}",
                "Content-Type": "application/json"
            }
            
            # 构建请求体(只包含query)
            payload = {
                "inputs": {"query": question},
                "response_mode": "blocking",  # 使用阻塞模式获取完整响应
                "user": user_id
            }
            
            # 发送请求
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # 更新限流计数器
                        self._update_rate_limit_counters()
                        
                        logger.info(f"Dify API调用成功，响应状态: {response.status}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"Dify API调用失败: {response.status}, {error_text}")
                        return {"error": f"API调用失败: {response.status}", "details": error_text}
                        
        except Exception as e:
            logger.error(f"Dify API调用异常: {e}")
            return {"error": f"API调用异常: {str(e)}"}
    
    async def generate_answers_with_dify(self, dataset: Dataset, task_name: str | None = None) -> Dict[str, List]:
        """
        使用Dify平台生成答案
        
        Args:
            dataset: 输入数据集
            task_name: 任务名称
            
        Returns:
            RAGAS格式的评估数据
        """
        results = {
            "question": [],
            "contexts": [],
            "answer": [],
            "ground_truth": [],
            "query_id": [],
            "retrieved_docs": []  # 系统实际检索到的文档列表
        }
        
        for i, example in enumerate(dataset):
            try:
                question = example["question"]
                documents = example["documents"]  # list of strings
                ground_truth = example["response"]
                query_id = example.get("id", f"query_{i+1}")
                
                logger.info(f"处理查询 {i+1}/{len(dataset)}: {question[:100]}...")
                
                # 调用Dify API(不再传递documents)
                user_id = f"ragbench_eval_{task_name}_{i}" if task_name else f"ragbench_eval_{i}"
                dify_result = await self.call_dify_api(question, user_id)
                
                # 检查API调用结果
                if "error" in dify_result:
                    logger.error(f"查询 {i+1} Dify API调用失败: {dify_result['error']}")
                    # 添加失败的占位数据
                    results["question"].append(question)
                    results["contexts"].append(documents if documents else [""])
                    results["answer"].append("")
                    results["ground_truth"].append(ground_truth)
                    results["query_id"].append(query_id)
                    results["retrieved_docs"].append([])
                    continue
                
                # 提取Dify的响应
                generated_answer = ""
                if "answer" in dify_result:
                    generated_answer = dify_result["answer"]
                elif "message" in dify_result:
                    generated_answer = dify_result["message"]
                else:
                    logger.warning(f"查询 {i+1} 无法从Dify响应中提取答案")
                    generated_answer = ""
                
                # 调试信息：打印生成的答案
                logger.info(f"查询 {i+1} 生成的答案长度: {len(generated_answer)}")
                if len(generated_answer) == 0:
                    logger.warning(f"查询 {i+1} 生成的答案为空！")
                else:
                    logger.info(f"查询 {i+1} 生成的答案前100字符: {generated_answer[:100]}...")
                
                # 提取检索上下文（从Dify响应中获取）
                retrieved_contexts = []
                retrieved_docs = []
                
                # 尝试从Dify响应中提取检索到的文档信息
                if "metadata" in dify_result and "retriever_resources" in dify_result["metadata"]:
                    retriever_resources = dify_result["metadata"]["retriever_resources"]
                    if retriever_resources:
                        for resource in retriever_resources:
                            content = resource.get("content", "")
                            retrieved_contexts.append(content)
                            retrieved_docs.append({
                                "content": content,
                                "source": resource.get("dataset_name", "dify"),
                                "score": resource.get("score", 0.0)
                            })
                
                # 如果没有检索信息，使用一个空字符串作为上下文，以避免RAGAS出错
                if not retrieved_contexts:
                    retrieved_contexts = [""]
                    retrieved_docs = [{"content": "No documents retrieved", "source": "Dify"}]
                
                # 处理ground_truth格式 - RAGAS期望是字符串
                if isinstance(ground_truth, str):
                    ground_truth_str = ground_truth
                elif isinstance(ground_truth, list):
                    if ground_truth and isinstance(ground_truth[0], list):
                        ground_truth_str = ground_truth[0][0] if ground_truth[0] else ""
                    else:
                        ground_truth_str = ground_truth[0] if ground_truth else ""
                else:
                    ground_truth_str = str(ground_truth)
                
                results["question"].append(question)
                results["contexts"].append(retrieved_contexts)
                results["answer"].append(generated_answer)
                results["ground_truth"].append(ground_truth_str)
                results["query_id"].append(query_id)
                results["retrieved_docs"].append(retrieved_docs)
                    
            except Exception as e:
                logger.error(f"Dify评估失败: {e}")
                # 添加失败的占位数据
                query_id = example.get("id", f"query_{i+1}") if 'example' in locals() else f"query_{i+1}"
                results["question"].append(question if 'question' in locals() else "")
                results["contexts"].append(documents if documents else [""])
                results["answer"].append("")
                results["ground_truth"].append(ground_truth_str if 'ground_truth_str' in locals() else "")
                results["query_id"].append(query_id)
                results["retrieved_docs"].append([])
            
            # # 在每个请求后添加延迟，以避免触发后端LLM的频率限制
            # if i < len(dataset) - 1:
            #     logger.info("等待3秒以避免频率限制...")
            #     await asyncio.sleep(3)
        
        return results

    async def run_ragas_evaluation(self, evaluation_data: Dict[str, List]) -> Dict[str, Any]:
        """
        运行RAGAS评估
        
        Args:
            evaluation_data: 评估数据
            
        Returns:
            RAGAS评估结果，包含整体分数和详细分数
        """
        try:
            # 检查评估数据质量
            logger.info(f"评估数据统计: 问题数={len(evaluation_data.get('question', []))}, "
                       f"答案数={len(evaluation_data.get('answer', []))}, "
                       f"上下文数={len(evaluation_data.get('contexts', []))}")
            
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
                
                logger.debug(f"处理样本 {i+1}: 问题长度={len(question)}, 答案长度={len(answer)}, 上下文数量={len(contexts)}")
                
                # 过滤条件：问题不为空，答案不为空，上下文不为空
                if (question and answer and contexts and 
                    any(ctx.strip() for ctx in contexts if ctx)):
                    
                    # 处理ground_truth格式 - 确保是字符串
                    if isinstance(ground_truth, str):
                        ground_truth_str = ground_truth
                    elif isinstance(ground_truth, list):
                        if ground_truth and isinstance(ground_truth[0], list):
                            ground_truth_str = ground_truth[0][0] if ground_truth[0] else ""
                        else:
                            ground_truth_str = ground_truth[0] if ground_truth else ""
                    else:
                        ground_truth_str = str(ground_truth)
                    
                    filtered_data["question"].append(question)
                    filtered_data["contexts"].append(contexts)
                    filtered_data["answer"].append(answer)
                    filtered_data["ground_truth"].append(ground_truth_str)
                    logger.debug(f"样本 {i+1} 通过过滤")
                else:
                    logger.debug(f"样本 {i+1} 被过滤掉: 问题={bool(question)}, 答案={bool(answer)}, 上下文={bool(contexts and any(ctx.strip() for ctx in contexts if ctx))}")
            
            logger.info(f"过滤后数据统计: 问题数={len(filtered_data['question'])}, "
                       f"答案数={len(filtered_data['answer'])}, "
                       f"上下文数={len(filtered_data['contexts'])}")
            
            if len(filtered_data["question"]) == 0:
                logger.warning("过滤后没有有效数据，返回空结果")
                return {"overall_scores": {}, "detailed_scores": {}}
            
            # 创建Dataset对象
            dataset = Dataset.from_dict(filtered_data)
            logger.info(f"创建的Dataset信息: {dataset}")
            logger.info(f"Dataset列名: {dataset.column_names}")
            logger.info(f"Dataset样本数: {len(dataset)}")
            
            # 配置RAGAS使用的LLM和embedding模型
            llm = self.get_ragas_llm()
            embeddings = self.get_ragas_embeddings()
            
            # 定义评估指标并配置LLM和embedding
            from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
            metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
            for metric in metrics:
                if llm and hasattr(metric, 'llm'):
                    metric.llm = llm
                if embeddings and hasattr(metric, 'embeddings'):
                    metric.embeddings = embeddings
            
            # 执行评估
            import time
            start_time = time.time()
            
            # 详细说明RAGAS指标计算过程
            logger.info("=== RAGAS指标计算说明 ===")
            logger.info("1. Faithfulness: 评估生成的答案是否忠实于检索到的上下文")
            logger.info("2. Answer Relevancy: 评估生成的答案是否与问题相关")
            logger.info("3. Context Precision: 评估检索到的上下文是否精确相关")
            logger.info("4. Context Recall: 评估检索到的上下文是否完整覆盖")
            logger.info("RAGAS会对每个样本单独计算指标，然后取平均值")
            
            # 记录每个样本的基本信息（简化版）
            logger.info(f"开始评估 {len(dataset)} 个样本...")
            
            # 智能限流：基于平台限制进行批处理
            logger.info(f"基于平台限制进行智能批处理: RPM={self.RPM_LIMIT}, TPM={self.TPM_LIMIT}")
            logger.info(f"批次大小: {self.BATCH_SIZE}, 批次延迟: {self.BATCH_DELAY}秒")
            
            # 分批处理评估，基于平台限制
            all_results = []
            
            for i in range(0, len(dataset), self.BATCH_SIZE):
                batch_end = min(i + self.BATCH_SIZE, len(dataset))
                batch_dataset = dataset.select(range(i, batch_end))
                
                logger.info(f"处理批次 {i//self.BATCH_SIZE + 1}/{(len(dataset) + self.BATCH_SIZE - 1)//self.BATCH_SIZE}: 样本 {i+1}-{batch_end}")
                
                # 检查限流
                self._check_rate_limit()
                
                try:
                    batch_results = evaluate(batch_dataset, metrics=metrics)
                    all_results.append(batch_results)
                    
                    # 更新限流计数器（估算每个样本约1000 tokens）
                    estimated_tokens = len(batch_dataset) * 1000
                    self._update_rate_limit_counters(estimated_tokens)
                    
                    # 批次间添加延迟，确保不超过RPM限制
                    if batch_end < len(dataset):
                        logger.info(f"批次间等待 {self.BATCH_DELAY} 秒...")
                        await asyncio.sleep(self.BATCH_DELAY)
                        
                except Exception as e:
                    logger.error(f"批次 {i//self.BATCH_SIZE + 1} 评估失败: {e}")
                    # 继续处理下一批
                    continue
            
            # 合并所有批次的结果
            if all_results:
                # 这里需要根据RAGAS的结果格式来合并
                results = all_results[0]  # 暂时使用第一个批次的结果
                logger.info(f"成功处理 {len(all_results)} 个批次")
            else:
                logger.error("所有批次评估都失败了")
                return {"overall_scores": {}, "detailed_scores": {}}
            
            evaluation_time = time.time() - start_time
            logger.info(f"RAGAS评估完成，耗时: {evaluation_time:.2f}秒")
            
            # 转换结果格式
            evaluation_results = {}
            detailed_scores = {}  # 存储每个query的详细分数
            
            # 详细分析RAGAS结果对象
            if hasattr(results, '__dict__'):
                # 检查是否有scores属性
                if hasattr(results, 'scores'):
                    scores = results.scores
                    if isinstance(scores, dict):
                        for key, value in scores.items():
                            # 处理列表类型的情况 - 这是每个query的分数
                            if isinstance(value, list):
                                # 存储详细分数
                                detailed_scores[key] = value
                                # 计算平均值
                                if value and all(isinstance(v, (int, float)) for v in value):
                                    avg_score = float(sum(value) / len(value))
                                    evaluation_results[key] = avg_score
                                else:
                                    logger.warning(f"跳过非数值列表: {key}")
                            elif isinstance(value, (int, float)):
                                evaluation_results[key] = float(value)
                            else:
                                logger.warning(f"跳过非数值类型: {key} = {type(value)}")
                
                # 检查是否有_repr_dict属性
                if hasattr(results, '_repr_dict'):
                    repr_dict = results._repr_dict
                    for key, value in repr_dict.items():
                        if isinstance(value, (int, float)):
                            evaluation_results[key] = float(value)
                        elif isinstance(value, list):
                            # 存储详细分数
                            detailed_scores[key] = value
                            # 计算平均值
                            if value and all(isinstance(v, (int, float)) for v in value):
                                avg_score = float(sum(value) / len(value))
                                evaluation_results[key] = avg_score
                            else:
                                logger.warning(f"跳过非数值列表: {key}")
            
            # 尝试不同的结果格式
            if hasattr(results, 'items'):
                # 如果是字典格式
                for metric_name, score in results.items():
                    # 处理列表类型的情况
                    if isinstance(score, list):
                        # 存储详细分数
                        detailed_scores[metric_name] = score
                        # 计算平均值
                        if score and all(isinstance(v, (int, float)) for v in score):
                            avg_score = float(sum(score) / len(score))
                            evaluation_results[metric_name] = avg_score
                        else:
                            logger.warning(f"跳过非数值列表: {metric_name}")
                    elif isinstance(score, (int, float)):
                        evaluation_results[metric_name] = float(score)
                    else:
                        logger.warning(f"跳过非数值类型: {metric_name} = {type(score)}")
            elif hasattr(results, '__dict__'):
                # 如果是对象格式，尝试获取属性
                possible_attributes = ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall', 
                                     'faithfulness_score', 'answer_relevancy_score', 'context_precision_score', 'context_recall_score']
                
                for attr in possible_attributes:
                    if hasattr(results, attr):
                        score = getattr(results, attr)
                        if score is not None:
                            # 处理列表类型的情况
                            if isinstance(score, list):
                                # 存储详细分数
                                detailed_scores[attr.replace('_score', '')] = score
                                # 计算平均值
                                if score and all(isinstance(v, (int, float)) for v in score):
                                    avg_score = float(sum(score) / len(score))
                                    evaluation_results[attr.replace('_score', '')] = avg_score
                                else:
                                    logger.warning(f"跳过非数值列表: {attr}")
                            elif isinstance(score, (int, float)):
                                evaluation_results[attr.replace('_score', '')] = float(score)
                            else:
                                logger.warning(f"跳过非数值类型: {attr} = {type(score)}")
                
                # 如果没有找到任何分数，尝试其他方法
                if not evaluation_results:
                    # 尝试调用to_dict()方法
                    if hasattr(results, 'to_dict'):
                        try:
                            results_dict = results.to_dict()
                            for key, value in results_dict.items():
                                if isinstance(value, (int, float)):
                                    evaluation_results[key] = float(value)
                                elif isinstance(value, list):
                                    # 存储详细分数
                                    detailed_scores[key] = value
                                    # 计算平均值
                                    if value and all(isinstance(v, (int, float)) for v in value):
                                        avg_score = float(sum(value) / len(value))
                                        evaluation_results[key] = avg_score
                                    else:
                                        logger.warning(f"跳过非数值列表: {key}")
                        except Exception as e:
                            logger.error(f"调用to_dict()失败: {e}")
                    
                    # 尝试调用to_pandas()方法
                    if hasattr(results, 'to_pandas'):
                        try:
                            results_df = results.to_pandas()
                            
                            # 详细查看DataFrame内容
                            for column in results_df.columns:
                                if results_df[column].dtype in ['float64', 'int64']:
                                    # 计算所有样本的平均得分，而不是只取第一个
                                    scores = results_df[column].tolist()
                                    detailed_scores[column] = scores
                                    avg_score = sum(scores) / len(scores) if scores else 0.0
                                    evaluation_results[column] = float(avg_score)
                        except Exception as e:
                            logger.error(f"调用to_pandas()失败: {e}")
            else:
                logger.error(f"未知的RAGAS结果格式: {type(results)}")
                return {"overall_scores": {}, "detailed_scores": {}}
            
            # 记录整体指标分数
            if evaluation_results:
                logger.info("=== RAGAS整体指标分数 ===")
                for metric, score in evaluation_results.items():
                    logger.info(f"{metric}: {score:.4f}")
            
            # 记录各个query的详细分数
            if detailed_scores:
                logger.info("=== 各个query的详细分数 ===")
                # 获取所有指标名称
                metrics = ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']
                
                # 获取最大长度（用于对齐）
                max_length = max(len(detailed_scores.get(metric, [])) for metric in metrics)
                
                for i in range(max_length):
                    query_id = f"query_{i+1}"
                    faithfulness = detailed_scores.get('faithfulness', [0.0])[i] if i < len(detailed_scores.get('faithfulness', [])) else 0.0
                    answer_relevancy = detailed_scores.get('answer_relevancy', [0.0])[i] if i < len(detailed_scores.get('answer_relevancy', [])) else 0.0
                    context_precision = detailed_scores.get('context_precision', [0.0])[i] if i < len(detailed_scores.get('context_precision', [])) else 0.0
                    context_recall = detailed_scores.get('context_recall', [0.0])[i] if i < len(detailed_scores.get('context_recall', [])) else 0.0
                    
                    logger.info(f"【{query_id}：faithfulness: {faithfulness:.4f}, answer_relevancy: {answer_relevancy:.4f}, context_precision: {context_precision:.4f}, context_recall: {context_recall:.4f}】")
            
            # 返回包含整体分数和详细分数的结果
            return {
                "overall_scores": evaluation_results,
                "detailed_scores": detailed_scores
            }
            
        except Exception as e:
            logger.error(f"RAGAS评估失败: {e}")
            import traceback
            traceback.print_exc()
            return {"overall_scores": {}, "detailed_scores": {}}
    
    async def run_complete_evaluation(self, task_name: str, split: str = "test", sample_size: int = 10):
        """
        运行完整的评估流程
        
        Args:
            task_name: 任务名称
            split: 数据集分割 (train, validation, test)
            sample_size: 样本数量
        """
        logger.info(f"开始完整评估流程: {task_name}")

        # 根据任务名称动态设置API密钥
        api_key = self.DIFY_API_KEYS.get(task_name)
        if not api_key:
            logger.error(f"未找到任务 '{task_name}' 对应的API密钥，请在 DIFY_API_KEYS 字典中配置。")
            return
        self.DIFY_API_KEY = api_key
        logger.info(f"任务 '{task_name}' 将使用API密钥: ...{self.DIFY_API_KEY[-4:]}")
        
        try:
            # 1. 加载本地ragbench子任务数据
            print("步骤1: 加载本地ragbench子任务数据...")
            dataset = self.load_ragbench_subset(task_name, split, sample_size)
            
            # 2. 使用Dify平台生成答案
            print("步骤2: 使用Dify平台生成答案...")
            evaluation_data = await self.generate_answers_with_dify(dataset, task_name)
            
            # 3. 运行RAGAS评估
            print("步骤3: 运行RAGAS评估...")
            ragas_results = await self.run_ragas_evaluation(evaluation_data)
            
            # 4. 保存和展示结果
            results = {
                "task_name": task_name,
                "split": split,
                "sample_size": len(evaluation_data["question"]),
                "timestamp": datetime.now().isoformat(),
                "ragas_metrics": ragas_results.get("overall_scores", {}),
                "summary": {
                    "average_score": sum(ragas_results.get("overall_scores", {}).values()) / len(ragas_results.get("overall_scores", {})) if ragas_results.get("overall_scores", {}) else 0,
                    "best_metric": max(ragas_results.get("overall_scores", {}).keys(), key=lambda k: ragas_results.get("overall_scores", {})[k]) if ragas_results.get("overall_scores", {}) else None,
                    "worst_metric": min(ragas_results.get("overall_scores", {}).keys(), key=lambda k: ragas_results.get("overall_scores", {})[k]) if ragas_results.get("overall_scores", {}) else None
                }
            }
            
            self.save_results(task_name, results)
            self.print_results(results)
            
            # 5. 导出详细结果到xlsx文件
            print("步骤4: 导出详细结果到xlsx文件...")
            self.export_detailed_results_to_xlsx(task_name, dataset, evaluation_data, ragas_results)
            
        except Exception as e:
            logger.error(f"完整评估流程失败: {e}")
            import traceback
            traceback.print_exc()
    
    def save_results(self, task_name: str, results: Dict[str, Any]):
        """保存评估结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dify_ragbench_ragas_evaluation_{task_name}_{timestamp}.json"
        filepath = self.results_path / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"评估结果已保存到: {filepath}")
    
    def print_results(self, results: Dict[str, Any]):
        """打印评估结果"""
        print("\n" + "="*70)
        print("Dify平台RAG系统在RagBench数据集上的RAGAS评估结果")
        print("="*70)
        print(f"任务名称: {results['task_name']}")
        print(f"数据集分割: {results['split']}")
        print(f"评估样本数: {results['sample_size']}")
        print(f"评估时间: {results['timestamp']}")
        print("\nRAGAS指标得分:")
        print("-"*50)
        
        # 修复：ragas_metrics现在直接是overall_scores
        ragas_metrics = results.get('ragas_metrics', {})
        if isinstance(ragas_metrics, dict) and 'overall_scores' in ragas_metrics:
            # 如果是新的格式（包含overall_scores）
            for metric, score in ragas_metrics['overall_scores'].items():
                print(f"{metric:25}: {score:.4f}")
        else:
            # 如果是直接是overall_scores的格式
            for metric, score in ragas_metrics.items():
                print(f"{metric:25}: {score:.4f}")
        
        print("-"*50)
        print(f"平均得分: {results['summary']['average_score']:.4f}")
        print(f"最佳指标: {results['summary']['best_metric']}")
        print(f"最差指标: {results['summary']['worst_metric']}")
        print("="*70)

    def export_detailed_results_to_xlsx(self, task_name: str, dataset: Dataset, evaluation_data: Dict[str, List], ragas_results: Dict[str, Any]):
        """
        导出详细结果到xlsx文件
        
        Args:
            task_name: 任务名称
            dataset: 原始数据集
            evaluation_data: 评估数据
            ragas_results: RAGAS评估结果，包含overall_scores和detailed_scores
        """
        try:
            # 获取详细分数
            detailed_scores = ragas_results.get("detailed_scores", {})
            
            # 准备导出数据
            export_data = []
            
            for i in range(len(evaluation_data["question"])):
                # 使用数据集的query_id字段
                query_id = evaluation_data.get("query_id", [])[i] if i < len(evaluation_data.get("query_id", [])) else f"query_{i+1}"
                query = evaluation_data["question"][i]
                
                # 检索到的document列表（用于RAGAS评估的上下文）
                retrieved_contexts = evaluation_data["contexts"][i]
                retrieved_contexts_str = "\n".join(retrieved_contexts) if retrieved_contexts else ""
                
                # 系统实际检索到的文档列表（包含更多信息）
                retrieved_docs = evaluation_data.get("retrieved_docs", [])[i] if i < len(evaluation_data.get("retrieved_docs", [])) else []
                retrieved_docs_str = ""
                if retrieved_docs:
                    # 格式化检索到的文档信息
                    doc_info_list = []
                    for j, doc in enumerate(retrieved_docs):
                        if isinstance(doc, dict):
                            content = doc.get('content', '')
                            source = doc.get('source', 'unknown')
                            score = doc.get('score', '')
                            doc_info = f"文档{j+1} (来源: {source}"
                            if score:
                                doc_info += f", 分数: {score}"
                            doc_info += f"): {content}"
                            doc_info_list.append(doc_info)
                        else:
                            doc_info_list.append(f"文档{j+1}: {str(doc)}")
                    retrieved_docs_str = "\n".join(doc_info_list)
                
                # 实际数据集对应的document
                original_docs = dataset[i]["documents"] if "documents" in dataset[i] else []
                original_docs_str = "\n".join(original_docs) if original_docs else ""
                
                # 四个指标分数
                faithfulness = detailed_scores.get('faithfulness', [0.0])[i] if i < len(detailed_scores.get('faithfulness', [])) else 0.0
                answer_relevancy = detailed_scores.get('answer_relevancy', [0.0])[i] if i < len(detailed_scores.get('answer_relevancy', [])) else 0.0
                context_precision = detailed_scores.get('context_precision', [0.0])[i] if i < len(detailed_scores.get('context_precision', [])) else 0.0
                context_recall = detailed_scores.get('context_recall', [0.0])[i] if i < len(detailed_scores.get('context_recall', [])) else 0.0
                
                # 获取系统生成的回答
                generated_answer = evaluation_data["answer"][i]
                
                # 获取数据集的标准答案
                ground_truth_answer = evaluation_data["ground_truth"][i]
                
                # 添加到导出数据
                export_data.append({
                    "query_id": query_id,
                    "query": query,
                    "系统生成的回答": generated_answer,
                    "数据集标准答案": ground_truth_answer,
                    "检索到的document列表": retrieved_contexts_str,
                    "系统实际检索到的文档列表": retrieved_docs_str,
                    "faithfulness": faithfulness,
                    "answer_relevancy": answer_relevancy,
                    "context_precision": context_precision,
                    "context_recall": context_recall,
                    "实际数据集对应的document": original_docs_str
                })
            
            # 创建DataFrame
            df = pd.DataFrame(export_data)
            
            # 保存到xlsx文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dify_ragbench_detailed_results_{task_name}_{timestamp}.xlsx"
            filepath = self.results_path / filename
            
            # 使用openpyxl引擎保存xlsx文件
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='详细评估结果', index=False)
                
                # 调整列宽
                worksheet = writer.sheets['详细评估结果']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)  # 最大宽度50
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            logger.info(f"详细结果已导出到: {filepath}")
            print(f"详细结果已导出到: {filepath}")
            
        except Exception as e:
            logger.error(f"导出xlsx文件失败: {e}")
            import traceback
            traceback.print_exc()

async def main():
    """主函数"""
    evaluator = DifyRagasEvaluator()
    
    print("Dify平台RAG系统在RagBench数据集上的RAGAS评估工具")
    print("="*60)
    
    # 显示可用数据集
    print("可用数据集:")
    for i, dataset in enumerate(evaluator.available_datasets, 1):
        print(f"{i:2d}. {dataset}")
    
    # 选择数据集
    while True:
        try:
            choice = input(f"\n请选择数据集 (1-{len(evaluator.available_datasets)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(evaluator.available_datasets):
                selected_dataset = evaluator.available_datasets[idx]
                break
            else:
                print("无效选择，请重试")
        except ValueError:
            print("请输入有效数字")
    

    # 选择数据集分割
    splits = ["train", "validation", "test"]
    print("\n可用数据集分割:")
    for i, split in enumerate(splits, 1):
        print(f"{i:2d}. {split}")
    
    while True:
        try:
            split_choice = input(f"\n请选择数据集分割 (1-{len(splits)}): ").strip()
            split_idx = int(split_choice) - 1
            if 0 <= split_idx < len(splits):
                selected_split = splits[split_idx]
                break
            else:
                print("无效选择，请重试")
        except ValueError:
            print("请输入有效数字")
    
    # 设置样本数量
    while True:
        try:
            sample_size = input("评估样本数量 (默认10): ").strip()
            if not sample_size:
                sample_size = 10
            else:
                sample_size = int(sample_size)
            break
        except ValueError:
            print("请输入有效数字")
    
    print(f"\n开始评估 {selected_dataset} 数据集 ({selected_split} 分割)...")
    print("这将包括:")
    print("1. 加载本地ragbench子任务数据")
    print("2. 使用Dify平台生成答案")
    print("3. 用RAGAS评估效果")
    
    confirm = input("\n确认开始? (y/N): ").strip().lower()
    if confirm == 'y':
        await evaluator.run_complete_evaluation(selected_dataset, selected_split, sample_size)
    else:
        print("已取消评估")

if __name__ == "__main__":
    asyncio.run(main())
