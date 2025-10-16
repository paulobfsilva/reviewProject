#!/usr/bin/env python3
"""
qa_lean.py
Run Lean QA on a sermon. Produces:
  output/qa/<sermon>_to_review.csv
  output/qa/<sermon>_report.json
"""

from __future__ import annotations
import argparse, json, csv
from pathlib import Path
import pandas as pd

from .lean_checks import run_checks, numbering_gap

META_DIR = Path("output/metadata")
QA_DIR   = Path("output/qa")
QA_DIR.mkdir(parents=True, exist_ok=True)

def load_meta(sermon_id: str):
    meta_path = META_DIR / f"{sermon_id}.jsonl"
    if not meta_path.exists():
        raise FileNotFoundError(meta_path)
    recs = [json.loads(l) for l in meta_path.open(encoding="utf-8")]
    recs.sort(key=lambda r: int(r["para_no"]))
    return recs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sermon-id", required=True)
    args = ap.parse_args()
    sid = args.sermon_id

    recs = load_meta(sid)

    # numbering check
    gaps = numbering_gap([r["para_no"] for r in recs])
    if gaps:
        print("WARNING: missing paragraph numbers:", gaps)

    flagged = []
    full    = []
    for r in recs:
        issues = run_checks(r["src"], r["raw"], r["pe"], r["para_no"])
        full.append({**r, "issues": issues})

        if issues:  # non-empty dict
            flagged.append({
                "para_no": r["para_no"],
                "issues": "; ".join(issues.keys()),
                "src": r["src"][:120].replace("\n", " "),
                "pe":  r["pe"][:120].replace("\n", " ")
            })

    # write outputs
    json_path = QA_DIR / f"{sid}_report.json"
    with json_path.open("w", encoding="utf-8") as fh:
        for row in full:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    csv_path = QA_DIR / f"{sid}_to_review.csv"
    pd.DataFrame(flagged).to_csv(csv_path, index=False)

    print(f"QA finished: {len(flagged)} paragraphs flagged.")
    print("CSV :", csv_path)
    print("JSON:", json_path)

if __name__ == "__main__":
    main()
