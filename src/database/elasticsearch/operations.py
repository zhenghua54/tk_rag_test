"""Elasticsearch 数据库操作类"""
import os
import json
from typing import List, Dict
from elasticsearch import Elasticsearch

from config.settings import Config
from src.utils.common.logger import logger


class ElasticsearchOperation:
    """Elasticsearch 操作类"""

    def __init__(self):
        """初始化 ES 客户端"""

        # 创建 ES 客户端实例，使用配置中的连接信息
        self.client = Elasticsearch(
            hosts=[Config.ES_CONFIG['host']],  # 使用配置的 host
            request_timeout=Config.ES_CONFIG["timeout"]  # 超时设置
        )
        # 获取索引名称
        self.index_name = Config.ES_CONFIG["index_name"]
        
    def create_index(self, index_name: str, schema_config: dict) -> bool:
        """创建索引
        
        Args:
            index_name: 索引名称
            schema_config: 索引配置
            
        Returns:
            bool: 是否创建成功
        """
        try:
            if self.client.indices.exists(index=index_name):
                logger.info(f"索引 {index_name} 已存在，跳过创建")
                return True
                
            # 打印 schema 配置，用于调试
            logger.debug(f"创建索引 {index_name}，配置: {schema_config}")
            
            # 创建索引
            response = self.client.indices.create(
                index=index_name,
                body= schema_config
            )
            logger.info(f"成功创建索引 {index_name}")
            return True
        except Exception as e:
            logger.error(f"创建索引失败: {str(e)}")
            logger.error(f"索引配置: {json.dumps(schema_config, ensure_ascii=False, indent=2)}")
            return False
        

    def insert_data(self, data: List[Dict]):
        """批量插入数据
        
        Args:
            data: 要插入的数据列表，每条数据包含：
                - segment_id: 片段ID
                - doc_id: 文档ID
                - segment_text: 文本内容
        """
        try:
            # 准备批量插入数据
            actions = []
            for doc in data:
                # 构建 ES 文档格式
                actions.append({
                    "_index": self.index_name,  # 指定索引名
                    "_id": doc["segment_id"],  # 使用 segment_id 作为文档 ID
                    "_source": doc  # 文档内容
                })
            # 执行批量插入
            self.client.bulk(actions)
            logger.info(f"成功插入 {len(data)} 条数据到 ES")
        except Exception as e:
            logger.error(f"ES 插入数据失败: {str(e)}")
            raise

    def search(self, query: str, top_k: int = 5):
        """搜索数据
        
        Args:
            query: 搜索查询文本
            top_k: 返回结果数量，默认5条
            
        Returns:
            List[Dict]: 搜索结果列表，每个结果包含：
                - _id: 文档ID
                - _score: 相关度分数
                - _source: 文档内容
        """
        try:
            # 执行搜索
            response = self.client.search(
                index=self.index_name,  # 指定索引名
                body={
                    "query": {
                        "match": {
                            "segment_text": query  # 在 segment_text 字段中搜索
                        }
                    },
                    "size": top_k  # 返回结果数量
                }
            )
            # 返回搜索结果
            return response["hits"]["hits"]
        except Exception as e:
            logger.error(f"ES 搜索失败: {str(e)}")
            raise

    def delete_by_segment_id(self, segment_id: str):
        """删除指定 segment_id 的数据
        
        Args:
            segment_id: 要删除的片段ID
        """
        try:
            # 执行删除操作
            self.client.delete(
                index=self.index_name,  # 指定索引名
                id=segment_id  # 指定文档 ID
            )
            logger.info(f"成功删除 segment_id: {segment_id}")
        except Exception as e:
            logger.error(f"ES 删除数据失败: {str(e)}")
            raise

    def ping(self) -> bool:
        """检查 ES 连接是否正常
        
        Returns:
            bool: 连接是否正常
        """
        try:
            return self.client.ping()
        except Exception as e:
            logger.error(f"ES ping 失败: {str(e)}")
            return False