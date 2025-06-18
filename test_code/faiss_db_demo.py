import os

import numpy as np
from databases import FaissDB


def test_faiss_db():
    # 设置测试数据目录
    test_dir = './test_data'

    os.makedirs(test_dir, exist_ok=True)
    index_path = os.path.join(test_dir, 'test_index.faiss')

    # 初始化数据库
    dimension = 768  # 假设使用 768 维向量
    db = FaissDB(dimension=dimension, index_path=index_path)

    # 生成测试数据
    num_vectors = 1000
    vectors = np.random.rand(num_vectors, dimension).astype('float32')

    # 创建元数据
    metadata = [
        {
            'id': i,
            'content': f'这是第 {i} 条测试文本',
            'source': 'test_source',
            'timestamp': f'2024-04-{i % 30 + 1:02d}'
        }
        for i in range(num_vectors)
    ]

    # 添加向量和元数据
    print(f"添加 {num_vectors} 条向量数据...")
    db.add_vectors(vectors, metadata)
    print(f"当前向量总数: {db.get_total_vectors()}")

    # 生成查询向量
    query_vector = np.random.rand(1, dimension).astype('float32')

    # 执行搜索
    print("\n执行相似度搜索...")
    k = 5  # 返回最相似的 5 条结果
    distances, results = db.search(query_vector, k=k)

    # 打印搜索结果
    print(f"\nTop {k} 相似结果:")
    for i, (distance, result) in enumerate(zip(distances, results)):
        print(f"\n结果 {i + 1}:")
        print(f"距离: {distance:.4f}")
        print(f"ID: {result['id']}")
        print(f"文本: {result['content']}")
        print(f"来源: {result['source']}")
        print(f"时间戳: {result['timestamp']}")

    # 测试保存和加载
    print("\n测试保存和加载...")
    db.save_index()

    # 创建新的数据库实例并加载
    new_db = FaissDB(dimension=dimension, index_path=index_path)
    print(f"加载后的向量总数: {new_db.get_total_vectors()}")

    # 清理测试数据
    print("\n清理测试数据...")
    db.clear()
    print(f"清理后的向量总数: {db.get_total_vectors()}")


if __name__ == '__main__':
    test_faiss_db()
