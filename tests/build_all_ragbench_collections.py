import os
from test_ragas_evaluation import RagBenchEvaluator
from utils.llm_utils import EmbeddingManager
from databases.milvus.flat_collection import FlatCollectionManager
from config.global_config import GlobalConfig
from utils.log_utils import logger

def build_all_collections():
    evaluator = RagBenchEvaluator()
    all_datasets = evaluator.available_datasets  # 12个类别
    logger.info(f"将处理以下数据集: {all_datasets}")

    for dataset_name in all_datasets:
        logger.info(f"==== 开始处理数据集: {dataset_name} ====")
        try:
            collection_name = f"ragbench_{dataset_name}"
            embedding_manager = EmbeddingManager()
            flat_manager = FlatCollectionManager(collection_name=collection_name)

            # 🔹 强制重建集合，避免重复追加（可改为读环境变量控制）
            try:
                if flat_manager.exists():
                    logger.info(f"集合已存在，先删除以保证去重: {collection_name}")
                    flat_manager.drop_collection(force=True)
                # 重新创建集合
                flat_manager._init_collection(force_recreate=False)
                logger.info(f"集合已重建: {collection_name}")
            except Exception as e:
                logger.error(f"创建/重建集合 {collection_name} 失败: {e}")
                continue

            # 1. 提取文档
            documents_data = evaluator.extract_documents_from_dataset(dataset_name)
            logger.info(f"{dataset_name} 提取文档数: {len(documents_data)}")

            if not documents_data:
                logger.warning(f"{dataset_name} 没有文档数据，跳过插入")
                continue

            # 2. 批量处理并插入
            batch_size = 10
            for i in range(0, len(documents_data), batch_size):
                batch = documents_data[i:i+batch_size]
                milvus_records = []
                candidate_doc_ids = []
                for doc_data in batch:
                    try:
                        doc_id = f"ragbench_{doc_data['dataset']}_{doc_data['doc_hash'][:8]}"
                        seg_id = f"{doc_id}_seg_0"  # 统一首段索引，避免重复
                        content = doc_data['document']
                        dense_vector = embedding_manager.embed_text(content)
                        milvus_record = {
                            "doc_id": seg_id,
                            "seg_id": seg_id,
                            "seg_dense_vector": dense_vector,
                            "seg_content": content,
                            "seg_type": "text",
                            "seg_page_idx": 0,
                            "created_at": "",
                            "updated_at": "",
                            "metadata": {
                                "dataset": doc_data['dataset'],
                                "source_file": doc_data.get('source_file', ''),
                                "source_idx": doc_data.get('source_idx', 0)
                            }
                        }
                        milvus_records.append(milvus_record)
                        candidate_doc_ids.append(seg_id)
                    except Exception as e:
                        logger.error(f"文档处理失败: {e}")
                        continue
                if milvus_records:
                    # 去重：过滤已存在的 doc_id
                    try:
                        existing = flat_manager.get_existing_doc_ids(candidate_doc_ids)
                        if existing:
                            before = len(milvus_records)
                            milvus_records = [r for r in milvus_records if r["doc_id"] not in existing]
                            logger.info(f"过滤已存在记录: {len(existing)} 条，实际将插入 {len(milvus_records)}/{before}")
                    except Exception as e:
                        logger.warning(f"查询已存在 doc_id 失败，跳过去重: {e}")

                if milvus_records:
                    try:
                        flat_manager.insert_data(milvus_records)
                        logger.info(f"{dataset_name} 插入 {len(milvus_records)} 条记录")
                    except Exception as e:
                        logger.error(f"{dataset_name} 批量插入失败: {e}")
            # 打印集合统计信息，核对实体数
            try:
                stats = flat_manager.get_collection_stats()
                logger.info(f"集合 {collection_name} 统计: entities={stats.get('entity_count')}")
            except Exception:
                pass

            logger.info(f"==== {dataset_name} 处理完成 ====")
        except Exception as e:
            logger.error(f"{dataset_name} 处理失败: {e}")

if __name__ == "__main__":
    build_all_collections()
