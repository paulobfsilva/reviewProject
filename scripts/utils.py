# scripts/utils.py
from __future__ import annotations
from pathlib import Path
import yaml
from openai import OpenAI
import re
from datetime import date

NUM_RE = re.compile(r"^(\d+)\s+(.*)$", flags=re.MULTILINE)

def load_yaml(path: str | Path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_prompt(path: str | Path):
    return Path(path).read_text(encoding="utf-8")

def split_numbered_paragraphs(text: str):
    """
    Input: full EN sermon body where paragraphs start with a number.
    Return: list of tuples [(num, para_text), ...]
    Accepts empty lines between paragraphs.
    """
    paras = []
    current_num = None
    buff = []

    lines = text.splitlines()
    for ln in lines:
        if not ln.strip():
            # blank line: flush if we were in a paragraph
            if current_num is not None:
                paras.append((current_num, "\n".join(buff).strip()))
                current_num, buff = None, []
            continue
        m = NUM_RE.match(ln)
        if m:
            # new paragraph start
            if current_num is not None:
                paras.append((current_num, "\n".join(buff).strip()))
            current_num = int(m.group(1))
            first_line = m.group(2).strip()
            buff = [first_line]
        else:
            buff.append(ln)
    if current_num is not None:
        paras.append((current_num, "\n".join(buff).strip()))
    return paras

def merge_numbered_paragraphs(paras):
    """
    Given list of tuples [(num, text), ...] create final txt
    with 'num text\n\n' blocks.
    """
    out_lines = []
    for num, txt in paras:
        out_lines.append(f"{num} {txt}\n")
    return "\n".join(out_lines).rstrip() + "\n"

def chat_translate(client: OpenAI, system_prompt: str, user_content: str, model: str, temperature: float = 0):
    """
    One call to GPT-4o to translate 'user_content' using 'system_prompt'.
    Return string.
    """
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role":"system","content": system_prompt},
            {"role":"user","content": user_content}
        ]
    )
    return resp.choices[0].message.content.strip()

def chat_postedit(client: OpenAI, system_prompt: str, user_prompt: str, model: str, temperature: float = 0):
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role":"system","content": system_prompt},
            {"role":"user","content": user_prompt}
        ]
    )
    return resp.choices[0].message.content.strip()

WS_MULTI = re.compile(r"[ \t\u00A0]+")

def paragraph_single_line(text: str) -> str:
    """Collapse internal newlines and excessive spaces inside a paragraph."""
    text = text.replace("\r", "")
    text = text.replace("\n", " ")
    text = WS_MULTI.sub(" ", text)
    return text.strip()

PT_MONTHS = [
    None, "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

PART_OF_DAY = {
    "B": "ao pequeno-almoço",
    "M": "manhã",
    "A": "à tarde",
    "E": "à noite",
    "S": "ao nascer do sol",
    "X": "",   # unknown -> omit
}

def format_pt_date_from_ref(ref: str) -> str:
    """
    Convert refs like '55-0116A' or '61-0613' to
    '16 de Janeiro de 1955, à tarde' or '13 de Junho de 1961'.
    """
    # patterns: YY-MMDDX  or  YY-MMDD
    m = re.match(r"^(\d{2})-(\d{2})(\d{2})([A-Z])?$", ref)
    if not m:
        return ""  # can't parse
    yy, mm, dd, suf = m.group(1), m.group(2), m.group(3), m.group(4) or ""
    year = 1900 + int(yy)  # all your corpus is 19xx
    month_i = int(mm)
    day_i = int(dd)
    month_name = PT_MONTHS[month_i] if 1 <= month_i <= 12 else ""
    part = PART_OF_DAY.get(suf, "")
    base = f"{day_i} de {month_name} de {year}".strip()
    return f"{base}, {part}".rstrip(", ").strip()
