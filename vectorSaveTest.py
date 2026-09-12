# 将 Markdown 知识库切分并写入 Chroma（稳定 chunk id，与检索评测一致）
import logging
import os

import chromadb

from utils.config import Config
from utils.knowledge import load_knowledge_chunks
from utils.llms import get_llm

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def generate_vectors(texts: list) -> list:
    _, embeddings = get_llm(Config.LLM_TYPE)
    return embeddings.embed_documents(texts)


class MyVectorDBConnector:
    def __init__(self, collection_name, embedding_fn):
        self.chroma_client = chromadb.PersistentClient(path=Config.CHROMADB_DIRECTORY)
        self.collection_name = collection_name
        self.embedding_fn = embedding_fn
        # 重建集合，保证 id 与文档一一对应（评测依赖稳定 id）
        try:
            self.chroma_client.delete_collection(name=collection_name)
            logger.info(f"Deleted existing collection: {collection_name}")
        except Exception:
            pass
        self.collection = self.chroma_client.get_or_create_collection(name=collection_name)

    def add_documents(self, ids: list, documents: list):
        self.collection.add(
            embeddings=self.embedding_fn(documents),
            documents=documents,
            ids=ids,
            metadatas=[{"chunk_id": i} for i in ids],
        )

    def search(self, query, top_n):
        try:
            return self.collection.query(
                query_embeddings=self.embedding_fn([query]),
                n_results=top_n,
            )
        except Exception as e:
            logger.info(f"检索向量数据库时出错: {e}")
            return {}


def vectorStoreSave():
    md_path = Config.KNOWLEDGE_MD
    if not os.path.exists(md_path):
        raise FileNotFoundError(f"知识库文件不存在: {md_path}")
    chunks = load_knowledge_chunks(md_path)
    ids = [c[0] for c in chunks]
    documents = [c[1] for c in chunks]
    logger.info(f"切分得到 {len(documents)} 个段落，ids={ids}")
    vector_db = MyVectorDBConnector(Config.CHROMADB_COLLECTION_NAME, generate_vectors)
    vector_db.add_documents(ids, documents)
    user_query = "校园套餐给谁用"
    search_results = vector_db.search(user_query, 5)
    logger.info(f"检索测试「{user_query}」: {search_results}")


if __name__ == "__main__":
    vectorStoreSave()
