# scripts/tm_retriever.py
from __future__ import annotations
import chromadb
from openai import OpenAI

def get_chroma_collection(path: str, collection_name: str):
    chroma = chromadb.PersistentClient(path=path)
    col = chroma.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )
    return col

def retrieve_examples(src_text: str, col, openai_client: OpenAI,
                      embedding_model: str, k: int = 3):
    """
    Return list of dicts: [{"src": <eng>, "pe": <pt>, "id": <segment_id>, "distance": float}, ...]
    """
    # Embed query
    emb = openai_client.embeddings.create(model=embedding_model, input=[src_text])
    q_vec = emb.data[0].embedding

    # Query Chroma
    res = col.query(
        query_embeddings=[q_vec],
        n_results=k,
        include=["documents", "metadatas", "distances"]  # <-- no "ids" here
    )

    # ids come back regardless of include
    ids       = res.get("ids", [[]])[0]
    docs      = res.get("documents", [[]])[0]
    metas     = res.get("metadatas", [[]])[0]
    distances = res.get("distances", [[]])[0]

    out = []
    for doc, meta, i, dist in zip(docs, metas, ids, distances):
        out.append({"id": i, "src": doc, "pe": meta["pe"], "distance": dist})
    return out
