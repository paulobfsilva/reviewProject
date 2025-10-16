#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_sermon.py
-----------------
Phase 1 pipeline with console feedback:
- Translate EN -> PT (RAW)
- Retrieve K examples from Chroma
- Post-edit with FT model
- Save final PT + metadata

Usage:
  python -m scripts.process_sermon \
      --sermon-id 47-0412 \
      --input-file input/en/47-0412.txt \
      [--verbose]

"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from typing import List, Tuple

from openai import OpenAI
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.table import Table

from .utils import (
    load_yaml, load_prompt,
    split_numbered_paragraphs, merge_numbered_paragraphs,
    chat_translate, chat_postedit,
    paragraph_single_line, format_pt_date_from_ref
)

from .tm_retriever import get_chroma_collection, retrieve_examples

console = Console()


def load_english(input_file: Path):
    """
    Given a plain text English sermon:
    - line 1: title EN
    - line 2: place EN
    - from line 3: numbered paras (# <text>)
    Return: title_en, place_en, [(num, text), ...]
    """
    lines = input_file.read_text(encoding="utf-8").splitlines()
    title = lines[0].strip() if lines else ""
    place = lines[1].strip() if len(lines) > 1 else ""
    body  = "\n".join(lines[2:]) if len(lines) > 2 else ""
    paras = split_numbered_paragraphs(body)
    return title, place, paras


def build_postedit_prompt(src, raw, examples, postedit_instruction):
    blocks = []
    for i, ex in enumerate(examples, 1):
        blocks.append(
            f"### EXAMPLE {i}\n"
            f"SRC: {ex['src']}\n"
            f"FINAL: {ex['pe']}"
        )
    return (
        f"{postedit_instruction}\n\n"
        + "\n\n".join(blocks)
        + "\n\n---\nNow post-edit:\n"
        f"SRC: {src}\n"
        f"RAW: {raw}\n"
        "Return only the corrected Portuguese."
    )


def preview(text: str, n: int = 80) -> str:
    text = text.replace("\n", " ")
    return text[:n] + ("…" if len(text) > n else "")

def needs_retry(raw_pt, pe_pt, ratio=0.85):
    return len(pe_pt.strip()) < ratio * len(raw_pt.strip())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sermon-id", required=True)
    parser.add_argument("--input-file", required=True, help="Path to English TXT sermon")
    parser.add_argument("--verbose", action="store_true", help="Print full paragraphs & examples")
    args = parser.parse_args()

    cfg = load_yaml("config/settings.yaml")
    translate_system = load_prompt(cfg["translate_prompt_path"])
    postedit_instr   = load_prompt(cfg["postedit_prompt_path"])

    # Init clients & collection
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    client = OpenAI(api_key=api_key)
    col = get_chroma_collection(cfg["chroma_path"], cfg["collection_name"])

    input_file = Path(args.input_file)
    sermon_id  = args.sermon_id

    console.rule(f"[bold cyan]Processing Sermon {sermon_id}")

    title_en, place_en, paras_en = load_english(input_file)
    num_paras = len(paras_en)

    if num_paras == 0:
        console.print("[red]No paragraphs found. Check your input file structure.")
        return

    console.print(f"[green]Loaded EN sermon[/green]: {title_en} ({num_paras} paragraphs)\n")

    # 1) Translate title & place (RAW)
    console.print("[bold]Translating header…[/bold]")
    title_pt_raw = chat_translate(client, translate_system, title_en,
                                  cfg["translate_model"], cfg["temperature_translate"])
    place_pt_raw = chat_translate(client, translate_system, place_en,
                                  cfg["translate_model"], cfg["temperature_translate"])
    if args.verbose:
        console.print(f"[bold]Title RAW[/bold]: {title_pt_raw}")
        console.print(f"[bold]Place RAW[/bold]: {place_pt_raw}\n")

    # 2) Translate paragraphs (RAW) with progress bar
    raw_paras: List[Tuple[int, str]] = []
    console.print("[bold]Translating paragraphs (RAW)…[/bold]")
    with Progress(
        SpinnerColumn(),
        BarColumn(bar_width=40),
        "[progress.percentage]{task.percentage:>3.0f}%",
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        t_task = progress.add_task("RAW translation", total=num_paras)
        for num, src_txt in paras_en:
            raw_pt = chat_translate(client, translate_system, src_txt,
                                    cfg["translate_model"], cfg["temperature_translate"])
            raw_paras.append((num, raw_pt))
            if args.verbose:
                console.print(f"\n[cyan]Para {num} RAW[/cyan]: {preview(raw_pt)}")
            progress.advance(t_task)

    # 3) Post-edit each paragraph
    pe_paras: List[Tuple[int, str]] = []
    metadata_lines = []
    console.print("\n[bold]Post-editing paragraphs (FT + TM)…[/bold]")
    with Progress(
        SpinnerColumn(),
        BarColumn(bar_width=40),
        "[progress.percentage]{task.percentage:>3.0f}%",
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        p_task = progress.add_task("Post-edit", total=num_paras)
        for (num, src_txt), (_, raw_pt) in zip(paras_en, raw_paras):
            # retrieve examples (TM)
            examples = retrieve_examples(src_txt, col, client, cfg["embedding_model"], k=cfg["k_examples"])
            user_prompt = build_postedit_prompt(src_txt, raw_pt, examples, postedit_instr)
            pe_pt = chat_postedit(client, "You post-edit EN→pt-PT sermons.", user_prompt,
                                  cfg["postedit_model"], cfg["temperature_postedit"])
            if needs_retry(raw_pt, pe_pt):
                # Retry with a “strict” instruction
                strict_instr = postedit_instr + "\n\nOUTPUT MUST MATCH RAW LENGTH ±15%. DO NOT OMIT ANY LINE."
                user_prompt = build_postedit_prompt(src_txt, raw_pt, examples, strict_instr)
                pe_pt = chat_postedit(client, "You post-edit EN→pt-PT sermons.", user_prompt,
                                      cfg["postedit_model"], cfg["temperature_postedit"])
                # Optionally, if still short, just fall back to RAW
                if needs_retry(raw_pt, pe_pt):
                    pe_pt = raw_pt
            pe_paras.append((num, pe_pt))
            metadata_lines.append({
                "sermon_id": sermon_id,
                "para_no": num,
                "src": src_txt,
                "raw": raw_pt,
                "pe": pe_pt,
                "examples_used": [{"id": e["id"], "distance": e["distance"]} for e in examples]
            })

            # console feedback
            console.print(
                f"[green]✓ Para {num}[/green] "
                f"EN: {preview(src_txt)} | RAW: {preview(raw_pt)} | PE: {preview(pe_pt)}"
            )
            if args.verbose and examples:
                table = Table(title=f"Examples used for para {num}", show_header=True, header_style="bold magenta")
                table.add_column("ID", style="dim", width=18)
                table.add_column("Distance", justify="right", width=9)
                table.add_column("SRC Example", width=40)
                table.add_column("PE Example", width=40)
                for ex in examples:
                    table.add_row(
                        ex["id"],
                        f"{ex['distance']:.4f}",
                        preview(ex["src"], 120),
                        preview(ex["pe"], 120),
                    )
                console.print(table)

            progress.advance(p_task)

    # 4) Assemble final outputs
    date_pt = format_pt_date_from_ref(sermon_id)
    header = f"{title_pt_raw}\n{place_pt_raw}\n{date_pt}\n"
    final_body = merge_numbered_paragraphs(pe_paras)
    final_text = header + final_body

    # 5) Write files
    Path(cfg["output_final_dir"]).mkdir(parents=True, exist_ok=True)
    Path(cfg["output_meta_dir"]).mkdir(parents=True, exist_ok=True)
    Path(cfg["output_raw_dir"]).mkdir(parents=True, exist_ok=True)

    raw_body = merge_numbered_paragraphs(raw_paras)
    raw_text = f"{title_pt_raw}\n{place_pt_raw}\n{raw_body}"

    raw_path   = Path(cfg["output_raw_dir"],   f"{sermon_id}_raw.txt")
    final_path = Path(cfg["output_final_dir"], f"{sermon_id}_final.txt")
    meta_path  = Path(cfg["output_meta_dir"],  f"{sermon_id}.jsonl")

    raw_path.write_text(raw_text, encoding="utf-8")
    final_path.write_text(final_text, encoding="utf-8")
    with meta_path.open("w", encoding="utf-8") as fh:
        for row in metadata_lines:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    console.rule("[bold green]Done")
    console.print(f"RAW   : {raw_path}")
    console.print(f"FINAL : {final_path}")
    console.print(f"META  : {meta_path}")
    console.print(f"[cyan]Paragraphs processed[/cyan]: {num_paras}")


if __name__ == "__main__":
    main()
