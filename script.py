#!/usr/bin/env python3
"""
script.py – Unified Itaú Credit-Card PDF/TXT → CSV Parser
(“100 %-golden” foundation build)

Core goals
──────────
• Single canonical entry-point – replaces codex.py / enhanced_codex.py.
• Golden-CSV compliant schema and ‘;’ delimiter.
• Modular internal structure but delivered as one file for now.
• Extensible via CONFIG dicts (regexes, categories, keywords).
• Graceful fallbacks, deterministic SHA-256 ledger hash.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import datetime
import tracemalloc
import time
import re
import sys
from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, date
from typing import List, Tuple, Optional

# ──────────────────────────────────────────────────────────────
# 1. CONFIGURATION TABLES  (edit without touching code below)
# ──────────────────────────────────────────────────────────────
SCHEMA = [
    "card_last4",
    "post_date", 
    "desc_raw",
    "amount_brl",
    "installment_seq",
    "installment_tot",
    "fx_rate",
    "iof_brl",
    "category",
    "merchant_city",
    "ledger_hash",
    "prev_bill_amount",
    "interest_amount",
    "amount_orig",
    "currency_orig",
    "amount_usd"
]

CATEGORY_MAP = {
    # priority keywords → category
    "7117": "PAGAMENTO",
    "IOF": "ENCARGOS",
    "JUROS": "ENCARGOS",
    "MULTA": "ENCARGOS",
    # merchant patterns
    "SUPERMERC": "SUPERMERCADO",
    "MERCADO": "SUPERMERCADO",
    "FARMAC": "FARMÁCIA",
    "DROG": "FARMÁCIA",
    "RESTAUR": "RESTAURANTE",
    "POSTO": "POSTO",
    "UBER": "TRANSPORTE",
    "HOTEL": "TURISMO",
    "AEROPORTO": "TURISMO",
    "ALIMENT": "ALIMENTAÇÃO",
    "SERVIÇO": "SERVIÇOS",
    # fallback
}

PREV_BILL_KEYWORDS = ("fatura anterior", "ref.", "refª", "pagt anterior")

# ──────────────────────────────────────────────────────────────
# 2. REGEXES  (compiled once – reusable everywhere)
# ──────────────────────────────────────────────────────────────
RE_DECIMAL = re.compile(r"[^\d,\-]")
RE_CARD = re.compile(r"final (\d{4})")
RE_DATE = re.compile(r"(?P<d>\d{1,2})/(?P<m>\d{1,2})(?:/(?P<y>\d{4}))?")
RE_BRL = re.compile(r"-?\s*\d{1,3}(?:\.\d{3})*,\d{2}")

# Single-line domestic purchase  → “15/03 COMPRA MERCADO X         123,45”
RE_DOMESTIC = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2})\s+(?P<desc>.+?)\s+(?P<amt>-?\d{1,3}(?:\.\d{3})*,\d{2})$"
)

# Payment line  (flexible spacing)
RE_PAYMENT = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}(?:/\d{4})?)\s+PAGAMENTO.*?7117.*?(?P<amt>-?\s*[\d.,]+)\s*$",
    re.I,
)

# FX first line: “15/04 AMAZON US  10,00   52,34”
RE_FX_L1 = re.compile(
    r"^(?P<date>\d{2}/\d{2})\s+(?P<desc>.+?)\s+(?P<orig>-?\d{1,3}(?:\.\d{3})*,\d{2})\s+(?P<brl>-?\d{1,3}(?:\.\d{3})*,\d{2})$"
)
# FX rate line:  “Dólar de Conversão R$ 4,9876”
RE_DOLLAR_RATE = re.compile(r"D[óo]lar de Convers[ãa]o.*?(\d+,\d{4})", re.I)
# IOF detection
RE_IOF = re.compile(r"Repasse de IOF", re.I)

# ──────────────────────────────────────────────────────────────
# 3. UTILS
# ──────────────────────────────────────────────────────────────
def decomma(x: str | Decimal) -> Decimal:
    "Convert Brazilian number string to Decimal(2) safely."
    if isinstance(x, Decimal):
        return x
    if not x:
        return Decimal("0.00")
    val = RE_DECIMAL.sub("", x.replace(" ", "")).replace(".", "").replace(",", ".")
    try:
        return Decimal(val).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:  # pragma: no cover
        return Decimal("0.00")


def calculate_ledger_hash(card_last4: str, post_date: str, desc_raw: str, valor_brl: str) -> str:
    """
    Simple deterministic hash for golden CSV alignment.
    Uses: card|date|description|amount
    """
    # Normalize inputs
    card = (card_last4 or "").strip()
    date = (post_date or "").strip()
    desc = (desc_raw or "").strip().lower()
    amount = (valor_brl or "").strip()
    
    # Create hash input
    key = f"{card}|{date}|{desc}|{amount}"
    return hashlib.sha1(key.encode('utf-8')).hexdigest()


def norm_date(raw: str, ref_year: int, ref_month: int) -> str:
    """
    Normalise DD/MM(/YYYY) → YYYY-MM-DD.
    If year missing, use reference (footer period).
    """
    m = RE_DATE.match(raw or "")
    if not m:
        return ""
    d, mth, yr = m.groups()
    yr = yr or str(ref_year)
    mth = mth or str(ref_month)
    try:
        return f"{int(yr):04}-{int(mth):02}-{int(d):02}"
    except ValueError:
        return ""


def clean_line(txt: str) -> str:
    "Strip funky symbols / duplicate spaces."
    txt = re.sub(r"[\ue000-\uf8ff]", "", txt)  # PUA glyphs
    txt = re.sub(r"\s{2,}", " ", txt.strip(">•*®«» @_")).strip()
    return txt


def extract_merchant_city_domestic(second_line: str) -> str:
    """
    Extract merchant city from domestic posting second line.
    Format: 'SAÚDE .PASSO FUNDO' -> 'PASSO FUNDO'
    """
    if not second_line or '.' not in second_line:
        return ""
    parts = second_line.split('.')
    if len(parts) >= 2:
        city = parts[-1].strip()
        return city.upper() if city else ""  # Keep uppercase for golden alignment
    return ""

def extract_merchant_city_international(second_line: str) -> str:
    """
    Extract merchant city from international posting second line.
    Format: 'ROMA 18,20 EUR 21,04' -> 'ROMA'
            'SAN FRANCISCO 5,09 USD 5,09' -> 'SAN FRANCISCO'
    """
    if not second_line:
        return ""
    
    # Find city as text before first number
    import re
    match = re.match(r"([A-Za-zÀ-ÿ\s]+?)\s+\d", second_line)
    if match:
        city = match.group(1).strip()
        return city.upper() if city else ""  # Keep uppercase for golden alignment
    
    # Fallback: first word
    words = second_line.split()
    return words[0].upper() if words else ""

def classify(desc: str, amt: Decimal) -> str:
    """
    Category assignment to match golden CSV expectations.
    """
    up = desc.upper()
    
    # Priority classifications
    if "7117" in up:
        return "PAGAMENTO"
    if "AJUSTE" in up or (abs(amt) < Decimal("0.30") and abs(amt) > 0):
        return "AJUSTE"
    if any(k in up for k in ("IOF", "JUROS", "MULTA")):
        return "ENCARGOS"
    
    # Category mapping based on golden CSV patterns
    if "FARMAC" in up or "DROG" in up:
        return "FARMÁCIA"
    if "SUPERMERC" in up or "MERCADO" in up:
        return "SUPERMERCADO"
    if "RESTAUR" in up or "PIZZ" in up or "BAR" in up:
        return "RESTAURANTE"
    if "POSTO" in up or "COMBUST" in up:
        return "POSTO"
    if "UBER" in up or "TAXI" in up:
        return "TRANSPORTE"
    if "HOTEL" in up or "AEROPORTO" in up:
        return "TURISMO"
    if "APPLE" in up or "DISNEY" in up or "NETFLIX" in up:
        return "DIVERSOS"
    
    # FX detection
    if any(c in up for c in ("USD", "EUR", "FX")) or "DOLAR" in up:
        return "FX"
    
    # Default fallback
    return "DIVERSOS"


# ──────────────────────────────────────────────────────────────
# 4. DATA STRUCTURES
# ──────────────────────────────────────────────────────────────
@dataclass
class Transaction:
    post_date: str = ""
    card_last4: str = ""
    desc_raw: str = ""
    valor_brl: str = ""
    installment_seq: Optional[int] = None
    installment_tot: Optional[int] = None
    valor_orig: str = ""
    moeda_orig: str = ""
    valor_usd: str = ""
    fx_rate: str = ""
    iof_brl: str = ""
    categoria_high: str = ""
    merchant_city: str = ""
    ledger_hash: str = ""
    pagamento_fatura_anterior: str = ""

    def finalise(self):
        # Ledger hash uses canonical fields for deduplication
        self.ledger_hash = calculate_ledger_hash(
            self.card_last4, self.post_date, self.desc_raw, self.valor_brl
        )

    def to_csv_row(self) -> dict:
        # Map internal fields to golden CSV schema
        d = {
            "card_last4": self.card_last4,
            "post_date": self.post_date,
            "desc_raw": self.desc_raw,
            "amount_brl": self.valor_brl,
            "installment_seq": self.installment_seq if self.installment_seq else "",
            "installment_tot": self.installment_tot if self.installment_tot else "",
            "fx_rate": self.fx_rate,
            "iof_brl": self.iof_brl,
            "category": self.categoria_high,
            "merchant_city": self.merchant_city,
            "ledger_hash": self.ledger_hash,
            "prev_bill_amount": self.pagamento_fatura_anterior if self.pagamento_fatura_anterior else "0.00",
            "interest_amount": "0.00",  # Not extracted yet
            "amount_orig": self.valor_orig,
            "currency_orig": self.moeda_orig,
            "amount_usd": self.valor_usd
        }
        
        # Ensure all SCHEMA fields are present
        for k in SCHEMA:
            if k not in d:
                d[k] = ""
        
        # Format decimals as strings with comma (Brazilian format)
        for k in ("amount_brl", "amount_orig", "amount_usd", "fx_rate", "iof_brl", "prev_bill_amount", "interest_amount"):
            if isinstance(d[k], Decimal):
                d[k] = f"{d[k]:.2f}".replace(".", ",")
            elif isinstance(d[k], float):
                d[k] = f"{d[k]:.2f}".replace(".", ",")
            elif not d[k]:  # Empty string
                d[k] = "0.00"
        
        # Installments as int or 0
        for k in ("installment_seq", "installment_tot"):
            if d[k] is None or d[k] == "":
                d[k] = "0"
                
        return d


# ──────────────────────────────────────────────────────────────
# 5. LOADERS
# ──────────────────────────────────────────────────────────────
def load_lines(path: Path) -> List[str]:
    "Return list of cleaned text lines from PDF or TXT."
    if path.suffix.lower() == ".pdf":
        try:
            import pdfplumber
        except ImportError:
            sys.exit("pdfplumber missing: pip install pdfplumber")
        out: List[str] = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                raw = page.extract_text() or ""
                out.extend(raw.splitlines())
        return [clean_line(l) for l in out if l.strip()]
    # else TXT
    return [clean_line(l) for l in path.read_text(encoding="utf-8").splitlines() if l]


# ──────────────────────────────────────────────────────────────
# 6. BLOCK-LEVEL PARSERS
# ──────────────────────────────────────────────────────────────
def parse_fx_block(lines: List[str], idx: int) -> Tuple[Optional[Transaction], int]:
    """
    Try to parse FX cluster at position idx.
    Returns (Transaction | None, lines_consumed)
    """
    if idx >= len(lines) - 1:
        return None, 0
    l1 = lines[idx]
    m1 = RE_FX_L1.match(l1)
    if not m1:
        return None, 0

    # By default we expect next 1–2 lines to contain rate and possibly IOF
    desc = m1.group("desc")
    amount_orig = decomma(m1.group("orig"))
    amount_brl = decomma(m1.group("brl"))
    date_raw = m1.group("date")
    moeda_orig = "USD"  # TODO: parse from line if possible
    valor_usd = ""      # TODO: parse if present
    merchant_city = ""  # Will be extracted from second line

    fx_rate = ""
    iof = ""
    consumed = 1

    for j in range(idx + 1, min(idx + 4, len(lines))):
        ln = lines[j]
        # Extract merchant city from second line (international format)
        if j == idx + 1 and not merchant_city:
            merchant_city = extract_merchant_city_international(ln)
        if not fx_rate:
            rate_m = RE_DOLLAR_RATE.search(ln)
            if rate_m:
                fx_rate = rate_m.group(1).replace(",", ".")
                consumed = j - idx + 1
        if not iof and RE_IOF.search(ln):
            brl_m = RE_BRL.search(ln)
            if brl_m:
                iof = brl_m.group(0)
                consumed = j - idx + 1

    t = Transaction(
        post_date="",  # filled in main loop
        card_last4="", # filled in main loop
        desc_raw=desc,
        valor_brl=f"{amount_brl:.2f}".replace(".", ","),
        installment_seq="",
        installment_tot="",
        valor_orig=f"{amount_orig:.2f}".replace(".", ","),
        moeda_orig=moeda_orig,
        valor_usd=valor_usd,
        fx_rate=fx_rate.replace(".", ",") if fx_rate else "",
        iof_brl=iof.replace(".", ",") if iof else "",
        categoria_high="FX",
        merchant_city=merchant_city,
        ledger_hash="",
        pagamento_fatura_anterior="",
    )
    # Store raw date for enrichment
    t.date = date_raw  # temporary field
    return t, consumed


def parse_payment_line(l: str) -> Optional[Transaction]:
    mp = RE_PAYMENT.match(l)
    if not mp:
        return None
    amt = decomma(mp.group("amt"))
    date_raw = mp.group("date")
    t = Transaction(
        post_date="",  # filled in main loop
        card_last4="", # filled in main loop
        desc_raw="PAGAMENTO",  # Clean description for golden alignment
        valor_brl=f"{amt:.2f}".replace(".", ","),
        installment_seq="",
        installment_tot="",
        valor_orig="",
        moeda_orig="",
        valor_usd="",
        fx_rate="",
        iof_brl="",
        categoria_high="PAGAMENTO",
        merchant_city="",
        ledger_hash="",
        pagamento_fatura_anterior="",
    )
    # Store raw date for enrichment
    t.date = date_raw  # temporary field
    return t


def parse_domestic_line(l: str, next_line: str = "") -> Optional[Transaction]:
    md = RE_DOMESTIC.match(l)
    if not md:
        return None
    amt = decomma(md.group("amt"))
    desc = md.group("desc")
    date_raw = md.group("date")
    
    # Extract merchant city from next line (domestic format)
    merchant_city = extract_merchant_city_domestic(next_line) if next_line else ""
    
    # Try to extract installments from description
    ins_seq, ins_tot = "", ""
    ins_match = re.search(r"(\d{1,2})/(\d{1,2})", desc)
    if ins_match:
        ins_seq, ins_tot = ins_match.group(1), ins_match.group(2)
    
    # Add a temporary date field for enrichment
    t = Transaction(
        post_date="",  # filled in main loop
        card_last4="", # filled in main loop
        desc_raw=desc,  # Use clean description, not full line
        valor_brl=f"{amt:.2f}".replace(".", ","),
        installment_seq=ins_seq,
        installment_tot=ins_tot,
        valor_orig="",
        moeda_orig="",
        valor_usd="",
        fx_rate="",
        iof_brl="",
        categoria_high=classify(desc, amt),
        merchant_city=merchant_city,
        ledger_hash="",
        pagamento_fatura_anterior="",
    )
    # Store raw date for enrichment
    t.date = date_raw  # temporary field
    return t


# ──────────────────────────────────────────────────────────────
# 7. MAIN PARSER LOOP
# ──────────────────────────────────────────────────────────────
def parse_statement(path: Path) -> List[Transaction]:
    lines = load_lines(path)
    logging.info("Loaded %s cleaned lines from %s", len(lines), path.name)

    # crude statement period → filename YYYY-MM fallback
    period_match = re.search(r"(20\d{2})[-_]?(\d{2})", path.stem)
    ref_year, ref_month = (
        (int(period_match.group(1)), int(period_match.group(2)))
        if period_match
        else (2000, 1)
    )

    card_last4 = "0000"
    txs: List[Transaction] = []
    i = 0
    pagamento_idx = 0

    while i < len(lines):
        l = lines[i]

        # card header capture
        mcard = RE_CARD.search(l)
        if mcard:
            card_last4 = mcard.group(1)
            i += 1
            continue

        # FX block (priority)
        tx, consumed = parse_fx_block(lines, i)
        if tx:
            i += consumed
        else:
            # payment
            tx = parse_payment_line(l)
            if tx:
                # ignore previous-bill payoff
                if pagamento_idx == 0 or any(k in l.lower() for k in PREV_BILL_KEYWORDS):
                    logging.debug("Skipping previous-cycle payment: %s", l)
                    i += 1
                    pagamento_idx += 1
                    continue
                pagamento_idx += 1
            else:
                # domestic / fallback - pass next line for merchant city extraction
                next_line = lines[i + 1] if i + 1 < len(lines) else ""
                tx = parse_domestic_line(l, next_line)
            i += 1

        if not tx:
            # UNKNOWN line – can log for training
            logging.debug("UNMATCHED: %s", l)
            continue

        # enrich & finalise
        tx.card_last4 = card_last4
        # Map date fields to canonical
        if hasattr(tx, "date"):
            tx.post_date = norm_date(getattr(tx, "date", ""), ref_year, ref_month)
        elif hasattr(tx, "post_date"):
            tx.post_date = norm_date(getattr(tx, "post_date", ""), ref_year, ref_month)
        tx.finalise()
        txs.append(tx)

    # deduplicate
    unique: dict[str, Transaction] = {}
    for t in txs:
        unique.setdefault(t.ledger_hash, t)
    logging.info("Parsed %d transactions (%d unique)", len(txs), len(unique))
    return list(unique.values())


# ──────────────────────────────────────────────────────────────
# 8. CSV WRITER
# ──────────────────────────────────────────────────────────────
def write_csv(rows: List[Transaction], out_path: Path):
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=SCHEMA, delimiter=";")
        w.writeheader()
        for t in rows:
            w.writerow(t.to_csv_row())
    logging.info("CSV written: %s (%d KB)", out_path.name, out_path.stat().st_size // 1024)


# ──────────────────────────────────────────────────────────────
# 9. CLI
# ──────────────────────────────────────────────────────────────
def cli(argv: List[str] | None = None):
    p = argparse.ArgumentParser(
        description="Unified Itaú PDF/TXT → CSV parser (golden-ready)"
    )
    p.add_argument("files", nargs="+", type=Path, help="PDF or TXT statements")
    p.add_argument("-o", "--out-dir", type=Path, default=Path.cwd(), help="Output dir")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s"
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for f in args.files:
        rows = parse_statement(f)
        out = args.out_dir / f"{f.stem}_parsed.csv"
        write_csv(rows, out)


if __name__ == "__main__":
    cli()
