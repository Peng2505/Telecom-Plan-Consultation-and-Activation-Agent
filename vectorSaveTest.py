# 将 Markdown 知识库切分并写入 Chroma（稳定 chunk id；默认写入 policy_v2，不污染 data_plans）
from __future__ import annotations

import argparse
import logging
import os
import sys

import chromadb

from utils.config import Config
from utils.knowledge import load_knowledge_chunks, metadata_for_chunk
from utils.llms import get_llm

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def generate_vectors(texts: list) -> list:
    _, embeddings = get_llm(Config.LLM_TYPE)
    # DashScope embedding 单批上限 25
    batch_size = 25
    vectors: list = []
    for i in range(0, len(texts), batch_size):
        vectors.extend(embeddings.embed_documents(texts[i : i + batch_size]))
    return vectors


class MyVectorDBConnector:
    def __init__(self, collection_name, embedding_fn, *, rebuild: bool = True):
        self.chroma_client = chromadb.PersistentClient(path=Config.CHROMADB_DIRECTORY)
        self.collection_name = collection_name
        self.embedding_fn = embedding_fn
        if rebuild:
            try:
                self.chroma_client.delete_collection(name=collection_name)
                logger.info(f"Deleted existing collection: {collection_name}")
            except Exception:
                pass
        self.collection = self.chroma_client.get_or_create_collection(name=collection_name)

    def add_documents(self, ids: list, documents: list, metadatas: list):
        self.collection.add(
            embeddings=self.embedding_fn(documents),
            documents=documents,
            ids=ids,
            metadatas=metadatas,
        )

    def count(self) -> int:
        return self.collection.count()

    def list_ids(self) -> list:
        got = self.collection.get(include=[])
        return list(got.get("ids") or [])


def ingest(md_path: str, collection_name: str, *, rebuild: bool = True) -> tuple[int, list]:
    if not os.path.exists(md_path):
        raise FileNotFoundError(f"知识库文件不存在: {md_path}")
    chunks = load_knowledge_chunks(md_path)
    ids = [c[0] for c in chunks]
    documents = [c[1] for c in chunks]
    source = md_path.replace("\\", "/")
    metadatas = [metadata_for_chunk(i, source) for i in ids]
    if len(ids) != len(set(ids)):
        raise ValueError(f"存在重复 chunk id: {ids}")
    logger.info(f"切分得到 {len(documents)} 个段落，ids={ids}")
    vector_db = MyVectorDBConnector(collection_name, generate_vectors, rebuild=rebuild)
    # 幂等：同 id 用 upsert 语义 —— chromadb add 遇重复会报错，故重建后 add；二次入库前先清空同集合再写入
    vector_db.add_documents(ids, documents, metadatas)
    return vector_db.count(), sorted(vector_db.list_ids())


def main():
    parser = argparse.ArgumentParser(description="Ingest knowledge markdown into Chroma")
    parser.add_argument(
        "--md",
        default=os.getenv("KNOWLEDGE_MD_V2", "knowledge/data_plans_v2.md"),
        help="知识库 Markdown 路径（默认 data_plans_v2.md，不覆盖原文）",
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("CHROMADB_COLLECTION_V2", "policy_v2"),
        help="目标集合名（默认 policy_v2，不污染 data_plans）",
    )
    parser.add_argument(
        "--compare-old",
        default=os.getenv("CHROMADB_COLLECTION_NAME", Config.CHROMADB_COLLECTION_NAME),
        help="用于对比的旧集合名",
    )
    parser.add_argument(
        "--idempotent-check",
        action="store_true",
        help="连续入库两次，确认 chunk 数量与 id 集合不变",
    )
    args = parser.parse_args()

    client = chromadb.PersistentClient(path=Config.CHROMADB_DIRECTORY)
    old_count = None
    try:
        old_count = client.get_collection(args.compare_old).count()
    except Exception:
        old_count = None

    count1, ids1 = ingest(args.md, args.collection, rebuild=True)
    print(f"\n=== INGEST OK ===")
    print(f"md={args.md}")
    print(f"collection={args.collection}")
    print(f"old_collection={args.compare_old} count={old_count}")
    print(f"new_count={count1}")
    print(f"all_ids={ids1}")
    print(f"first_5_ids={ids1[:5]}")

    if args.idempotent_check:
        count2, ids2 = ingest(args.md, args.collection, rebuild=True)
        same = count1 == count2 and ids1 == ids2
        print(f"\n=== IDEMPOTENT CHECK ===")
        print(f"second_count={count2}")
        print(f"ids_unchanged={same}")
        if not same:
            raise SystemExit("幂等自检失败：两次入库 chunk 数或 id 不一致")
        print("idempotent_ok=True")


if __name__ == "__main__":
    main()
