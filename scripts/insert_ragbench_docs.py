#!/usr/bin/env python3
"""
为RAGBench相关的空知识库插入文档

此脚本会：
1. 获取所有知识库列表
2. 识别RAGBench相关的空知识库
3. 从parquet文件提取文档内容
4. 创建txt文件并上传到对应知识库
5. 使用优化的模型配置和处理规则
"""

import os
import json
import requests
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Set
import time
from tqdm import tqdm

# 导入配置
try:
    from insert_config import (
        DIFY_CONFIG, RAGBENCH_CONFIG, DATASET_CONFIGS, 
        DEFAULT_MODELS, PROCESS_RULES, UPLOAD_CONFIG
    )
except ImportError:
    print("⚠️  无法导入配置文件，使用默认配置")
    # 默认配置
    DIFY_CONFIG = {
        "base_url": "http://192.168.31.205",
        "api_key": "dataset-L7pHf6iaAwImkw5601pv3N2u"
    }
    RAGBENCH_CONFIG = {
        "data_path": "data/ragbench",
        "max_documents_per_dataset": 50,
        "upload_delay": 0.2,
        "temp_dir": "temp_docs"
    }
    DEFAULT_MODELS = {
        "embedding_model": {"provider": "siliconflow", "model": "BAAI/bge-m3"},
        "retrieval_model": {"search_method": "hybrid_search", "reranking_enable": True}
    }
    PROCESS_RULES = {"mode": "custom"}

class RAGBenchDocumentInserter:
    def __init__(self, dify_base_url: str, api_key: str):
        """
        初始化RAGBench文档插入器
        
        Args:
            dify_base_url: Dify服务器地址
            api_key: Dify API密钥
        """
        self.base_url = dify_base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 使用配置文件中的RAGBench数据集配置
        self.ragbench_datasets = DATASET_CONFIGS
        
        # 模型配置
        self.model_config = DEFAULT_MODELS
        self.process_rules = PROCESS_RULES
        
        print(f"🔧 使用模型配置:")
        print(f"   嵌入模型: {self.model_config['embedding_model']['model']}")
        print(f"   检索方法: {self.model_config['retrieval_model']['search_method']}")
        print(f"   重排序: {'启用' if self.model_config['retrieval_model']['reranking_enable'] else '禁用'}")
    
    def get_all_knowledge_bases(self) -> List[Dict[str, Any]]:
        """
        获取所有知识库列表
        
        Returns:
            知识库列表
        """
        url = f"{self.base_url}/v1/datasets?include_all=true"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            result = response.json()
            knowledge_bases = result.get("data", [])
            
            print(f"✅ 成功获取知识库列表")
            print(f"   总数: {len(knowledge_bases)}")
            
            return knowledge_bases
            
        except requests.exceptions.RequestException as e:
            print(f"❌ 获取知识库列表失败: {e}")
            return []
    
    def identify_ragbench_kbs(self, knowledge_bases: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        识别RAGBench相关的知识库
        
        Args:
            knowledge_bases: 知识库列表
            
        Returns:
            RAGBench知识库字典 {name: kb_info}
        """
        ragbench_kbs = {}
        
        for kb in knowledge_bases:
            name = kb.get('name', '')
            doc_count = kb.get('document_count', 0)
            
            # 检查是否是RAGBench数据集
            if name in self.ragbench_datasets:
                priority = self.ragbench_datasets[name].get('priority', 1)
                ragbench_kbs[name] = {
                    'kb_info': kb,
                    'has_documents': doc_count > 0,
                    'document_count': doc_count,
                    'priority': priority,
                    'description': self.ragbench_datasets[name].get('description', '')
                }
                print(f"📚 发现RAGBench知识库: {name} (文档数: {doc_count}, 优先级: {priority})")
        
        # 按优先级排序
        sorted_kbs = dict(sorted(ragbench_kbs.items(), key=lambda x: x[1]['priority']))
        return sorted_kbs
    
    def extract_documents_from_parquet(self, dataset_name: str, ragbench_path: str, max_docs: int = 50) -> List[str]:
        """
        从parquet文件提取文档内容
        
        Args:
            dataset_name: 数据集名称
            ragbench_path: RAGBench数据路径
            max_docs: 最大文档数量
            
        Returns:
            文档内容列表
        """
        dataset_path = Path(ragbench_path) / dataset_name
        train_file = dataset_path / "train-00000-of-00001.parquet"
        
        if not train_file.exists():
            print(f"  ⚠️  训练文件不存在: {train_file}")
            return []
        
        try:
            # 读取parquet文件
            df = pd.read_parquet(train_file)
            print(f"  📖 读取到 {len(df)} 条记录")
            
            # 提取文档内容
            documents = []
            if 'documents' in df.columns:
                # 如果documents列是列表，展开它
                for idx, row in df.iterrows():
                    docs = row['documents']
                    if isinstance(docs, list):
                        documents.extend(docs)
                    else:
                        documents.append(str(docs))
            elif 'question' in df.columns and 'response' in df.columns:
                # 如果没有documents列，使用question和response组合
                for idx, row in df.iterrows():
                    content = f"Question: {row['question']}\n\nAnswer: {row['response']}"
                    documents.append(content)
            elif 'context' in df.columns and 'question' in df.columns:
                # 如果有context和question列
                for idx, row in df.iterrows():
                    content = f"Context: {row['context']}\n\nQuestion: {row['question']}"
                    if 'answer' in df.columns:
                        content += f"\n\nAnswer: {row['answer']}"
                    documents.append(content)
            
            # 去重并限制数量
            unique_docs = list(set(documents))
            selected_docs = unique_docs[:max_docs]
            
            print(f"  📄 提取到 {len(selected_docs)} 个唯一文档")
            return selected_docs
            
        except Exception as e:
            print(f"  ❌ 处理数据集失败 {dataset_name}: {e}")
            return []
    
    def create_txt_file(self, content: str, filename: str, output_dir: str = None) -> str:
        """
        创建txt文件
        
        Args:
            content: 文档内容
            filename: 文件名
            output_dir: 输出目录
            
        Returns:
            文件路径
        """
        if output_dir is None:
            output_dir = RAGBENCH_CONFIG.get("temp_dir", "temp_docs")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 清理文件名
        safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_filename = safe_filename.replace(' ', '_')
        
        file_path = os.path.join(output_dir, f"{safe_filename}.txt")
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return file_path
        except Exception as e:
            print(f"  ❌ 创建文件失败 {filename}: {e}")
            return None
    
    def upload_document_to_kb(self, kb_id: str, file_path: str, filename: str) -> bool:
        """
        上传文档到知识库
        
        Args:
            kb_id: 知识库ID
            file_path: 文件路径
            filename: 文件名
            
        Returns:
            是否上传成功
        """
        url = f"{self.base_url}/v1/datasets/{kb_id}/document/create-by-file"
        
        try:
            # 使用配置文件中的处理规则
            process_data = {
                "indexing_technique": UPLOAD_CONFIG.get("indexing_technique", "high_quality"),
                "process_rule": self.process_rules
            }
            
            # 上传文件
            with open(file_path, 'rb') as f:
                files = {'file': (f"{filename}.txt", f, 'text/plain')}
                data = {
                    'data': (None, json.dumps(process_data), 'application/json')
                }
                
                response = requests.post(url, files=files, data=data, headers={
                    "Authorization": f"Bearer {self.api_key}"
                })
                
                response.raise_for_status()
                print(f"  ✅ 上传成功: {filename}")
                return True
                
        except Exception as e:
            print(f"  ❌ 上传失败 {filename}: {e}")
            return False
    
    def process_ragbench_dataset(self, dataset_name: str, kb_info: Dict[str, Any], 
                                ragbench_path: str, max_docs: int = 50) -> None:
        """
        处理单个RAGBench数据集
        
        Args:
            dataset_name: 数据集名称
            kb_info: 知识库信息
            ragbench_path: RAGBench数据路径
            max_docs: 最大文档数量
        """
        print(f"\n📚 处理数据集: {dataset_name}")
        print(f"   描述: {kb_info.get('description', 'N/A')}")
        print(f"   优先级: {kb_info.get('priority', 'N/A')}")
        
        kb_id = kb_info['kb_info']['id']
        doc_count = kb_info['document_count']
        
        if doc_count > 0:
            print(f"  ⚠️  知识库已有 {doc_count} 个文档，跳过")
            return
        
        print(f"  🆕 知识库为空，开始插入文档...")
        
        # 提取文档内容
        documents = self.extract_documents_from_parquet(dataset_name, ragbench_path, max_docs)
        
        if not documents:
            print(f"  ❌ 无法提取文档内容")
            return
        
        # 上传文档
        success_count = 0
        for i, doc_content in enumerate(tqdm(documents, desc=f"上传 {dataset_name}")):
            if doc_content and str(doc_content).strip():
                filename = f"{dataset_name}_doc_{i+1:04d}"
                
                # 创建txt文件
                file_path = self.create_txt_file(doc_content, filename)
                if file_path:
                    # 上传到知识库
                    if self.upload_document_to_kb(kb_id, file_path, filename):
                        success_count += 1
                    
                    # 清理临时文件
                    os.remove(file_path)
                    
                    # 添加延迟避免API限制
                    delay = RAGBENCH_CONFIG.get("upload_delay", 0.2)
                    time.sleep(delay)
        
        print(f"  ✅ 成功上传 {success_count}/{len(documents)} 个文档")
    
    def insert_all_ragbench_docs(self, ragbench_path: str, max_docs_per_dataset: int = None) -> None:
        """
        为所有RAGBench知识库插入文档
        
        Args:
            ragbench_path: RAGBench数据路径
            max_docs_per_dataset: 每个数据集最大文档数量
        """
        if max_docs_per_dataset is None:
            max_docs_per_dataset = RAGBENCH_CONFIG.get("max_documents_per_dataset", 50)
        
        print(f"🚀 开始为RAGBench知识库插入文档")
        print(f"📁 数据集路径: {ragbench_path}")
        print(f"🔑 Dify服务器: {self.base_url}")
        print(f"📊 每个数据集最大文档数: {max_docs_per_dataset}")
        print(f"⏱️  上传延迟: {RAGBENCH_CONFIG.get('upload_delay', 0.2)}秒")
        print("=" * 60)
        
        # 获取所有知识库
        knowledge_bases = self.get_all_knowledge_bases()
        if not knowledge_bases:
            print("❌ 无法获取知识库列表")
            return
        
        # 识别RAGBench知识库
        ragbench_kbs = self.identify_ragbench_kbs(knowledge_bases)
        
        if not ragbench_kbs:
            print("❌ 未找到RAGBench相关的知识库")
            return
        
        print(f"\n📋 找到 {len(ragbench_kbs)} 个RAGBench知识库")
        
        # 按优先级处理每个数据集
        for dataset_name, kb_info in ragbench_kbs.items():
            self.process_ragbench_dataset(dataset_name, kb_info, ragbench_path, max_docs_per_dataset)
        
        print(f"\n🎉 所有RAGBench数据集处理完成！")
        
        # 显示最终状态
        print(f"\n📊 最终状态:")
        for dataset_name, kb_info in ragbench_kbs.items():
            status = "✅ 有文档" if kb_info['has_documents'] else "🆕 已插入文档"
            priority = kb_info.get('priority', 'N/A')
            print(f"  {dataset_name}: {status} (优先级: {priority})")


def main():
    """主函数"""
    # 使用配置文件中的配置
    dify_base_url = DIFY_CONFIG.get("base_url", "http://192.168.31.205")
    dify_api_key = DIFY_CONFIG.get("api_key", "dataset-L7pHf6iaAwImkw5601pv3N2u")
    ragbench_path = RAGBENCH_CONFIG.get("data_path", "data/ragbench")
    max_docs = RAGBENCH_CONFIG.get("max_documents_per_dataset", 50)
    
    print("🚀 RAGBench文档插入工具")
    print("=" * 50)
    print(f"Dify服务器: {dify_base_url}")
    print(f"RAGBench路径: {ragbench_path}")
    print(f"最大文档数/数据集: {max_docs}")
    print()
    
    # 检查RAGBench路径
    if not Path(ragbench_path).exists():
        print(f"❌ RAGBench路径不存在: {ragbench_path}")
        return
    
    # 创建插入器并执行
    inserter = RAGBenchDocumentInserter(dify_base_url, dify_api_key)
    inserter.insert_all_ragbench_docs(ragbench_path, max_docs)


if __name__ == "__main__":
    main()
