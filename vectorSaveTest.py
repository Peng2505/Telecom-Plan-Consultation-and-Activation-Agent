# 将 Markdown 知识库切分并写入 Chroma（与运行时同一套 embedding）
import logging
import os
import uuid

import chromadb

from utils.config import Config
from utils.llms import get_llm

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def split_markdown(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    chunks = []
    current = []
    for line in text.splitlines():
        if line.startswith("## ") and current:
            chunks.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append("\n".join(current).strip())
    return [c for c in chunks if c]


def generate_vectors(texts: list) -> list:
    _, embeddings = get_llm(Config.LLM_TYPE)
    return embeddings.embed_documents(texts)


class MyVectorDBConnector:
    def __init__(self, collection_name, embedding_fn):
        chroma_client = chromadb.PersistentClient(path=Config.CHROMADB_DIRECTORY)
        self.collection = chroma_client.get_or_create_collection(name=collection_name)
        self.embedding_fn = embedding_fn

    def add_documents(self, documents):
        self.collection.add(
            embeddings=self.embedding_fn(documents),
            documents=documents,
            ids=[str(uuid.uuid4()) for _ in documents],
        )

    def search(self, query, top_n):
        try:
            return self.collection.query(
                query_embeddings=self.embedding_fn([query]),
                n_results=top_n,
            )
        except Exception as e:
            logger.info(f"检索向量数据库时出错: {e}")
            return []


def vectorStoreSave():
    md_path = Config.KNOWLEDGE_MD
    if not os.path.exists(md_path):
        raise FileNotFoundError(f"知识库文件不存在: {md_path}")
    paragraphs = split_markdown(md_path)
    logger.info(f"切分得到 {len(paragraphs)} 个段落")
    vector_db = MyVectorDBConnector(Config.CHROMADB_COLLECTION_NAME, generate_vectors)
    vector_db.add_documents(paragraphs)
    user_query = "校园套餐给谁用"
    search_results = vector_db.search(user_query, 5)
    logger.info(f"检索测试「{user_query}」: {search_results}")


if __name__ == "__main__":
    vectorStoreSave()
