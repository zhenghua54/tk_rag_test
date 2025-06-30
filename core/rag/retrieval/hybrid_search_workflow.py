"""混合检索工作流处理器 - 负责协调多种检索方式并合并结果"""
from langchain_core.documents import Document
from typing import List, Dict, Any, Union, Optional
from databases.milvus.operations_v2 import get_hybrid_collection
from utils.log_utils import logger
from utils.llm_utils import rerank_manager
from databases.mysql.operations import ChunkOperation


class HybridSearchWorkflow:
    """混合检索工作流处理器"""

    def __init__(self):
        """初始化工作流处理器"""

        # 初始化 rag_collection_v2 集合
        self.collection = get_hybrid_collection()

    def execute_hybrid_search(self,
                              query: str,
                              query_dense_vector: List[float],
                              permission_ids: Dict[str, Any] = None,
                              k: int = 20,
                              top_k: int = 10) -> List[Document]:
        """执行混合检索工作流 - 返回Document对象
        
        Args:
            query: 查询文本
            query_dense_vector: 查询密集向量
            permission_ids: 权限信息
            k: 每个检索器的返回数量
            top_k: 最终返回数量
            
        Returns:
            List[Dict[str, Any]]: 检索结果列表
        """
        try:
            logger.info(f"开始混合检索工作流, 查询: {query}")

            # 构建权限过滤表达式
            expr = self._build_permission_expr(permission_ids)

            # 步骤1: 并行执行两种检索（密集向量 + 全文检索）
            dense_results = self.collection.dense_search(query_dense_vector, k, expr)
            full_text_results = self.collection.full_text_search(query, k, expr)

            # 步骤2: 提取父片段
            parent_seg_ids = [result["seg_parent_id"] for result in dense_results + full_text_results if
                              result.get("seg_parent_id", "").strip()]
            parent_seg_ids = list(set(parent_seg_ids))  # 去重
            if parent_seg_ids:
                parent_results = self.collection.get_parent_segments(parent_seg_ids)
            else:
                parent_results = []

            # 步骤3: 合并搜索结果
            merged_results = self._merge_search_results(
                dense_results, full_text_results, parent_results
            )

            # 步骤4: 重排序
            reranked_results = self._custom_rerank(query, merged_results, top_k)

            # 步骤5: 检索 mysql 元数据信息, 并转换为 Document 列表
            documents = self._convert_to_documents(reranked_results, permission_ids)

            # 返回前top_k个结果
            final_results = documents[:top_k]

            logger.info(f"混合检索工作流完成, 返回 {len(final_results)} 条结果")
            return final_results

        except Exception as e:
            logger.error(f"混合检索工作流失败: {str(e)}")
            return []

    @staticmethod
    def _build_permission_expr(permission_ids: Union[str, List[str], None]) -> str:
        """构造权限过滤表达式"""
        # 单个权限
        if isinstance(permission_ids, str) and permission_ids.strip():
            perm_list = [permission_ids.strip(), ""]  # 加入默认公开权限
        # 多个权限
        elif isinstance(permission_ids, list) and len(permission_ids) > 0:
            perm_list = [pid.strip() for pid in permission_ids if pid.strip()]
            perm_list.append("")  # 加入默认公开权限
        # 无权限
        else:
            return 'permission_ids IS NULL OR permission_ids == ""'

        perm_expr = ", ".join(f'"{pid}"' for pid in perm_list)  # 避免直接字符串拼接带来的语法注入风险
        return f"permission_ids in [{perm_expr}]"

    @staticmethod
    def _merge_search_results(dense_results: List[Dict[str, Any]],
                              full_text_results: List[Dict[str, Any]],
                              parent_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """合并搜索结果 - 自定义合并策略
        
        Args:
            dense_results: 密集向量检索结果
            full_text_results: 全文检索结果
            parent_results: 父片段结果

        Returns:
            List[Dict[str, Any]]: 合并后的搜索结果
        """

        # 创建结果字典, 使用复合键 (doc_id, seg_id) 避免重复
        result_dict = {}

        # 处理密集向量检索结果
        for i, result in enumerate(dense_results):
            composite_key = (result["doc_id"], result["seg_id"])  # 复合键
            if composite_key not in result_dict:
                result_dict[composite_key] = result.copy()

        # 处理全文检索结果
        for i, result in enumerate(full_text_results):
            composite_key = (result["doc_id"], result["seg_id"])
            if composite_key not in result_dict:
                result_dict[composite_key] = result.copy()

        # 处理父片段结果
        for i, result in enumerate(parent_results):
            composite_key = (result["doc_id"], result["seg_id"])
            if composite_key not in result_dict:
                result_dict[composite_key] = result.copy()

        # 转换为列表
        merged_results = list(result_dict.values())

        logger.info(f"搜索结果合并完成，共 {len(merged_results)} 条唯一结果")
        return merged_results

    def _custom_rerank(self, query: str, results: List[Dict[str, Any]], top_k: int = 10) -> List[Dict[str, Any]]:
        """自定义重排序 - 可以在这里实现各种重排序策略"""
        try:
            # 重排序
            reranked_result = []
            if results:
                scores: List[float] = rerank_manager.rerank(
                    query=query,
                    passages=[doc["seg_content"] for doc in results]
                )

                # 将分数存储到 Document 的 metadata 中
                for doc, score in zip(results, scores):
                    doc['rerank_score'] = score
                    reranked_result.append(doc)

                # 根据rerank分数排序
                reranked_result.sort(key=lambda x: x.metadata.get("rerank_score", 0), reverse=True)

                # 使用一阶差分算法进行文档过滤
                reranked_result = self.detect_cliff_and_filter(reranked_result, top_k=top_k)

            logger.info(f"[重排序] 重排过滤完成, 返回 {len(reranked_result)} 条结果")

            # 提取 Document 列表
            return reranked_result

        except Exception as error:
            logger.error(f"混合检索失败: {str(error)}")
            return []

    @staticmethod
    def _convert_to_documents(results: List[Dict[str, Any]],
                              permission_ids: Union[str, List[str], None] = None) -> List[Document]:
        """将检索结果转换为Langchain Document对象 - 需要从MySQL获取完整内容
        
        Args:
            results: 重排序后的结果列表
        Returns:
            List[Document]: Document 列表
        """

        try:
            if not results:
                return []

            # 提取 seg_ids
            seg_ids = [result.get("seg_id", "") for result in results if result.get("seg_id", "").strip()]

            if not seg_ids:
                logger.warning("没有找到有效的seg_id")
                return []

            # 从mysql获取完整内容
            chunk_op = ChunkOperation()
            mysql_results = chunk_op.get_segment_contents(
                seg_ids=seg_ids,
                permission_ids=permission_ids
            )

            # 创建seg_id 到mysql结果的映射
            mysql_map = {item["seg_id"]: item for item in mysql_results}

            # 转换为Document列表
            documents = []
            for result in results:
                seg_id = result.get("seg_id", "")
                mysql_data = mysql_map.get(seg_id, {})

                if mysql_data:

                    doc = Document(
                        page_content=mysql_data.get("seg_content", ""),
                        metadata={
                            "doc_id": mysql_data.get("doc_id"),
                            "seg_id": mysql_data.get("seg_id"),
                            # "seg_parent_id": result.get("seg_parent_id"),  # 从Milvus结果获取
                            "seg_type": result.get("seg_type"),
                            "seg_page_idx": mysql_data.get("seg_page_idx"),
                            "permission_ids": result.get("permission_ids"),
                            "score": result.get("score"),
                            "search_type": result.get("search_type"),
                            "doc_name": mysql_data.get("doc_name"),
                            "doc_http_url": mysql_data.get("doc_http_url"),
                            "page_png_path": mysql_data.get("page_png_path"),
                            "create_time": mysql_data.get("created_at"),
                            "update_time": mysql_data.get("updated_at")
                        }
                    )
                    documents.append(doc)
                else:
                    logger.warning(f"MySQL 中未找到seg_id: {seg_id}")

            logger.info(f"成功转换为 {len(documents)} 个Document对象")
            return documents

        except Exception as e:
            logger.error(f"转换为Document失败: {str(e)}")
            return []

    @staticmethod
    def detect_cliff_and_filter(reranked_result: List[Dict[str, Any]],
                                top_k: int = 10
                                ) -> List[Dict[str, Any]]:
        """一阶差分算法, 自动检测重排分数的断崖点，并据此过滤文档。
        Args:
            reranked_result: 排名后的 rerank 列表, 分数在 Document.metadata 中
            top_k: 最大保留文档数，None 表示不限。

        Returns:
            List[Document]: 过滤后的文档列表（保留到断崖点前）。
        """
        # 提取分数
        sorted_scores = [doc.get('rerank_score', 0) for doc in reranked_result]

        # 初始化断崖点索引
        cliff_index = 0

        # 无法计算差值时,直接截断前top_k个
        if len(reranked_result) <= 1:
            return reranked_result[:top_k]

        # 计算一阶差分：相邻两个分数之间的“下降值”
        deltas = [sorted_scores[i + 1] - sorted_scores[i] for i in range(len(sorted_scores) - 1)]

        # 找出“下降最大”的位置（断崖点）
        min_delta = min(deltas)
        for idx, delta in enumerate(deltas):
            if delta == min_delta:
                cliff_index = idx + 1
                break

        # 若设置了 top_k，则取 min(cliff_index, top_k)
        if top_k is not None:
            cliff_index = min(cliff_index, top_k)

        # 返回断崖前的文档列表
        return reranked_result[:cliff_index]

    # 全局工作流实例


_hybrid_workflow: Optional[HybridSearchWorkflow] = None


def get_hybrid_workflow() -> HybridSearchWorkflow:
    """获取混合检索工作流实例"""
    global _hybrid_workflow
    if _hybrid_workflow is None:
        _hybrid_workflow = HybridSearchWorkflow()
    return _hybrid_workflow
