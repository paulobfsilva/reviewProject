#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_corpus.py
---------------
Build data/corpus.jsonl with:
  src (EN), mt (raw GPT output), pe (final reviewed PT)

Assumes directories:
  batches/        -> *_input.jsonl with EN source (your old batch files)
  output txt/     -> raw MT txt files: <sermon>_gpt-4o-*-output.txt
  final/          -> reviewed PT txt files: <sermon>.txt

Outputs:
  data/corpus.jsonl

Run:
  python -m scripts.build_corpus
"""

from __future__ import annotations
import json
import re
import unicodedata
from pathlib import Path

# ------------------- PATHS -------------------
ROOT = Path(__file__).resolve().parents[1]
BATCHES_DIR   = ROOT / "batches"
RAW_DIR       = ROOT / "output" / "txt"   # where write_document.py writes raw translations
FINAL_DIR     = ROOT / "output" / "final"        # reviewed PT files
DATA_DIR      = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

print("FINAL_DIR ->", FINAL_DIR, "exists:", FINAL_DIR.exists())
print("Found final files:", list(FINAL_DIR.glob("*"))[:5])

CORPUS_JSONL  = DATA_DIR / "corpus.jsonl"

# -------------- ENCODING HELPERS -------------
CANDIDATE_ENCODINGS = ["utf-8-sig", "utf-8", "cp1252", "iso-8859-1", "latin-1"]

def smart_read_text(path: Path) -> str:
    """Read a text file robustly, trying multiple encodings; normalize newlines and weird chars."""
    if path.is_dir():
        raise IsADirectoryError(f"smart_read_text() given a directory, not a file: {path}")

    raw = path.read_bytes()
    for enc in CANDIDATE_ENCODINGS:
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("latin-1", errors="replace")

    # fix Windows NEL char, normalize
    text = text.replace("\x85", "\n")
    text = unicodedata.normalize("NFC", text)
    return text

# --------------- REGEX HELPERS ---------------
NUM_RE = re.compile(r"^\s*(\d+)\s+(.*)$", flags=re.UNICODE)

def parse_numbered_paragraphs(lines, start_index=0):
    """
    Parse lines[start_index:] that are numbered like '1 text...', possibly with multiple lines until next number.
    Returns: dict {para_num: text}
    """
    paras = {}
    current_num = None
    buff = []

    for ln in lines[start_index:]:
        m = NUM_RE.match(ln)
        if m:
            # flush previous
            if current_num is not None:
                paras[current_num] = "\n".join(buff).strip()
            current_num = int(m.group(1))
            buff = [m.group(2).strip()]
        else:
            # continuation
            if current_num is not None:
                buff.append(ln)
            else:
                # If no paragraph started yet, ignore stray lines
                pass
    if current_num is not None:
        paras[current_num] = "\n".join(buff).strip()

    return paras

# --------------- READERS ---------------------

def read_batches_english(path: Path):
    """
    Return dict:
      {sermon_id: {"title":str, "place":str, "paras": {1: str, 2: str, ...}}}
    Based on your *_input.jsonl format with keys: _title, _place, _<num>
    """
    data = {}
    for f in path.glob("*_input.jsonl"):
        if f.is_dir():
            continue
        sermon_id = f.stem.split("_")[0]  # "47-0412_input" -> "47-0412"
        text = smart_read_text(f)
        en_title = None
        en_place = None
        paras = {}

        for line in text.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            cid = row["custom_id"]                # e.g. 47-0412_3
            part = cid.split("_", 1)[1]           # "title" | "place" | "3" etc.
            msg_text = row["body"]["messages"][-1]["content"]

            if part == "title":
                en_title = msg_text.strip()
            elif part == "place":
                en_place = msg_text.strip()
            else:
                try:
                    num = int(part)
                    paras[num] = msg_text.strip()
                except ValueError:
                    # ignore unknown parts
                    pass

        data[sermon_id] = {"title": en_title, "place": en_place, "paras": paras}
    return data

def read_output_mt(path: Path):
    """
    Raw GPT output TXT files:
      line 1: Title (Norwegian in your example)
      line 2: Place (Norwegian)
      from line 3: numbered paragraphs "1 <text...", blank line separation
    We'll pick only the numbered paras.
    """
    out = {}
    for f in path.glob("*.txt"):
        if f.is_dir():
            continue
        sermon_id = f.stem.split("_")[0]  # <sermon>_gpt-4o-date-output => <sermon>
        text = smart_read_text(f)
        lines = text.splitlines()
        # skip first 2 lines (title + place)
        paras = parse_numbered_paragraphs(lines, start_index=2)
        out[sermon_id] = {"paras": paras}
    return out

def read_final_pe(path: Path):
    """
    Final reviewed PT files:
      line 1: PT title
      line 2: PT place
      line 3: long date text
      from line 4: numbered paragraphs (1, 2, ...)
      -> paragraphs may span multiple lines until next numbered line.
    Return: {sermon_id: {"paras": {1: str, 2: str, ...}}}
    """
    out = {}
    for f in path.glob("*"):
        if f.is_dir():
            continue
        sermon_id = f.stem
        text = smart_read_text(f)
        lines = text.splitlines()
        # from line 4 onward:
        paras = parse_numbered_paragraphs(lines, start_index=3)
        out[sermon_id] = {"paras": paras}
    return out

# --------------- MAIN BUILD ------------------

if __name__ == "__main__":
    print("Using build_corpus from:", Path(__file__).resolve())
    import sys
    print("Python executable:", sys.executable)

    # 1. Read inputs
    print("Reading EN source from batches/ …")
    en = read_batches_english(BATCHES_DIR)

    print("Reading MT from output txt/ …")
    mt = read_output_mt(RAW_DIR)

    print("Reading PE from final/ …")
    pe = read_final_pe(FINAL_DIR)

    # 2. Merge into corpus
    lines_written = 0
    missing = 0
    with CORPUS_JSONL.open("w", encoding="utf-8") as outfh:
        for sid, en_obj in en.items():
            mt_paras = mt.get(sid, {}).get("paras", {})
            pe_paras = pe.get(sid, {}).get("paras", {})

            for num, src_txt in en_obj["paras"].items():
                record = {
                    "sermon_id": sid,
                    "segment_id": f"{sid}_{num:04d}",
                    "para_no": num,
                    "src": src_txt,
                    "mt": mt_paras.get(num, ""),
                    "pe": pe_paras.get(num, "")
                }
                if not record["mt"] or not record["pe"]:
                    missing += 1
                outfh.write(json.dumps(record, ensure_ascii=False) + "\n")
                lines_written += 1

    print(f"\n✔ Wrote {lines_written} segments to {CORPUS_JSONL}")
    if missing:
        print(f"⚠ {missing} segments missing MT or PE. Check alignment or parsing.")

    # Optional: length sanity check
    short = 0
    with CORPUS_JSONL.open(encoding="utf-8") as fh:
        for l in fh:
            r = json.loads(l)
            if len(r["pe"]) < 0.8 * len(r["mt"]) and r["mt"]:
                short += 1
    if short:
        print(f"⚠ {short} segments where PE < 80% of MT length (possible truncation).")
    print("Done.")
