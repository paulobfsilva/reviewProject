#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bible.py  –  ARC scripture lookup + mismatch checker
Requires:
  - sqlite3 DB  (data/bible_arc.sqlite)
  - config/book_map.json
"""

from __future__ import annotations
import json, re, sqlite3, unicodedata
from pathlib import Path
from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parents[2]
CFG = json.loads(Path(ROOT / "config" / "qa.yaml").read_text())
BOOK_MAP = json.loads(Path(ROOT / "config" / "book_map.json").read_text())

DB = sqlite3.connect(str(ROOT / CFG["bible"]["sqlite_path"]))

REF_RE = re.compile(
    r"\b([1-3]?\s?[A-Za-z]+)\s+(\d{1,3}):(\d{1,3})(?:[-–](\d{1,3}))?",
    flags=re.I
)

def _norm(txt: str) -> str:
    txt = unicodedata.normalize("NFD", txt.lower())
    txt = re.sub(r"[\u0300-\u036f]", "", txt)   # strip accents
    txt = re.sub(r"[^\w\s]", "", txt)           # punctuation
    return re.sub(r"\s+", " ", txt).strip()

def fetch_arc(book_en: str, chap: int, verse: int) -> str | None:
    book_pt = BOOK_MAP.get(book_en.lower())
    if not book_pt:
        return None
    cur = DB.execute(
        "SELECT v.text FROM verse v JOIN book b ON v.book_id=b.id "
        "WHERE b.name=? AND v.chapter=? AND v.verse=?",
        (book_pt, chap, verse)
    )
    row = cur.fetchone()
    return row[0] if row else None

def extract_refs(src: str) -> list[tuple[str,int,int,int]]:
    """Return [(book_en, chapter, v_start, v_end)]"""
    refs = []
    for m in REF_RE.finditer(src):
        book = m.group(1).strip()
        chap = int(m.group(2))
        v1   = int(m.group(3))
        v2   = int(m.group(4) or v1)
        refs.append((book, chap, v1, v2))
    return refs

SIM_THRESHOLD = 0.85

def bible_checker(src: str, pe: str, cfg=None):
    """Return dict with refs, missing, mismatches, suggestions"""
    refs = extract_refs(src)
    if not refs:
        return {"refs": [], "missing": [], "mismatches": [], "suggestions": []}

    pe_norm = _norm(pe)
    missing, mismatches, suggestions = [], [], []

    for book, chap, v1, v2 in refs:
        if v1 != v2:  # verse range, skip for now
            continue
        arc = fetch_arc(book, chap, v1)
        if not arc:
            continue
        if _norm(arc) not in pe_norm:
            # calc similarity for diagnostics
            sim = fuzz.partial_ratio(_norm(arc), pe_norm) / 100.0
            if sim < SIM_THRESHOLD:
                mismatches.append({"ref": f"{book} {chap}:{v1}", "similarity": sim})
                suggestions.append({"ref": f"{book} {chap}:{v1}", "arc": arc})
    # any refs not found at all in PE?
    for book, chap, v1, v2 in refs:
        if v1 != v2: continue
        tag = f"{BOOK_MAP.get(book.lower(), book)} {chap}:{v1}"
        if all(tag not in s.get("ref", "") for s in suggestions) and tag not in pe:
            missing.append({"ref": tag})

    return {
        "refs": [f"{book} {chap}:{v1}" for book, chap, v1, _ in refs],
        "missing": missing,
        "mismatches": mismatches,
        "suggestions": suggestions[:3]  # cap to 3 notes per para
    }
