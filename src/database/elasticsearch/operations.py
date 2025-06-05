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
        try:
            # 创建 ES 客户端实例，使用配置中的连接信息
            self.client = Elasticsearch(
                hosts=Config.ES_CONFIG['host'],  # 使用配置的 host
                request_timeout=Config.ES_CONFIG["timeout"],  # 超时设置
                # 7.x版本使用http_auth而不是basic_auth
                http_auth=(Config.ES_CONFIG.get('username', ''), 
                          Config.ES_CONFIG.get('password', '')),  # 用户名密码认证
                verify_certs=Config.ES_CONFIG.get('verify_certs', False)  # 是否验证证书
            )
            # 获取索引名称
            self.index_name = Config.ES_CONFIG["index_name"]
            
            # 测试连接
            if not self.ping():
                raise Exception("无法连接到 Elasticsearch 服务器")
                
            logger.info("Elasticsearch 客户端初始化成功")
            
        except Exception as e:
            logger.error(f"Elasticsearch 客户端初始化失败: {str(e)}")
            raise
        
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
                - type: 文档类型
                - summary_text: 文本内容
        """
        try:
            # 准备批量插入数据
            actions = []
            for doc in data:
                # 构建 ES 文档格式
                action = {
                    "index": {
                        "_index": self.index_name,
                        "_id": doc["segment_id"]
                    }
                }
                actions.append(action)
                actions.append(doc)  # 添加文档内容
                
            # 执行批量插入
            self.client.bulk(body=actions)
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
                            "segment_text": {
                                "query": query,
                                "operator": "and"  # 使用 AND 操作符提高精确度
                            }
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

    def delete_by_doc_id(self, doc_id: str) -> bool:
        """根据文档ID删除所有相关数据
        
        Args:
            doc_id: 要删除的文档ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            # 构建删除查询
            query = {
                "query": {
                    "term": {
                        "doc_id": doc_id
                    }
                }
            }
            
            # 执行删除
            response = self.client.delete_by_query(
                index=self.index_name,
                body=query
            )
            
            deleted_count = response.get('deleted', 0)
            logger.info(f"成功删除文档 {doc_id} 相关的 {deleted_count} 条数据")
            return True
            
        except Exception as e:
            logger.error(f"删除文档 {doc_id} 失败: {str(e)}")
            return False

    def delete_by_segment_id(self, segment_id: str) -> bool:
        """根据片段ID删除数据
        
        Args:
            segment_id: 要删除的片段ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            # 执行删除
            response = self.client.delete(
                index=self.index_name,
                id=segment_id
            )
            
            if response.get('result') == 'deleted':
                logger.info(f"成功删除片段 {segment_id}")
                return True
            else:
                logger.warning(f"片段 {segment_id} 不存在或删除失败")
                return False
                
        except Exception as e:
            logger.error(f"删除片段 {segment_id} 失败: {str(e)}")
            return False

    def clear_index(self) -> bool:
        """清空索引中的所有数据
        
        Returns:
            bool: 是否清空成功
        """
        try:
            # 获取当前索引的文档数
            stats = self.get_stats()
            doc_count = stats.get('doc_count', 0)
            
            if doc_count == 0:
                logger.info("索引已经是空的")
                return True
                
            # 构建删除所有文档的查询
            query = {
                "query": {
                    "match_all": {}
                }
            }
            
            # 执行删除
            response = self.client.delete_by_query(
                index=self.index_name,
                body=query
            )
            
            deleted_count = response.get('deleted', 0)
            logger.info(f"成功清空索引，删除了 {deleted_count} 条数据")
            return True
            
        except Exception as e:
            logger.error(f"清空索引失败: {str(e)}")
            return False

    def delete_index(self) -> bool:
        """完全删除索引
        
        Returns:
            bool: 是否删除成功
        """
        try:
            # 检查索引是否存在
            if not self.client.indices.exists(index=self.index_name):
                logger.info(f"索引 {self.index_name} 不存在")
                return True
                
            # 删除索引
            response = self.client.indices.delete(index=self.index_name)
            
            if response.get('acknowledged'):
                logger.info(f"成功删除索引 {self.index_name}")
                return True
            else:
                logger.warning(f"删除索引 {self.index_name} 失败")
                return False
                
        except Exception as e:
            logger.error(f"删除索引失败: {str(e)}")
            return False

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

    def get_stats(self) -> Dict:
        """获取 ES 索引的统计信息
        
        Returns:
            Dict: 包含索引统计信息的字典
        """
        try:
            # 检查索引是否存在
            if not self.client.indices.exists(index=self.index_name):
                logger.warning(f"索引 {self.index_name} 不存在")
                return {
                    'doc_count': 0,
                    'store_size': 0,
                    'shard_count': 0
                }
            
            # 获取索引统计信息
            stats = self.client.indices.stats(index=self.index_name)
            index_stats = stats['indices'][self.index_name]['total']
            
            # 获取文档总数
            doc_count = index_stats['docs']['count']
            
            # 获取索引大小
            store_size = index_stats['store']['size_in_bytes']
            
            # 获取分片信息
            shard_count = index_stats.get('shards', {}).get('total', 0)
            
            logger.info(f"ES 索引 {self.index_name} 统计信息:")
            logger.info(f"- 文档总数: {doc_count}")
            logger.info(f"- 索引大小: {store_size / 1024 / 1024:.2f} MB")
            logger.info(f"- 分片数: {shard_count}")
            
            return {
                'doc_count': doc_count,
                'store_size': store_size,
                'shard_count': shard_count
            }
        except Exception as e:
            logger.error(f"获取 ES 统计信息失败: {str(e)}")
            raise

    def list_all_documents(self, size: int = 100) -> List[Dict]:
        """列出索引中的所有文档
        
        Args:
            size: 返回的最大文档数，默认100
            
        Returns:
            List[Dict]: 文档列表
        """
        try:
            # 执行搜索，不设置查询条件，返回所有文档
            response = self.client.search(
                index=self.index_name,
                body={
                    "query": {
                        "match_all": {}
                    },
                    "size": size
                }
            )
            
            hits = response["hits"]["hits"]
            total = response["hits"]["total"]["value"]
            
            logger.info(f"ES 索引 {self.index_name} 文档列表:")
            logger.info(f"- 总文档数: {total}")
            logger.info(f"- 返回文档数: {len(hits)}")
            
            # 打印每个文档的基本信息
            for hit in hits:
                doc = hit["_source"]
                logger.info(f"文档 ID: {hit['_id']}")
                logger.info(f"- doc_id: {doc.get('doc_id', 'unknown')}")
                logger.info(f"- segment_id: {doc.get('segment_id', 'unknown')}")
                logger.info(f"- 文本长度: {len(doc.get('segment_text', ''))}")
                logger.info(f"- 文本内容: {doc.get('segment_text', 'unknown')}")
                logger.info("---")
            
            return hits
        except Exception as e:
            logger.error(f"获取文档列表失败: {str(e)}")
            raise

    def init_index(self):
        """初始化ES索引"""
        try:
            # 检查索引是否存在
            if not self.client.indices.exists(index=self.index_name):
                # 创建索引
                self.client.indices.create(
                    index=self.index_name,
                    body={
                        "settings": {
                            "analysis": {
                                "analyzer": {
                                    "default": {
                                        "type": "custom",
                                        "tokenizer": "ik_max_word",
                                        "filter": ["lowercase", "asciifolding"]
                                    }
                                }
                            }
                        },
                        "mappings": {
                            "properties": {
                                "segment_id": {"type": "keyword"},
                                "doc_id": {"type": "keyword"},
                                "type": {"type": "keyword"},
                                "summary_text": {
                                    "type": "text",
                                    "analyzer": "ik_max_word",
                                    "search_analyzer": "ik_max_word"
                                }
                            }
                        }
                    }
                )
                logger.info(f"ES索引 {self.index_name} 创建成功")
            else:
                logger.info(f"ES索引 {self.index_name} 已存在")
                
            # 检查索引配置
            index_settings = self.client.indices.get_settings(index=self.index_name)
            index_mappings = self.client.indices.get_mapping(index=self.index_name)
            logger.info(f"ES索引配置: {index_settings}")
            logger.info(f"ES索引映射: {index_mappings}")
            
        except Exception as e:
            logger.error(f"初始化ES索引失败: {str(e)}")
            raise