from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection
import numpy as np

# 1️⃣ 连接到 Milvus（将 IP 替换为你的 Ubuntu 虚拟机 IP）
connections.connect("default", host="192.168.1.100", port="19530")  # ← 修改为你的虚拟机局域网地址

# 2️⃣ 定义字段和 schema
collection_name = "demo_bge_collection"
dimension = 1024  # 替换为你实际使用的 embedding 模型维度，例如 BGE-M3 为 1024

fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension)
]
schema = CollectionSchema(fields, description="Test Collection for BGE-M3 Embeddings")

# 删除已有同名 collection（如有）
if collection_name in Collection.list():
    Collection(name=collection_name).drop()

# 3️⃣ 创建 Collection
collection = Collection(name=collection_name, schema=schema)

# 4️⃣ 插入样本数据
num_vectors = 10
data = [
    [i for i in range(num_vectors)],  # id 列
    [np.random.rand(dimension).astype("float32") for _ in range(num_vectors)]  # embedding 向量
]
collection.insert(data)
print(f"✅ 插入 {num_vectors} 条向量数据")

# 5️⃣ 创建索引（建议使用 IVF_FLAT or HNSW）
collection.create_index(field_name="embedding", index_params={
    "metric_type": "L2",  # 或 "COSINE"
    "index_type": "IVF_FLAT",
    "params": {"nlist": 128}
})
print("✅ 索引创建完成")

# 6️⃣ 加载 collection
collection.load()

# 7️⃣ 执行向量搜索
query_vector = [np.random.rand(dimension).astype("float32")]
search_params = {"metric_type": "L2", "params": {"nprobe": 10}}

results = collection.search(
    data=query_vector,
    anns_field="embedding",
    param=search_params,
    limit=3,
    output_fields=["id"]
)

# 8️⃣ 打印搜索结果
for hits in results:
    for hit in hits:
        print(f"🥇 ID: {hit.entity.get('id')}  | Distance: {hit.distance:.4f}")