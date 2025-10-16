# top of file (after imports)
import os
import numpy as np, json
from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity
from openai import OpenAI
import tiktoken

# Load API key from environment
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is required")

client = OpenAI(api_key=api_key)
enc = tiktoken.encoding_for_model("text-embedding-3-large")

def batch_by_tokens(texts, max_tokens=240_000):
    """Yield chunks whose total tokens stay under max_tokens."""
    batch, count = [], 0
    for t in texts:
        tk = len(enc.encode(t))
        if batch and count + tk > max_tokens:
            yield batch
            batch, count = [t], tk
        else:
            batch.append(t); count += tk
    if batch:
        yield batch
