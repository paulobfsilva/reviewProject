#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_tm_db_full.py
--------------------
Reads ALL segments from data/corpus.jsonl and inserts the ones not yet in Chroma.

Run:
  python -m scripts.update_tm_db_full
"""

import json, os, time
from pathlib import Path

import chromadb
from openai import OpenAI

CORPUS = Path("../data/corpus.jsonl")
CHROMA_PATH = "data/chroma"
COLLECTION  = "sermon_tm_v1"
EMB_MODEL   = "text-embedding-3-large"
BATCH_SIZE  = 512
SLEEP_SEC   = 0.2

def chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i+size]

if __name__ == "__main__":
    # load corpus
    records = [json.loads(l) for l in CORPUS.open(encoding="utf-8")]
    # only those with a final PE to store in TM
    records = [r for r in records if r.get("pe")]

    # Load API key from environment
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    client_ai = OpenAI(api_key=api_key)
    chroma = chromadb.PersistentClient(path=CHROMA_PATH)
    col = chroma.get_or_create_collection(name=COLLECTION, metadata={"hnsw:space":"cosine"})

    # existing ids
    existing = set()
    try:
        # Might need pagination if really big; good enough for most cases
        existing.update(col.get(include=["ids"])["ids"])
    except Exception:
        pass

    new = [r for r in records if r["segment_id"] not in existing]
    if not new:
        print("No new segments to add to Chroma.")
        exit(0)

    ids   = [r["segment_id"] for r in new]
    srcs  = [r["src"] for r in new]
    metas = [{"pe": r["pe"]} for r in new]

    # embed new srcs in batches
    embeddings = []
    for chunk_text in chunk(srcs, BATCH_SIZE):
        resp = client_ai.embeddings.create(model=EMB_MODEL, input=chunk_text)
        embeddings.extend([d.embedding for d in resp.data])
        time.sleep(SLEEP_SEC)

    # ---- NEW CHUNKED INSERT -------------------
    CHROMA_BATCH_SIZE = 4000
    inserted = 0
    for i in range(0, len(ids), CHROMA_BATCH_SIZE):
        j = i + CHROMA_BATCH_SIZE
        col.add(
            ids=ids[i:j],
            documents=srcs[i:j],
            metadatas=metas[i:j],
            embeddings=embeddings[i:j],
        )
        inserted += (j - i)
        print(f"Inserted {inserted}/{len(ids)}")
    # -------------------------------------------

    print(f"✔ Done. Total new segments inserted: {inserted}")
