"""相似度分数计算"""
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from src.config.settings import Config


class SimilarCount:
    def __init__(self):
        self.model = SentenceTransformer(Config.MODEL_PATHS["embedding"])

    def get_similarity_to_others(self, reference: str, others: list[str]) -> list[float]:
        """计算一个文本与其他多个文本的相似度

        Args:
            reference (str): 参考文本
            others (list[str]): 待比较文本列表

        Returns:
            list[float]: 相似度列表
        """
        texts = [reference] + others
        embeddings = self.model.encode(texts)
        sims = cosine_similarity([embeddings[0]], embeddings[1:])
        return sims[0].tolist()


if __name__ == "__main__":
    similar_count = SimilarCount()
    print(similar_count.get_similarity_to_others("你好", ["你好吗", "你好啊", "你好呀"]))