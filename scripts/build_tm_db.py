# build_tm_db.py
from pathlib import Path
import json
import os
import time
from typing import List

import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI

# ---------------------- CONFIG ----------------------
CORPUS_PATH = Path("../data/corpus.jsonl")
CHROMA_PATH = Path("../data/chroma")
COLLECTION  = "sermon_tm_v1"

EMB_MODEL        = "text-embedding-3-large"
EMBED_BATCH_SIZE = 512      # max texts per OpenAI embedding call
CHROMA_BATCH_SIZE = 4000    # max rows per col.add(); keep < 5461
SLEEP_SEC        = 0.2      # tiny delay between API calls
# ----------------------------------------------------


def chunk(lst: List, size: int):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def main():
    # Load API key from environment
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    client_ai = OpenAI(api_key=api_key)

    # 1) Load corpus
    if not CORPUS_PATH.exists():
        raise FileNotFoundError("Run step 1 to create data/corpus.jsonl first.")
    records = [json.loads(l) for l in CORPUS_PATH.open()]
    # keep only records with final PT text
    records = [r for r in records if r.get("pe")]

    # 2) Prepare fields
    ids        = [r["segment_id"] for r in records]
    srcs       = [r["src"] for r in records]
    metadatas  = [{"pe": r["pe"]} for r in records]

    # 3) Connect to Chroma
    chroma = chromadb.PersistentClient(path=str(CHROMA_PATH))
    col    = chroma.get_or_create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )

    # Optional: skip IDs already inserted
    existing = set()
    try:
        # ask Chroma for all IDs (may fail if collection is huge – then do a paginated approach)
        all_ids = col.get(include=["ids"])["ids"]
        existing = set(all_ids)
    except Exception:
        pass

    new_ids, new_srcs, new_meta = [], [], []
    for i, _id in enumerate(ids):
        if _id not in existing:
            new_ids.append(_id)
            new_srcs.append(srcs[i])
            new_meta.append(metadatas[i])

    if not new_ids:
        print("Nothing new to insert. Collection already up to date.")
        return

    print(f"Total records: {len(records)} | New to insert: {len(new_ids)}")

    # 4) Embed in batches
    embeddings = []
    for texts in chunk(new_srcs, EMBED_BATCH_SIZE):
        resp = client_ai.embeddings.create(model=EMB_MODEL, input=texts)
        embeddings.extend([d.embedding for d in resp.data])
        time.sleep(SLEEP_SEC)

    # Sanity check
    assert len(new_ids) == len(embeddings) == len(new_srcs) == len(new_meta), "List length mismatch!"

    # 5) Add to Chroma in safe-sized chunks
    inserted = 0
    for i in range(0, len(new_ids), CHROMA_BATCH_SIZE):
        j = i + CHROMA_BATCH_SIZE
        col.add(
            ids=new_ids[i:j],
            documents=new_srcs[i:j],
            metadatas=new_meta[i:j],
            embeddings=embeddings[i:j],
        )
        inserted += (j - i)
        print(f"Inserted {inserted}/{len(new_ids)}")

    print("✔ Done. Collection size now:", col.count())


if __name__ == "__main__":
    main()
