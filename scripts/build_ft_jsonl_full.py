#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, random
from pathlib import Path

random.seed(7)

CORPUS = Path("../data/corpus.jsonl")
TRAIN_OUT = Path("../data/pe_ft_train.jsonl")
VAL_OUT   = Path("../data/pe_ft_val.jsonl")

records = [json.loads(l) for l in CORPUS.open(encoding="utf-8")]
# keep only where we actually edited something
records = [r for r in records if r["mt"] and r["pe"] and r["mt"] != r["pe"]]

# (optional) downsample to limit cost
MAX_TRAIN = 10000
if len(records) > MAX_TRAIN:
    records = random.sample(records, MAX_TRAIN)

msgs = []
for r in records:
    msgs.append({
        "messages": [
            {"role": "system",
             "content": "You are a senior EN→pt-PT post-editor. Apply the SMALLEST POSSIBLE edits; keep numbering & formatting; do not omit content."},
            {"role": "user",
             "content": f"SRC: {r['src']}\nRAW: {r['mt']}"},
            {"role": "assistant",
             "content": r["pe"]}
        ]
    })

random.shuffle(msgs)
n = len(msgs)
train, val = msgs[: int(n*0.9)], msgs[int(n*0.9):]

for path, data in [(TRAIN_OUT, train), (VAL_OUT, val)]:
    with path.open("w", encoding="utf-8") as fh:
        for item in data:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")

print("Train set:", len(train), "→", TRAIN_OUT)
print("Val set  :", len(val), "→", VAL_OUT)
