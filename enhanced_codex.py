#!/usr/bin/env python3
# enhanced_codex.py - Advanced Itaú Fatura PDF/TXT → CSV Parser
# Based on extensive business logic analysis from 4 script versions
# Incorporates sophisticated FX parsing, payment filtering, and validation

import re
import csv
import argparse
import logging
import datetime
import tracemalloc
import time
import hashlib
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, date

__version__ = "0.13.0"
DATE_FMT_OUT = "%Y-%m-%d"
SCHEMA = [
    "card_last4", "post_date", "desc_raw", "valor_brl",
    "installment_seq", "installment_tot",
    "valor_orig", "moeda_orig", "valor_usd", "fx_rate",
    "iof_brl", "categoria_high", "merchant_city", "ledger_hash",
    "pagamento_fatura_anterior"
]

# ================================================================
# ENHANCED REGEX PATTERNS (from advanced logic analysis)
# ================================================================

# Core patterns
RE_DATE = re.compile(r"(?P<d>\d{1,3})/(?P<m>\d{1,2})(?:/(?P<y>\d{4}))?")
RE_PAY_HDR = re.compile(r"Pagamentos efetuados", re.I)
RE_BRL = re.compile(r"-?\s*\d{1,3}(?:\.\d{3})*,\d{2}")

# Payment patterns (enhanced)
RE_PAY_LINE = re.compile(r"^(?P<date>\d{1,3}/\d{1,2}(?:/\d{4})?)\s+PAGAMENTO(\s+EFETUADO)?\s+7117\s*[-\t ]+(?P<amt>-\s*[\d.,]+)\s*$", re.I)
RE_PAY_LINE_ANY = re.compile(r"^(?P<date>\d{1,3}/\d{1,2}(?:/\d{4})?)\s+PAGAMENTO.*?(?P<amt>-?\s*[\d.,]+)\s*$", re.I)

# FX patterns (sophisticated multi-line parsing)
RE_FX_MAIN = re.compile(r'^(?P<date>\d{2}/\d{2})\s+(?P<descr>.+?)\s+(?P<orig>-?\d{1,3}(?:\.\d{3})*,\d{2})\s+(?P<brl>-?\d{1,3}(?:\.\d{3})*,\d{2})$')
RE_FX_L2_TOL = re.compile(r"^(.+?)\s+([\d.,]+)\s+([A-Z]{3})\s+([\d.,]+)$")
RE_FX_L2_TOL_ANY = re.compile(r"^(.+?)\s+([\d.,]+)\s+([A-Z]{3})\s+([\d.,]+)$", re.I)
RE_FX_BRL = re.compile(r"^(?P<date>\d{1,2}/\d{1,2})(?:/\d{4})?\s+(?P<city>.+?)\s+(?P<orig>[\d.,]+)\s+(?P<cur>[A-Z]{3})\s+(?P<brl>[\d.,]+)$")
RE_DOLAR = re.compile(r'^D[óo]lar de Convers[ãa]o.*?(\d+,\d{4})')

# Domestic and other patterns
RE_DOM = re.compile(r"^(?P<date>\d{1,3}/\d{1,2})\s+(?P<desc>.+?)\s+(?P<amt>[-\d.,]+)$")
RE_CARD = re.compile(r"final (\d{4})")
RE_INST = re.compile(r"(\d{1,2})/(\d{1,2})")
RE_INST_TXT = re.compile(r"\+\s*(\d+)\s*x\s*R\$")

# IOF and adjustments
RE_IOF_LINE = re.compile(r"Repasse de IOF", re.I)
RE_AJUSTE_NEG = re.compile(r"(?P<date>\d{1,3}/\d{1,2}).*?ajuste.*?(?P<amt>-\s*\d+,\d{2})", re.I)
RE_ROUND = re.compile(r"^(?P<date>\d{1,3}/\d{1,2})\s+-(?P<amt>0,\d{2})$")

# Headers to drop
RE_DROP_HDR = re.compile(r"^(Total |Lançamentos|Limites|Encargos|Próxima fatura|Demais faturas|Parcelamento da fatura|Simulação|Pontos|Cashback|Outros lançamentos|Limite total de crédito|Fatura anterior|Saldo financiado|Produtos e serviços|Tarifa|Compras parceladas - próximas faturas)", re.I)

# Character cleanup
LEAD_SYM = ">@§$Z)_•*®«» "

# ================================================================
# ENHANCED UTILITY FUNCTIONS
# ================================================================

def decomma(x: str) -> Decimal:
    """Enhanced number parsing with better error handling"""
    if not x or not str(x).strip():
        return Decimal("0.00")
    clean_x = re.sub(r"[^\d,\-]", "", str(x).replace(' ', '')).replace('.', '').replace(',', '.')
    try:
        return Decimal(clean_x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except:
        return Decimal("0.00")

def norm_date(date, ry, rm):
    """Enhanced date normalization"""
    if not date: return ""
    m = RE_DATE.match(str(date))
    if not m: return str(date)
    d, mth, y = m.groups()
    if not y: y = str(ry)
    if not mth: mth = str(rm)
    try:
        return f"{int(y):04}-{int(mth):02}-{int(d):02}"
    except ValueError:
        return str(date)

def sha1(card, date, desc, valor_brl, installment_tot, categoria_high):
    """Generate deterministic transaction hash"""
    h = hashlib.sha1()
    hash_input = f"{card}|{date}|{desc}|{valor_brl}|{installment_tot}|{categoria_high}"
    h.update(hash_input.encode("utf-8"))
    return h.hexdigest()

def classify(desc, amt):
    """Enhanced categorization with expanded mapping"""
    d = str(desc).upper()
    
    # Priority classifications
    if "7117" in d: return "PAGAMENTO"
    if "AJUSTE" in d or (abs(amt) <= Decimal("0.30") and abs(amt) > 0): return "AJUSTE"
    if any(k in d for k in ("IOF", "JUROS", "MULTA")): return "ENCARGOS"
    
    # Enhanced category mapping (from business logic analysis)
    mapping = [
        # Services
        ("ACELERADOR", "SERVIÇOS"),
        ("PONTOS", "SERVIÇOS"),
        ("ANUIDADE", "SERVIÇOS"),
        ("SEGURO", "SERVIÇOS"),
        ("TARIFA", "SERVIÇOS"),
        ("PRODUTO", "SERVIÇOS"),
        ("SERVIÇO", "SERVIÇOS"),
        
        # Specific merchants
        ("SUPERMERC", "SUPERMERCADO"),
        ("MERCADO", "SUPERMERCADO"),
        ("FARMAC", "FARMÁCIA"),
        ("DROG", "FARMÁCIA"),
        ("PANVEL", "FARMÁCIA"),
        
        # Food & dining
        ("RESTAUR", "RESTAURANTE"),
        ("PIZZ", "RESTAURANTE"),
        ("BAR", "RESTAURANTE"),
        ("CAFÉ", "RESTAURANTE"),
        ("LANCHE", "RESTAURANTE"),
        ("ALIMENT", "ALIMENTAÇÃO"),
        ("IFD", "ALIMENTAÇÃO"),
        
        # Transportation
        ("POSTO", "POSTO"),
        ("COMBUST", "POSTO"),
        ("GASOLIN", "POSTO"),
        ("UBER", "TRANSPORTE"),
        ("TAXI", "TRANSPORTE"),
        ("TRANSP", "TRANSPORTE"),
        ("PASSAGEM", "TRANSPORTE"),
        
        # Travel & entertainment
        ("AEROPORTO", "TURISMO"),
        ("HOTEL", "TURISMO"),
        ("TUR", "TURISMO"),
        ("ENTRETENIM", "TURISMO"),
        
        # Other categories
        ("SAUD", "SAÚDE"),
        ("VEIC", "VEÍCULOS"),
        ("VEST", "VESTUÁRIO"),
        ("LOJA", "VESTUÁRIO"),
        ("MAGAZINE", "VESTUÁRIO"),
        ("EDU", "EDUCAÇÃO"),
        ("HOBBY", "HOBBY"),
        ("DIVERS", "DIVERSOS"),
    ]
    
    for k, v in mapping:
        if k in d: return v
    
    # FX detection
    if "EUR" in d or "USD" in d or "FX" in d: return "FX"
    
    # Default
    return "DIVERSOS"

def is_prev_bill_payoff(descr: str, seq_no: int) -> bool:
    """Enhanced payment filtering - ignore first payment (previous bill)"""
    kw = ('fatura anterior', 'ref.', 'refª', 'pagt anterior')
    return seq_no == 0 or any(k in descr.lower() for k in kw)

def strip_pua(s: str) -> str:
    """Remove Private Use Area glyphs (icons)"""
    return re.sub('[\ue000-\uf8ff]', '', s)

def clean(raw: str) -> str:
    """Enhanced line cleaning with PUA removal"""
    if not raw:
        return ""
    raw = strip_pua(raw)
    raw = raw.lstrip(LEAD_SYM).replace("_", " ")
    raw = re.sub(r"\s{2,}", " ", raw)
    return raw.strip()

def build(card, date, desc, valor_brl, cat, ry, rm, **kv):
    """Enhanced transaction builder with better city extraction"""
    norm = norm_date(date, ry, rm) if date else ""
    ledger = sha1(card, norm, desc, valor_brl, kv.get("installment_tot"), cat)
    
    # Enhanced merchant city extraction
    city = None
    if cat == "FX" and "merchant_city" in kv and kv["merchant_city"]:
        city = kv["merchant_city"]
    elif cat == "FX" and " " in str(desc):
        city = str(desc).split()[0].title()
    elif cat == "FX" and desc:
        city = str(desc).title()
    
    # Remove merchant_city from kv if already processed
    kv = dict(kv)
    if "merchant_city" in kv:
        del kv["merchant_city"]
    
    d = dict(
        card_last4=card, 
        post_date=norm, 
        desc_raw=desc, 
        valor_brl=valor_brl,
        categoria_high=cat, 
        merchant_city=city, 
        ledger_hash=ledger, 
        **kv
    )
    
    # Fill missing schema fields
    for k in SCHEMA:
        if k not in d:
            d[k] = ""
    
    return d

# ================================================================
# SOPHISTICATED FX PARSING (state machine approach)
# ================================================================

def parse_fx_chunk(chunk: list[str]):
    """
    Enhanced FX parsing - handles 2 or 3 line patterns:
    • Purchase → Dollar rate (no IOF)
    • Purchase → IOF → Dollar rate
    • Purchase → Dollar rate → IOF
    """
    if len(chunk) < 2:
        return None

    main = RE_FX_MAIN.match(chunk[0])
    if not main:
        return None

    iof_brl = Decimal('0')
    rate_line = None
    
    for ln in chunk[1:]:
        if RE_IOF_LINE.search(ln):
            m = RE_BRL.search(ln)
            if m:
                iof_brl = decomma(m.group(0))
        elif RE_DOLAR.search(ln):
            rate_line = ln

    if not rate_line:
        return None

    dolar_match = RE_DOLAR.search(rate_line)
    if not dolar_match:
        return None
        
    fx_rate = Decimal(dolar_match.group(1).replace(',', '.'))
    
    return {
        "date": main.group('date'),
        "descr": main.group('descr'),
        "valor_orig": decomma(main.group('orig')),
        "valor_brl": decomma(main.group('brl')),
        "fx_rate": fx_rate,
        "iof": iof_brl,
    }

# ================================================================
# ENHANCED MAIN PARSING FUNCTION
# ================================================================

def parse_txt(path: Path, ref_y: int, ref_m: int, verbose=False):
    """Enhanced parsing with sophisticated FX and payment handling"""
    rows, stats = [], Counter()
    card = "0000"
    iof_postings = []
    
    # Handle both PDF and TXT files
    if path.suffix.lower() == '.pdf':
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                text = '\n'.join(page.extract_text() for page in pdf.pages if page.extract_text())
                lines = text.splitlines()
        except ImportError:
            print("[ERROR] pdfplumber not installed. Please install: pip install pdfplumber")
            return [], stats
    else:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    
    stats["lines"] = len(lines)
    skip = 0
    last_date = None
    pagamento_seq = 0
    seen_fx = set()
    
    i = 0
    while i < len(lines):
        if skip:
            skip -= 1
            i += 1
            continue
            
        line = clean(lines[i])
        
        # Skip headers and empty lines
        if RE_DROP_HDR.match(line):
            stats["hdr_drop"] += 1
            i += 1
            continue
        
        if not line:
            i += 1
            continue
        
        # Extract card number
        m_card = RE_CARD.search(line)
        if m_card:
            card = m_card.group(1)
            i += 1
            continue

        # FX parsing with state machine (2 or 3 lines)
        fx_res = None
        consumed = 1
        
        if i + 2 < len(lines):
            fx_res = parse_fx_chunk([line, clean(lines[i+1]), clean(lines[i+2])])
            consumed = 3
        if not fx_res and i + 1 < len(lines):
            fx_res = parse_fx_chunk([line, clean(lines[i+1])])
            consumed = 2
            
        if fx_res:
            fx_key = (fx_res['descr'], fx_res['date'], fx_res['valor_brl'], fx_res['valor_orig'], fx_res['fx_rate'])
            if fx_key in seen_fx:
                print(f"[DUPLICATE] FX duplicate confirmed: {fx_res['descr']} | {fx_res['date']} | {fx_res['valor_brl']}")
            else:
                seen_fx.add(fx_key)
                rows.append(build(
                    card, fx_res['date'], fx_res['descr'], fx_res['valor_brl'], "FX", ref_y, ref_m,
                    valor_orig=fx_res['valor_orig'], fx_rate=fx_res['fx_rate'], iof_brl=fx_res['iof']
                ))
                stats["fx"] += 1
            i += consumed
            continue

        # Enhanced payment parsing with first-payment filtering
        mp = RE_PAY_LINE.match(line) or RE_PAY_LINE_ANY.match(line)
        if mp and mp.group("amt"):
            if is_prev_bill_payoff(line, pagamento_seq):
                print(f"[PAGAMENTO-IGNORE] Previous bill payoff: {line}")
                pagamento_seq += 1
                i += 1
                continue

            val = decomma(mp.group("amt"))
            if val >= 0:
                print(f"[PAGAMENTO-ERR] Positive payment ignored: {line}")
                i += 1
                continue

            rows.append(build(card, mp.group("date"), "PAGAMENTO", val, "PAGAMENTO", ref_y, ref_m))
            stats["pagamento"] += 1
            pagamento_seq += 1
            last_date = mp.group("date")
            i += 1
            continue

        # Domestic transaction parsing
        if RE_DATE.match(line):
            md = RE_DOM.match(line)
            if md:
                desc, amt = md.group("desc"), decomma(md.group("amt"))
                
                # Value validation
                if abs(amt) > 10000 or abs(amt) < 0.01:
                    print(f"[VALOR-SUSPEITO] {desc} {amt}")
                
                # Enhanced installment detection
                re_parc = re.compile(r"(\d{1,2})\s*/\s*(\d{1,2})|(\d{1,2})\s*x\s*R\$|(\d{1,2})\s*de\s*(\d{1,2})", re.I)
                ins = RE_INST.search(desc) or RE_INST_TXT.search(desc) or re_parc.search(desc)
                
                if ins:
                    if ins.lastindex == 2:
                        seq, tot = int(ins.group(1)), int(ins.group(2))
                    elif ins.lastindex == 3:
                        seq, tot = int(ins.group(3)), None
                    elif ins.lastindex == 5:
                        seq, tot = int(ins.group(4)), int(ins.group(5))
                    else:
                        seq, tot = None, None
                    
                    # Only accept installments from current cycle
                    if tot and seq and seq > tot:
                        print(f"[PARCELA-ERR] Installment out of cycle: {desc}")
                        i += 1
                        continue
                else:
                    seq, tot = None, None
                
                cat = classify(desc, amt)
                rows.append(build(card, md.group("date"), desc, amt, cat, ref_y, ref_m, 
                                installment_seq=seq, installment_tot=tot))
                stats[cat.lower()] += 1
                last_date = md.group("date")
                
            i += 1
            continue

        # IOF handling
        m_iof = RE_IOF_LINE.search(line)
        if m_iof:
            mval = RE_BRL.search(line)
            if mval:
                valor = decomma(mval.group(0))
                iof_postings.append(build(card, last_date or "", "Repasse de IOF em R$", 
                                        valor, "IOF", ref_y, ref_m, iof_brl=valor))
                stats["iof"] += 1
            i += 1
            continue

        # Interest and fees
        if any(x in line.upper() for x in ("JUROS", "MULTA", "IOF DE FINANCIAMENTO")):
            mval = RE_BRL.search(line)
            if mval:
                valor = decomma(mval.group(0))
                if valor != 0:
                    rows.append(build(card, last_date or "", line, valor, "ENCARGOS", ref_y, ref_m))
                    stats["encargos"] += 1
            i += 1
            continue

        # Track missed patterns
        stats["regex_miss"] += 1
        if verbose:
            prev_line = lines[i-1] if i > 0 else ""
            next_line = lines[i+1] if i+1 < len(lines) else ""
            with open(f"{path.stem}_missing.txt", "a", encoding="utf-8") as f:
                f.write(f"{i+1:04d}|{lines[i]}\n")
                if prev_line:
                    f.write(f"  [prev] {prev_line}\n")
                if next_line:
                    f.write(f"  [next] {next_line}\n")
        
        i += 1

    # Add IOF postings
    rows.extend(iof_postings)
    
    # Final filtering
    rows = [r for r in rows if r.get("post_date") and r.get("valor_brl") not in ("", None)]
    stats["postings"] = len(rows)
    
    return rows, stats

# ================================================================
# ENHANCED LOGGING AND METRICS
# ================================================================

def log_block(tag, **kv):
    """Enhanced logging with timestamp"""
    logging.info("%s | %-8s", datetime.now().strftime("%H:%M:%S"), tag)
    for k, v in kv.items():
        logging.info("           %-12s: %s", k, v)

def calculate_metrics(rows):
    """Calculate comprehensive financial metrics"""
    kpi = Counter()
    for r in rows:
        if r["categoria_high"] in ("ALIMENTAÇÃO", "SAÚDE", "VESTUÁRIO", "VEÍCULOS", "FARMÁCIA", "SUPERMERCADO", "POSTO", "RESTAURANTE", "TURISMO"): 
            kpi['domestic'] += 1
        elif r["categoria_high"] == "FX": 
            kpi['fx'] += 1
        elif r["categoria_high"] in ("SERVIÇOS",): 
            kpi['services'] += 1
        else: 
            kpi['misc'] += 1

    brl_dom = sum(r["valor_brl"] for r in rows if r["categoria_high"] in ("ALIMENTAÇÃO", "SAÚDE", "VESTUÁRIO", "VEÍCULOS", "FARMÁCIA", "SUPERMERCADO", "POSTO", "RESTAURANTE", "TURISMO"))
    brl_fx = sum(r["valor_brl"] for r in rows if r["categoria_high"] == "FX")
    brl_serv = sum(r["valor_brl"] for r in rows if r["categoria_high"] == "SERVIÇOS")
    neg_rows = sum(1 for r in rows if r.get("valor_brl") not in ("", None) and Decimal(str(r["valor_brl"])) < 0)
    neg_sum = sum(Decimal(str(r["valor_brl"])) for r in rows if r.get("valor_brl") not in ("", None) and Decimal(str(r["valor_brl"])) < 0)

    return kpi, brl_dom, brl_fx, brl_serv, neg_rows, neg_sum

# ================================================================
# MAIN FUNCTION
# ================================================================

def main():
    tracemalloc.start()
    ap = argparse.ArgumentParser(description="Enhanced Itaú statement parser")
    ap.add_argument("files", nargs="+", help="PDF or TXT files to process")
    ap.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    total = Counter()
    t0 = time.perf_counter()
    
    for f in args.files:
        p = Path(f)
        
        # Extract date from filename
        m = re.search(r"(20\d{2})[\-_]?(\d{2})", p.stem)
        if m:
            ry, rm = int(m.group(1)), int(m.group(2))
        else:
            ry, rm = datetime.now().year, datetime.now().month
        
        log_block("START", version=__version__, file=p.name, 
                 sha=hashlib.sha1(p.read_bytes()).hexdigest()[:8])
        
        # Parse file
        rows, stats = parse_txt(p, ry, rm, args.verbose)
        total += stats
        
        # Deduplication check
        seen_hashes = set()
        dupes = 0
        for r in rows:
            if r["ledger_hash"] in seen_hashes:
                print(f"[DUPLICATE] {r['desc_raw']} | {r['post_date']} | {r['valor_brl']}")
                dupes += 1
            else:
                seen_hashes.add(r["ledger_hash"])
        
        # Calculate metrics
        kpi, brl_dom, brl_fx, brl_serv, neg_rows, neg_sum = calculate_metrics(rows)
        
        # Logging
        log_block("PARSE", lines=stats["lines"], postings=stats["postings"], dupes=dupes)
        log_block("CLASSIFY", domestic=kpi["domestic"], fx=kpi["fx"], services=kpi["services"], misc=kpi["misc"])
        log_block("AMOUNTS", brl_dom=f"{brl_dom:,.2f}", brl_fx=f"{brl_fx:,.2f}", brl_serv=f"{brl_serv:,.2f}")
        log_block("SIGNS", neg_rows=neg_rows, neg_sum=f"{neg_sum:,.2f}")
        
        # Write CSV
        output_file = p.with_name(f"{p.stem}_enhanced.csv")
        with output_file.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=SCHEMA)
            writer.writeheader()
            writer.writerows(rows)
        
        size_kb = output_file.stat().st_size // 1024
        log_block("OUTPUT", file=output_file.name, size_kb=size_kb, rows=len(rows))
        
        mem = tracemalloc.get_traced_memory()[1] // 1024 ** 2
        log_block("MEM", peak=f"{mem} MB")
        log_block("END", result="SUCCESS")
    
    # Summary
    dur = time.perf_counter() - t0
    eff_g = total["lines"] - total.get("hdr_drop", 0)
    acc_g = 100 * (eff_g - total["regex_miss"]) / max(eff_g, 1)
    
    log_block("SUMMARY", 
             files=len(args.files), 
             postings=total["postings"], 
             miss=total["regex_miss"], 
             accuracy=f"{acc_g:.1f}%", 
             duration=f"{dur:.2f}s")

if __name__ == "__main__":
    main()
