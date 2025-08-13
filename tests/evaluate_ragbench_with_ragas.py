#!/usr/bin/env python3
"""
RagBench数据集在TK-RAG系统上的RAGAS评估脚本

测试流程：
1. 从本地ragbench数据集加载数据
2. 使用TK-RAG系统对query进行检索和生成
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
from tqdm import tqdm

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
    from tqdm import tqdm
except ImportError as e:
    print(f"请先安装RAGAS和tqdm: pip install ragas datasets langchain-openai langchain-community tqdm")
    exit(1)

# 项目相关导入
import sys
sys.path.append('.')
from config.global_config import GlobalConfig
from core.rag.llm_generator import RAGGenerator
from utils.log_utils import logger

class RagBenchRagasEvaluator:
    """RagBench数据集RAGAS评估器"""
    
    # 单例模式 - 避免重复创建LLM和embedding实例
    _llm_instance = None
    _embeddings_instance = None
    _lock = threading.Lock()
    
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
        
        logger.info("RagBench RAGAS评估器初始化完成")
    
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
                        model=os.getenv("OPENAI_MODEL", "Qwen/Qwen2.5-72B-Instruct")

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
    
    def _merge_batch_results(self, all_results):
        """
        合并多个批次的RAGAS评估结果
        
        Args:
            all_results: 所有批次的评估结果列表
            
        Returns:
            合并后的评估结果
        """
        try:
            if not all_results:
                return None
            
            # 如果只有一个批次，直接返回
            if len(all_results) == 1:
                return all_results[0]
            
            logger.info(f"开始合并 {len(all_results)} 个批次的评估结果...")
            
            # 创建一个新的合并结果对象
            merged_result = all_results[0]  # 以第一个批次为基础
            
            # 如果结果有to_pandas方法，使用DataFrame方式合并
            if hasattr(merged_result, 'to_pandas'):
                try:
                    # 收集所有批次的DataFrame
                    all_dfs = []
                    for i, batch_result in enumerate(all_results):
                        df = batch_result.to_pandas()
                        logger.info(f"批次 {i+1} DataFrame形状: {df.shape}")
                        all_dfs.append(df)
                    
                    # 合并所有DataFrame
                    merged_df = pd.concat(all_dfs, ignore_index=True)
                    logger.info(f"合并后DataFrame形状: {merged_df.shape}")
                    
                    # 创建新的Dataset对象并重新评估以获得正确的结果格式
                    # 这里我们需要重新构建一个结果对象，包含合并后的分数
                    
                    # 创建一个模拟的结果对象
                    class MergedResult:
                        def __init__(self, df):
                            self.df = df
                            self._scores_dict = {}
                            
                            # 提取各个指标的分数列表
                            for column in df.columns:
                                if column in ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']:
                                    self._scores_dict[column] = df[column].tolist()
                        
                        def to_pandas(self):
                            return self.df
                        
                        def __getattr__(self, name):
                            if name in self._scores_dict:
                                return self._scores_dict[name]
                            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
                    
                    merged_result = MergedResult(merged_df)
                    logger.info("成功使用DataFrame方式合并结果")
                    
                except Exception as e:
                    logger.warning(f"DataFrame方式合并失败: {e}，尝试其他方式")
                    merged_result = self._merge_results_by_attributes(all_results)
            
            # 如果结果有scores属性，直接合并scores
            elif hasattr(merged_result, 'scores') or hasattr(merged_result, '_scores_dict'):
                merged_result = self._merge_results_by_attributes(all_results)
            
            else:
                logger.warning("未知的结果格式，使用第一个批次的结果")
                merged_result = all_results[0]
            
            return merged_result
            
        except Exception as e:
            logger.error(f"合并批次结果失败: {e}")
            import traceback
            traceback.print_exc()
            # 如果合并失败，返回第一个批次的结果
            return all_results[0] if all_results else None
    
    def _merge_results_by_attributes(self, all_results):
        """
        通过属性方式合并结果
        """
        try:
            # 创建一个新的合并结果对象
            class MergedResult:
                def __init__(self):
                    self._scores_dict = {}
                    self.scores = {}
                
                def __getattr__(self, name):
                    if name in self._scores_dict:
                        return self._scores_dict[name]
                    elif name in self.scores:
                        return self.scores[name]
                    raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
            
            merged = MergedResult()
            
            # 收集所有批次的分数
            all_scores = {
                'faithfulness': [],
                'answer_relevancy': [],
                'context_precision': [],
                'context_recall': []
            }
            
            for i, batch_result in enumerate(all_results):
                logger.info(f"处理批次 {i+1} 的结果...")
                
                # 尝试不同方式获取分数
                batch_scores = {}
                
                # 方式1: 通过_scores_dict
                if hasattr(batch_result, '_scores_dict'):
                    batch_scores = batch_result._scores_dict
                # 方式2: 通过scores属性
                elif hasattr(batch_result, 'scores'):
                    batch_scores = batch_result.scores
                # 方式3: 通过to_pandas
                elif hasattr(batch_result, 'to_pandas'):
                    try:
                        df = batch_result.to_pandas()
                        for col in df.columns:
                            if col in all_scores:
                                batch_scores[col] = df[col].tolist()
                    except Exception as e:
                        logger.warning(f"to_pandas方式获取分数失败: {e}")
                # 方式4: 直接访问属性
                else:
                    for metric in all_scores.keys():
                        if hasattr(batch_result, metric):
                            score = getattr(batch_result, metric)
                            if isinstance(score, list):
                                batch_scores[metric] = score
                            elif isinstance(score, (int, float)):
                                batch_scores[metric] = [score]
                
                # 合并分数
                for metric, scores in batch_scores.items():
                    if metric in all_scores:
                        if isinstance(scores, list):
                            all_scores[metric].extend(scores)
                            logger.info(f"批次 {i+1} {metric}: 添加了 {len(scores)} 个分数")
                        elif isinstance(scores, (int, float)):
                            all_scores[metric].append(scores)
                            logger.info(f"批次 {i+1} {metric}: 添加了 1 个分数")
            
            # 设置合并后的分数
            merged._scores_dict = all_scores
            merged.scores = all_scores
            
            # 记录合并结果
            for metric, scores in all_scores.items():
                logger.info(f"合并后 {metric}: {len(scores)} 个分数")
            
            return merged
            
        except Exception as e:
            logger.error(f"属性方式合并失败: {e}")
            import traceback
            traceback.print_exc()
            return all_results[0] if all_results else None
    
    async def generate_answers_with_tk_rag(self, dataset: Dataset, task_name: str | None = None) -> Dict[str, List]:
        """
        使用TK-RAG系统生成答案
        
        Args:
            dataset: 输入数据集
            task_name: 任务名称，用于确定使用哪个Milvus集合
            
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
        
        # 初始化RAG生成器，指定对应的集合名称
        collection_name = f"ragbench_{task_name}" if task_name else None
        logger.info(f"使用Milvus集合: {collection_name}")
        
        # 创建RAG生成器并指定集合
        rag_generator = RAGGenerator(collection_name=collection_name)
        
        # 将try-except移到循环外部，确保即使部分查询失败也能继续
        for i, example in enumerate(tqdm(dataset, desc=f"Generating answers for {task_name}")):
            session_id = f"ragbench_eval_{task_name}_{i}"
            request_id = f"ragbench_req_{task_name}_{i}"
            
            try:
                question = example["question"]
                documents = example["documents"]  # list of strings
                ground_truth = example["response"]
                query_id = example.get("id", f"query_{i+1}")  # 使用数据集的id字段，如果没有则生成
                
                logger.info(f"处理查询 {i+1}/{len(dataset)}: {question[:100]}...")
                
                # 使用TK-RAG系统生成答案（同步调用，但在异步函数中）
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    rag_generator.generate_response_without_permission,
                    question,
                    session_id,
                    request_id
                )
                
                # 调试信息：打印生成的答案
                generated_answer = result.get("answer", "")
                logger.info(f"查询 {i+1} 生成的答案长度: {len(generated_answer)}")
                if len(generated_answer) == 0:
                    logger.warning(f"查询 {i+1} 生成的答案为空！")
                else:
                    logger.info(f"查询 {i+1} 生成的答案前100字符: {generated_answer[:100]}...")
                
                # 调试信息：打印检索结果
                sources_count = len(result.get('sources', []))
                logger.info(f"查询 {i+1} 检索到的文档数量: {sources_count}")
                
                # 提取TK-RAG的检索上下文
                retrieved_contexts = []
                retrieved_docs = []  # 系统实际检索到的文档列表
                if 'sources' in result and result['sources']:
                    retrieved_contexts = [source.get('content', '') for source in result['sources']]
                    # 保存系统实际检索到的文档列表（包含更多信息）
                    retrieved_docs = result['sources']
                else:
                    # 如果没有检索到内容，使用原始documents
                    retrieved_contexts = documents if documents else [""]
                    retrieved_docs = [{"content": doc, "source": "original"} for doc in (documents if documents else [])]
                
                # 处理ground_truth格式 - RAGAS期望是字符串
                if isinstance(ground_truth, str):
                    ground_truth_str = ground_truth
                elif isinstance(ground_truth, list):
                    if ground_truth and isinstance(ground_truth[0], list):
                        # 如果是列表的列表，取第一个列表的第一个元素
                        ground_truth_str = ground_truth[0][0] if ground_truth[0] else ""
                    else:
                        # 如果是普通列表，取第一个元素
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
                logger.error(f"处理查询 {i+1} 时发生错误: {e}")
                # 即使失败，也添加占位符，以保持数据对齐
                query_id = example.get("id", f"query_{i+1}")
                results["question"].append(example.get("question", ""))
                results["contexts"].append(example.get("documents", [""]))
                results["answer"].append("") # 失败时答案为空
                results["ground_truth"].append(example.get("response", ""))
                results["query_id"].append(query_id)
                results["retrieved_docs"].append([])
            finally:
                # 关键修复：确保每次评估后清理会话缓存，防止内存泄漏
                rag_generator.end_session(session_id)
                logger.debug(f"已清理会话缓存: {session_id}")
        
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
                            # 如果是列表的列表，取第一个列表的第一个元素
                            ground_truth_str = ground_truth[0][0] if ground_truth[0] else ""
                        else:
                            # 如果是普通列表，取第一个元素
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
            
            # 检查数据样本
            if len(dataset) > 0:
                sample = dataset[0]
                logger.info(f"第一个样本: 问题长度={len(sample.get('question', ''))}, 答案长度={len(sample.get('answer', ''))}, 上下文数量={len(sample.get('contexts', []))}")
            
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
                    
                    # 调试信息：检查批次结果
                    logger.info(f"批次 {i//self.BATCH_SIZE + 1} 评估完成")
                    if hasattr(batch_results, 'to_pandas'):
                        try:
                            batch_df = batch_results.to_pandas()
                            logger.info(f"批次 {i//self.BATCH_SIZE + 1} 结果形状: {batch_df.shape}")
                            logger.info(f"批次 {i//self.BATCH_SIZE + 1} 结果列: {list(batch_df.columns)}")
                            
                            # 显示批次的分数范围
                            for col in ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']:
                                if col in batch_df.columns:
                                    scores = batch_df[col].tolist()
                                    logger.info(f"批次 {i//self.BATCH_SIZE + 1} {col}: 样本数={len(scores)}, 范围=[{min(scores):.4f}, {max(scores):.4f}]")
                        except Exception as e:
                            logger.warning(f"无法检查批次 {i//self.BATCH_SIZE + 1} 的结果: {e}")
                    
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
                results = self._merge_batch_results(all_results)
                logger.info(f"成功处理 {len(all_results)} 个批次，合并了所有结果")
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
                
                # 检查是否有_scores_dict属性
                if hasattr(results, '_scores_dict'):
                    scores_dict = results._scores_dict
                    for key, value in scores_dict.items():
                        # 处理列表类型的情况
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
    
    async def run_complete_evaluation(self, task_name: str = "covidqa", split: str = "test", sample_size: int = 10):
        """
        运行完整的评估流程
        
        Args:
            task_name: 任务名称
            split: 数据集分割 (train, validation, test)
            sample_size: 样本数量
        """
        logger.info(f"开始完整评估流程: {task_name}")
        
        try:
            # 1. 加载本地ragbench子任务数据
            print("步骤1: 加载本地ragbench子任务数据...")
            dataset = self.load_ragbench_subset(task_name, split, sample_size)
            
            # 2. 使用TK-RAG系统生成答案
            print("步骤2: 使用TK-RAG系统生成答案...")
            evaluation_data = await self.generate_answers_with_tk_rag(dataset, task_name)
            
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
        filename = f"ragbench_ragas_evaluation_{task_name}_{timestamp}.json"
        filepath = self.results_path / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"评估结果已保存到: {filepath}")
    
    def print_results(self, results: Dict[str, Any]):
        """打印评估结果"""
        print("\n" + "="*70)
        print("RagBench在TK-RAG系统上的RAGAS评估结果")
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
            filename = f"ragbench_detailed_results_{task_name}_{timestamp}.xlsx"
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
    evaluator = RagBenchRagasEvaluator()
    
    print("RagBench数据集在TK-RAG系统上的RAGAS评估工具")
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
    print("2. 使用TK-RAG系统生成答案")
    print("3. 用RAGAS评估效果")
    
    confirm = input("\n确认开始? (y/N): ").strip().lower()
    if confirm == 'y':
        await evaluator.run_complete_evaluation(selected_dataset, selected_split, sample_size)
    else:
        print("已取消评估")

if __name__ == "__main__":
    asyncio.run(main())
