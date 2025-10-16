"""
lean_checks.py
Core “always wrong” QA checks for Phase-2 Lean QA
"""

from __future__ import annotations
import re, unicodedata, json, yaml, requests
from pathlib import Path
from typing import List, Dict, Tuple

import language_tool_python as lt

# ---------- helpers ----------
SENT_RE = re.compile(r"[.!?…]+[\s”»\"]*")  # crude sentence splitter

def normalize(text: str) -> str:
    t = unicodedata.normalize("NFC", text)
    return t.replace("\r", "").strip()

def sentence_count(text: str) -> int:
    return len([s for s in SENT_RE.split(text) if s.strip()])

# ---------- LanguageTool ----------
CFG_PATH = Path(__file__).resolve().parents[2] / "config" / "qa.yaml"
CFG = yaml.safe_load(CFG_PATH.read_text(encoding="utf-8")) or {}
lt_url = CFG.get("lt", {}).get("url")
if lt_url:
    LT_CLIENT = lt.LanguageTool("pt-PT", remote_server=lt_url)
else:
    LT_CLIENT = lt.LanguageToolPublicAPI("pt-PT")  # fall back to public

SEVERE_RULES = {
    # subset of pt-PT rule IDs that almost always indicate a real error
    "SENT_START_CASE",
    "GENDER_NUMBER_AGREEMENT",
    "VERB_AGR",
    "ADV_ADV",
    "DUPLICATE_WORD"
}

def lt_high_errors(text: str) -> List[str]:
    matches = LT_CLIENT.check(text)
    msgs = [m.ruleId for m in matches if m.ruleId in SEVERE_RULES]
    return msgs

# ---------- Banned AO spellings ----------
PRE_AO_SET = set()
file_ao = Path(__file__).resolve().parents[2] / "config" / "pre_ao_list.txt"
if file_ao.exists():
    PRE_AO_SET = {w.strip().lower() for w in file_ao.read_text(encoding="utf-8").splitlines() if w.strip()}

def banned_ao_forms(text: str) -> List[str]:
    found = []
    for w in PRE_AO_SET:
        if re.search(rf"\b{re.escape(w)}\b", text, flags=re.I):
            found.append(w)
    return found

# ---------- Numbering gap ----------
def numbering_gap(nums: List[int]) -> List[int]:
    if not nums:
        return []
    full = set(range(1, max(nums) + 1))
    return sorted(full - set(nums))

# ---------- Scripture ref quick regex ----------
REF_RE = re.compile(r"\b([1-3]?\s?[A-Za-z]+)\s+\d{1,3}:\d{1,3}\b")

def scripture_refs(text: str) -> List[str]:
    return [m.group(0) for m in REF_RE.finditer(text)]

# ---------- MAIN CHECK FUNCTION ----------
def run_checks(src: str, raw: str, pe: str, para_no: int) -> Dict:
    """Return dict of issues for this paragraph"""
    src = normalize(src)
    raw = normalize(raw)
    pe  = normalize(pe)

    issues = {}

    # length / coverage
    len_ratio = len(pe) / max(1, len(raw))
    sent_ratio = sentence_count(pe) / max(1, sentence_count(raw))
    if len_ratio < 0.90 or sent_ratio < 0.90:
        issues["coverage"] = {"len_ratio": len_ratio, "sent_ratio": sent_ratio}

    # LT severe grammar
    lt_errs = lt_high_errors(pe)
    if lt_errs:
        issues["grammar"] = lt_errs[:5]

    # pre-AO banned spellings
    ao = banned_ao_forms(pe)
    if ao:
        issues["ao_spelling"] = ao

    # scripture ref missing verse
    refs = scripture_refs(src)
    if refs:
        present = any(r.lower() in pe.lower() for r in refs)
        if not present:
            issues["scripture_missing"] = refs

    return issues
