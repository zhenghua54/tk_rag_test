from src.database.elasticsearch.operations import ElasticsearchOperation
from datetime import datetime



# 初始化 ES 操作对象
es_op = ElasticsearchOperation()

# 构造测试数据
test_doc = {
    "seg_id": "test_seg_001",
    "seg_parent_id": "",
    "doc_id": "test_doc_001",
    "seg_content": "今天天气很不错",
    "seg_type": "text",
    "seg_page_idx": "1",
    "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "metadata": {}
}

# 写入数据
es_op.insert_data([test_doc])
print("写入成功")
# 继续用上面的 es_op 实例
results = es_op.search("天气")
print("检索结果：")
for hit in results:
    print("ID:", hit["_id"], "内容:", hit["_source"]["seg_content"])


# # 批量写入
# docs = []
# for i in range(5):
#     docs.append({
#         "seg_id": f"test_seg_{i}",
#         "seg_parent_id": "",
#         "doc_id": f"test_doc_{i}",
#         "seg_content": f"第{i}条ES批量写入测试数据",
#         "seg_type": "text",
#         "seg_page_idx": str(i),
#         "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#         "metadata": {}
#     })
# es_op.insert_data(docs)
# print("批量写入成功")


# # 复杂查询
# body = {
#     "query": {
#         "bool": {
#             "must": [
#                 {"match": {"seg_content": "测试"}},
#                 {"term": {"seg_type": "text"}}
#             ]
#         }
#     }
# }
# res = es_op.client.search(index=es_op.index_name, body=body)
# for hit in res["hits"]["hits"]:
#     print(hit["_id"], hit["_source"]["seg_content"])


# bash执行
# 1. 检查创建的索引字段： curl -X GET "localhost:9200/tk_rag/_mapping?pretty" -u elastic:password
# 2. 使用分词器对应的颗粒度进行分词： curl -X GET "localhost:9200/_analyze?pretty" -u elastic:Nihao123! -H 'Content-Type: application/json' -d'
                                # {
                                #   "analyzer": "ik_max_word",
                                #   "text": "今天天气很不错"
                                # }'
