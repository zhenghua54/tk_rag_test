from typing import List
from langchain.schema import Document

class VectorRetriever:
    """向量检索器"""
    def __init__(self, vectorstore):
        self.vectorstore = vectorstore
    
    def retrieve(self, query: str, k: int = 5) -> List[Document]:
        """检索文档"""
        return self.vectorstore.similarity_search(query, k=k)