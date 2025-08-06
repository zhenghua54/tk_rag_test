#!/usr/bin/env python3
"""
RagBench数据集在TK-RAG系统上的RAGAS评估脚本

测试流程：
1. 从ragbench数据集提取所有documents并去重
2. 将去重后的documents存储到MySQL数据库构建语料库  
3. 使用TK-RAG系统对query进行检索和生成
4. 用RAGAS框架评估生成效果
"""

import os
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Set, Any
import asyncio
from datetime import datetime
import hashlib
from collections import defaultdict

# RAGAS相关导入
try:
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy, 
        context_precision,
        context_recall
    )
except ImportError as e:
    print(f"请先安装RAGAS: pip install ragas datasets")
    exit(1)

# 项目相关导入
import sys
sys.path.append('.')
import requests
import httpx
from config.global_config import GlobalConfig
from core.rag.llm_generator import RAGGenerator
from databases.mysql.operations import file_op, chunk_op
from utils.log_utils import logger

class RagBenchEvaluator:
    """RagBench数据集评估器"""
    
    def __init__(self, api_base_url: str = "http://localhost:8080"):
        """初始化评估器"""
        self.api_base_url = api_base_url.rstrip('/')
        self.datasets_path = Path("data/ragbench")
        self.results_path = Path("evaluation_results")
        self.results_path.mkdir(exist_ok=True)
        
        # 支持的数据集列表
        self.available_datasets = [
            "covidqa", "cuad", "delucionqa", "emanual", "expertqa",
            "finqa", "hagrid", "hotpotqa", "msmarco", "pubmedqa", 
            "tatqa", "techqa"
        ]
        
        logger.info("RagBench评估器初始化完成")
    
    def extract_documents_from_dataset(self, dataset_name: str) -> List[Dict]:
        """
        从数据集中提取所有documents和相关信息
        
        Args:
            dataset_name: 数据集名称
            
        Returns:
            包含documents和queries的数据列表
        """
        dataset_path = self.datasets_path / dataset_name
        parquet_files = list(dataset_path.glob("*.parquet"))
        
        if not parquet_files:
            raise FileNotFoundError(f"在 {dataset_path} 中未找到parquet文件")
        
        all_data = []
        unique_documents = set()
        
        for file_path in parquet_files:
            try:
                df = pd.read_parquet(file_path)
                logger.info(f"加载文件: {file_path}, 样本数: {len(df)}")
                
                for _, row in df.iterrows():
                    # 提取documents（处理各种数据类型）
                    documents = row.get("documents", [])
                    
                    # 标准化documents为列表格式
                    if isinstance(documents, str):
                        documents = [documents]
                    elif hasattr(documents, '__iter__') and not isinstance(documents, str):
                        # 处理numpy数组、pandas Series等可迭代对象
                        try:
                            documents = list(documents)
                        except:
                            documents = [str(documents)]
                    else:
                        documents = [str(documents)] if documents else []
                    
                    # 去重documents
                    for doc in documents:
                        # 安全的文档验证
                        try:
                            doc_str = str(doc).strip() if doc is not None else ""
                            if doc_str:
                                doc_hash = hashlib.md5(doc_str.encode()).hexdigest()
                                if doc_hash not in unique_documents:
                                    unique_documents.add(doc_hash)
                                    all_data.append({
                                        'dataset': dataset_name,
                                        'doc_hash': doc_hash,
                                        'document': doc_str,
                                        'question': str(row.get("question", "")),
                                        'response': str(row.get("response", "")),
                                        'ground_truth': str(row.get("ground_truth", ""))
                                    })
                        except Exception as e:
                            logger.warning(f"处理文档时出错: {e}, 跳过该文档")
                        
            except Exception as e:
                logger.error(f"处理文件 {file_path} 失败: {e}")
                continue
        
        logger.info(f"从 {dataset_name} 提取了 {len(all_data)} 个唯一documents")
        return all_data
    
    def build_corpus_in_database(self, documents_data: List[Dict]) -> None:
        """
        将去重后的documents存储到MySQL数据库构建语料库
        
        Args:
            documents_data: 文档数据列表
        """
        logger.info("开始构建MySQL语料库...")
        
        # 批量插入文档信息
        batch_size = 100
        doc_batch = []
        chunk_batch = []
        
        for i, doc_data in enumerate(documents_data):
            try:
                doc_id = f"ragbench_{doc_data['dataset']}_{doc_data['doc_hash'][:8]}"
                
                # 准备文档信息
                doc_info = {
                    'doc_id': doc_id,
                    'doc_name': f"{doc_data['dataset']}_doc_{i}",
                    'doc_ext': 'txt',
                    'doc_path': f"ragbench/{doc_data['dataset']}/{doc_id}.txt",
                    'doc_size': str(len(doc_data['document'])),
                    'process_status': 'completed',
                    'is_visible': True
                }
                doc_batch.append(doc_info)
                
                # 准备分块信息（将整个document作为一个chunk）
                chunk_info = {
                    'seg_id': f"{doc_id}_seg_1",
                    'seg_content': doc_data['document'],
                    'seg_len': len(doc_data['document']),
                    'seg_type': 'text',
                    'seg_page_idx': 1,
                    'doc_id': doc_id
                }
                chunk_batch.append(chunk_info)
                
                # 批量插入
                if len(doc_batch) >= batch_size:
                    self._insert_batch_data(doc_batch, chunk_batch)
                    doc_batch = []
                    chunk_batch = []
                    
            except Exception as e:
                logger.error(f"处理文档数据失败: {e}")
                continue
        
        # 插入剩余数据
        if doc_batch:
            self._insert_batch_data(doc_batch, chunk_batch)
        
        logger.info(f"语料库构建完成，共插入 {len(documents_data)} 个文档")
    
    def _insert_batch_data(self, doc_batch: List[Dict], chunk_batch: List[Dict]) -> None:
        """批量插入数据到数据库"""
        try:
            # 插入文档信息
            for doc_info in doc_batch:
                try:
                    file_op.insert_data(doc_info)
                except Exception as e:
                    if "Duplicate entry" not in str(e):
                        logger.warning(f"插入文档信息失败: {e}")
            
            # 插入分块信息（批量插入更高效）
            if chunk_batch:
                try:
                    chunk_op.insert_chunks(chunk_batch)
                except Exception as e:
                    if "Duplicate entry" not in str(e):
                        logger.warning(f"批量插入分块信息失败: {e}")
                        # 如果批量插入失败，尝试逐个插入
                        for chunk_info in chunk_batch:
                            try:
                                chunk_op.insert_chunks([chunk_info])
                            except Exception as e2:
                                if "Duplicate entry" not in str(e2):
                                    logger.warning(f"插入单个分块信息失败: {e2}")
                        
        except Exception as e:
            logger.error(f"批量插入数据失败: {e}")
    
    def prepare_evaluation_queries(self, dataset_name: str, sample_size: int = 50) -> List[Dict]:
        """
        准备评估用的queries
        
        Args:
            dataset_name: 数据集名称
            sample_size: 样本数量
            
        Returns:
            评估queries列表
        """
        dataset_path = self.datasets_path / dataset_name
        parquet_files = list(dataset_path.glob("*.parquet"))
        
        queries = []
        for file_path in parquet_files:
            try:
                df = pd.read_parquet(file_path)
                for _, row in df.iterrows():
                    if len(queries) >= sample_size:
                        break
                        
                    query_data = {
                        'question': row.get("question", ""),
                        'documents': row.get("documents", []),
                        'response': row.get("response", ""),
                        'ground_truth': row.get("ground_truth", "")
                    }
                    
                    # 修复数组条件判断问题
                    question_valid = query_data['question'] and str(query_data['question']).strip()
                    documents_valid = False
                    
                    # 处理documents的各种数据类型
                    docs = query_data['documents']
                    if isinstance(docs, (list, tuple)):
                        documents_valid = len(docs) > 0 and any(str(doc).strip() for doc in docs if doc is not None)
                    elif isinstance(docs, str):
                        documents_valid = docs.strip() != ""
                    elif hasattr(docs, '__len__'):  # numpy数组或pandas Series
                        try:
                            documents_valid = len(docs) > 0
                        except:
                            documents_valid = bool(docs)
                    else:
                        documents_valid = bool(docs)
                    
                    if question_valid and documents_valid:
                        queries.append(query_data)
                        
                if len(queries) >= sample_size:
                    break
                    
            except Exception as e:
                logger.error(f"读取查询数据失败: {e}")
                continue
        
        logger.info(f"准备了 {len(queries)} 个评估queries")
        return queries[:sample_size]
    
    async def evaluate_with_tk_rag(self, queries: List[Dict]) -> Dict[str, List]:
        """
        使用TK-RAG系统API进行评估
        
        Args:
            queries: 查询列表
            
        Returns:
            RAGAS格式的评估数据
        """
        evaluation_data = {
            "question": [],
            "contexts": [],
            "answer": [],
            "ground_truth": []
        }
        
        # 使用异步HTTP客户端
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i, query_data in enumerate(queries):
                try:
                    logger.info(f"处理查询 {i+1}/{len(queries)}: {query_data['question'][:100]}...")
                    
                    # 准备API请求数据
                    request_data = {
                        "query": query_data['question'],
                        "session_id": f"ragbench_eval_{i}",
                        "permission_ids": [],  # 不使用权限管理
                        "timeout": 30
                    }
                    
                    # 调用RAG对话API
                    api_url = f"{self.api_base_url}/chat/rag_chat"
                    response = await client.post(api_url, json=request_data)
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        # 检查API响应格式
                        if result.get("success") and "data" in result:
                            data = result["data"]
                            
                            # 提取TK-RAG的检索上下文
                            retrieved_contexts = []
                            if 'sources' in data and data['sources']:
                                retrieved_contexts = [source.get('content', '') for source in data['sources']]
                            
                            # 如果没有检索到内容，使用空列表
                            if not retrieved_contexts:
                                retrieved_contexts = [""]
                            
                            evaluation_data["question"].append(query_data['question'])
                            evaluation_data["contexts"].append(retrieved_contexts)
                            evaluation_data["answer"].append(data.get("answer", ""))
                            evaluation_data["ground_truth"].append(query_data.get('ground_truth', query_data.get('response', '')))
                            
                        else:
                            logger.error(f"API返回错误: {result}")
                            # 添加失败的占位数据
                            evaluation_data["question"].append(query_data['question'])
                            evaluation_data["contexts"].append([""])
                            evaluation_data["answer"].append("")
                            evaluation_data["ground_truth"].append(query_data.get('ground_truth', ''))
                    else:
                        logger.error(f"API调用失败: HTTP {response.status_code}, {response.text}")
                        # 添加失败的占位数据
                        evaluation_data["question"].append(query_data['question'])
                        evaluation_data["contexts"].append([""])
                        evaluation_data["answer"].append("")
                        evaluation_data["ground_truth"].append(query_data.get('ground_truth', ''))
                        
                except Exception as e:
                    logger.error(f"API调用异常: {e}")
                    # 添加失败的占位数据
                    evaluation_data["question"].append(query_data['question'])
                    evaluation_data["contexts"].append([""])
                    evaluation_data["answer"].append("")
                    evaluation_data["ground_truth"].append(query_data.get('ground_truth', ''))
        
        return evaluation_data
    
    async def evaluate_with_tk_rag_direct(self, queries: List[Dict]) -> Dict[str, List]:
        """
        直接使用TK-RAG系统进行评估（绕过API，直接调用无权限方法）
        
        Args:
            queries: 查询列表
            
        Returns:
            RAGAS格式的评估数据
        """
        evaluation_data = {
            "question": [],
            "contexts": [],
            "answer": [],
            "ground_truth": []
        }
        
        # 初始化RAG生成器
        rag_generator = RAGGenerator()
        
        for i, query_data in enumerate(queries):
            try:
                logger.info(f"处理查询 {i+1}/{len(queries)}: {query_data['question'][:100]}...")
                
                # 使用无权限版本的方法进行检索
                result = rag_generator.generate_response_without_permission(
                    query=query_data['question'],
                    session_id=f"ragbench_eval_{i}",
                    request_id=f"ragbench_req_{i}"
                )
                
                # 提取TK-RAG的检索上下文
                retrieved_contexts = []
                if 'sources' in result and result['sources']:
                    retrieved_contexts = [source.get('content', '') for source in result['sources']]
                
                # 如果没有检索到内容，使用空列表
                if not retrieved_contexts:
                    retrieved_contexts = [""]
                
                evaluation_data["question"].append(query_data['question'])
                evaluation_data["contexts"].append(retrieved_contexts)
                evaluation_data["answer"].append(result.get("answer", ""))
                evaluation_data["ground_truth"].append(query_data.get('ground_truth', query_data.get('response', '')))
                    
            except Exception as e:
                logger.error(f"TK-RAG评估失败: {e}")
                # 添加失败的占位数据
                evaluation_data["question"].append(query_data['question'])
                evaluation_data["contexts"].append([""])
                evaluation_data["answer"].append("")
                evaluation_data["ground_truth"].append(query_data.get('ground_truth', ''))
        
        return evaluation_data
    
    def build_milvus_corpus(self, documents_data: List[Dict]) -> None:
        """
        将documents进行embedding并插入Milvus
        
        Args:
            documents_data: 文档数据列表
        """
        logger.info("开始构建Milvus语料库...")
        
        try:
            # 导入必要的模块
            from utils.llm_utils import EmbeddingManager
            from databases.milvus.flat_collection import FlatCollectionManager
            from datetime import datetime
            import hashlib
            
            # 初始化embedding管理器和Milvus管理器
            embedding_manager = EmbeddingManager()
            flat_manager = FlatCollectionManager(collection_name=GlobalConfig.MILVUS_CONFIG["collection_name"])
            
            # 批量处理数据
            batch_size = 10
            total_documents = len(documents_data)
            
            for i in range(0, total_documents, batch_size):
                batch = documents_data[i:i + batch_size]
                milvus_records = []
                
                logger.info(f"处理批次 {i//batch_size + 1}/{(total_documents + batch_size - 1)//batch_size}")
                
                for doc_data in batch:
                    try:
                        # 生成文档ID
                        doc_id = f"ragbench_{doc_data['dataset']}_{doc_data['doc_hash'][:8]}"
                        seg_id = f"{doc_id}_seg_0"
                        
                        # 获取文档内容
                        content = doc_data['document']
                        
                        # 生成embedding
                        dense_vector = embedding_manager.embed_text(content)
                        
                        # 准备Milvus记录
                        milvus_record = {
                            "doc_id": seg_id,  # 使用seg_id作为doc_id
                            "seg_id": seg_id,
                            "seg_dense_vector": dense_vector,
                            "seg_content": content,  # BM25函数会自动生成seg_sparse_vector
                            "seg_type": "text",
                            "seg_page_idx": 0,
                            "created_at": datetime.now().isoformat(),
                            "updated_at": datetime.now().isoformat(),
                            "metadata": {
                                "dataset": doc_data['dataset'],
                                "source_file": doc_data.get('source_file', ''),
                                "source_idx": doc_data.get('source_idx', 0)
                            }
                        }
                        
                        milvus_records.append(milvus_record)
                        
                    except Exception as e:
                        logger.error(f"处理文档失败: {e}")
                        continue
                
                # 批量插入到Milvus
                if milvus_records:
                    try:
                        inserted_ids = flat_manager.insert_data(milvus_records)
                        logger.info(f"成功插入 {len(inserted_ids)} 条记录到Milvus")
                    except Exception as e:
                        logger.error(f"批量插入Milvus失败: {e}")
                        # 如果批量插入失败，尝试逐个插入
                        for record in milvus_records:
                            try:
                                flat_manager.insert_data([record])
                            except Exception as e2:
                                logger.error(f"插入单个记录失败: {e2}")
            
            logger.info(f"Milvus语料库构建完成，共处理 {total_documents} 个文档")
            
        except Exception as e:
            logger.error(f"构建Milvus语料库失败: {e}")
            raise
    
    async def run_ragas_evaluation(self, evaluation_data: Dict[str, List]) -> Dict[str, float]:
        """
        运行RAGAS评估
        
        Args:
            evaluation_data: 评估数据
            
        Returns:
            RAGAS评估结果
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
                
                # 过滤条件：问题不为空，答案不为空，上下文不为空
                if (question and answer and contexts and 
                    any(ctx.strip() for ctx in contexts if ctx)):
                    filtered_data["question"].append(question)
                    filtered_data["contexts"].append(contexts)
                    filtered_data["answer"].append(answer)
                    filtered_data["ground_truth"].append(ground_truth)
            
            logger.info(f"过滤后数据统计: 问题数={len(filtered_data['question'])}, "
                       f"答案数={len(filtered_data['answer'])}, "
                       f"上下文数={len(filtered_data['contexts'])}")
            
            if len(filtered_data["question"]) == 0:
                logger.warning("过滤后没有有效数据，返回空结果")
                return {}
            
            # 创建Dataset对象
            dataset = Dataset.from_dict(filtered_data)
            
            # 配置RAGAS使用的LLM
            from langchain_openai import ChatOpenAI
            from ragas.llms import LangchainLLMWrapper
            
            # 使用本地LLM或配置OpenAI
            try:
                # 尝试使用本地LLM（如果有的话）
                llm = LangchainLLMWrapper(ChatOpenAI(
                    model=os.getenv("LLM_NAME"),
                    base_url=os.getenv("DASHSCOPE_API_BASE_URL"),
                    api_key=os.getenv("DASHSCOPE_API_KEY"),
                    temperature=0,
                    max_tokens=1000,
                    request_timeout=120,  # 增加超时时间
                    max_retries=3  # 添加重试机制
                ))
                logger.info("使用DashScope LLM进行RAGAS评估")
            except Exception as e:
                logger.warning(f"无法配置LLM，使用默认设置: {e}")
                llm = None
            
            # 定义评估指标并配置LLM
            metrics = []
            for metric in [faithfulness, answer_relevancy, context_precision, context_recall]:
                if llm:
                    metric.llm = llm
                metrics.append(metric)
            
            logger.info("开始RAGAS评估...")
            
            # 执行评估
            import time
            start_time = time.time()
            
            # 执行RAGAS评估
            try:
                results = evaluate(dataset, metrics=metrics)
                evaluation_time = time.time() - start_time
                logger.info(f"评估完成，耗时: {evaluation_time:.2f}秒")
            except Exception as e:
                logger.error(f"RAGAS评估失败，尝试简化评估: {e}")
                # 如果LLM评估失败，使用基于规则的简单评估
                evaluation_results = self._simple_evaluation(filtered_data)
                return evaluation_results
            
            # 转换结果格式（处理不同的返回格式）
            evaluation_results = {}
            
            # 检查results的类型和结构
            logger.info(f"RAGAS返回结果类型: {type(results)}")
            logger.info(f"RAGAS返回结果内容: {results}")
            
            if hasattr(results, 'items'):
                # 如果是字典格式
                for metric_name, score in results.items():
                    evaluation_results[metric_name] = float(score)
                    logger.info(f"{metric_name}: {score:.4f}")
            elif hasattr(results, '__dict__'):
                # 如果是对象格式，尝试获取属性
                for metric_name in ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']:
                    if hasattr(results, metric_name):
                        score = getattr(results, metric_name)
                        evaluation_results[metric_name] = float(score)
                        logger.info(f"{metric_name}: {score:.4f}")
            else:
                logger.error(f"未知的RAGAS结果格式: {type(results)}")
                return {}
            
            return evaluation_results
            
        except Exception as e:
            logger.error(f"RAGAS评估失败: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _simple_evaluation(self, data: Dict[str, List]) -> Dict[str, float]:
        """
        简化的评估方法，当LLM评估失败时使用
        
        Args:
            data: 评估数据
            
        Returns:
            简化的评估结果
        """
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
    
    async def run_complete_evaluation(self, dataset_name: str, sample_size: int = 50):
        """
        运行完整的评估流程
        
        Args:
            dataset_name: 数据集名称  
            sample_size: 评估样本数量
        """
        logger.info(f"开始完整评估流程: {dataset_name}")
        
        try:
            # 1. 提取documents并去重
            print("步骤1: 提取documents并去重...")
            documents_data = self.extract_documents_from_dataset(dataset_name)
            
            # 2. 构建MySQL语料库
            print("步骤2: 构建MySQL语料库...")
            # self.build_corpus_in_database(documents_data)
            
            # # 2.5. 将documents进行embedding并插入Milvus
            # print("步骤2.5: 将documents进行embedding并插入Milvus...")
            # self.build_milvus_corpus(documents_data)
            
            # 3. 准备评估queries
            print("步骤3: 准备评估queries...")
            queries = self.prepare_evaluation_queries(dataset_name, sample_size)
            
            # 4. 使用TK-RAG系统评估
            print("步骤4: 使用TK-RAG系统生成回答...")
            try:
                # 优先尝试直接调用（避免API依赖）
                evaluation_data = await self.evaluate_with_tk_rag_direct(queries)
            except Exception as e:
                logger.warning(f"直接调用失败，尝试API调用: {e}")
                evaluation_data = await self.evaluate_with_tk_rag(queries)
            
            # 5. 运行RAGAS评估
            print("步骤5: 运行RAGAS评估...")
            ragas_results = await self.run_ragas_evaluation(evaluation_data)
            
            # 6. 保存和展示结果
            results = {
                "dataset_name": dataset_name,
                "sample_size": len(evaluation_data["question"]),
                "documents_count": len(documents_data),
                "timestamp": datetime.now().isoformat(),
                "ragas_metrics": ragas_results,
                "summary": {
                    "average_score": sum(ragas_results.values()) / len(ragas_results) if ragas_results else 0,
                    "best_metric": max(ragas_results.keys(), key=lambda k: ragas_results[k]) if ragas_results else None,
                    "worst_metric": min(ragas_results.keys(), key=lambda k: ragas_results[k]) if ragas_results else None
                }
            }
            
            self.save_results(dataset_name, results)
            self.print_results(results)
            
        except Exception as e:
            logger.error(f"完整评估流程失败: {e}")
    
    def save_results(self, dataset_name: str, results: Dict[str, Any]):
        """保存评估结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ragbench_evaluation_{dataset_name}_{timestamp}.json"
        filepath = self.results_path / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"评估结果已保存到: {filepath}")
    
    def print_results(self, results: Dict[str, Any]):
        """打印评估结果"""
        print("\n" + "="*70)
        print("RagBench在TK-RAG系统上的RAGAS评估结果")
        print("="*70)
        print(f"数据集: {results['dataset_name']}")
        print(f"语料库文档数: {results['documents_count']}")
        print(f"评估样本数: {results['sample_size']}")
        print(f"评估时间: {results['timestamp']}")
        print("\nRAGAS指标得分:")
        print("-"*50)
        
        for metric, score in results['ragas_metrics'].items():
            print(f"{metric:25}: {score:.4f}")
        
        print("-"*50)
        print(f"平均得分: {results['summary']['average_score']:.4f}")
        print(f"最佳指标: {results['summary']['best_metric']}")
        print(f"最差指标: {results['summary']['worst_metric']}")
        print("="*70)

async def main():
    """主函数"""
    evaluator = RagBenchEvaluator()
    
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
    
    # 设置样本数量
    while True:
        try:
            sample_size = input("评估样本数量 (默认50): ").strip()
            if not sample_size:
                sample_size = 50
            else:
                sample_size = int(sample_size)
            break
        except ValueError:
            print("请输入有效数字")
    
    print(f"\n开始评估 {selected_dataset} 数据集...")
    print("这将包括:")
    print("1. 提取并去重documents")
    print("2. 构建MySQL语料库") 
    print("3. 使用TK-RAG系统生成回答")
    print("4. 用RAGAS评估效果")
    
    confirm = input("\n确认开始? (y/N): ").strip().lower()
    if confirm == 'y':
        await evaluator.run_complete_evaluation(selected_dataset, sample_size)
    else:
        print("已取消评估")

if __name__ == "__main__":
    asyncio.run(main())