import json

with open("/Users/jason/Codes/tk_rag/databases/schema/milvus_flat_schema.json", 'r', encoding='utf-8') as f:
    schema_config = json.load(f)

# 提取字段名作为必需字段列表
required_fields = [field["name"] for field in schema_config["fields"] if field["name"] != 'seg_sparse_vector']

print(required_fields)