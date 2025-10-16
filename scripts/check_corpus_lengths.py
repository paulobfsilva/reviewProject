# check_corpus_lengths.py
import json
from pathlib import Path

records = [json.loads(l) for l in Path("data/corpus.jsonl").open()]
bad = []
for r in records:
    mt_len = len(r["mt"])
    pe_len = len(r["pe"])
    if pe_len < 0.8 * mt_len:  # adjust threshold as you like
        bad.append((r["sermon_id"], r["para_no"], mt_len, pe_len))

print(f"Total segments: {len(records)}")
print(f"Truncated PE suspects: {len(bad)}")
for sid, pno, mt_l, pe_l in bad[:20]:
    print(sid, pno, mt_l, pe_l)
