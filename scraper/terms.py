"""Extract decision-relevant terms from EMA-template Fact Sheets (PDF).

EMA requires every retailer to publish a Fact Sheet per plan using a common template, so a
small set of anchored regexes covers all of them. Only fields that change the decision are
extracted; each keeps its verbatim snippet and the source URL so the user can verify it.
Anything not matched stays None and the app shows "see fact sheet" rather than guessing.
"""
from __future__ import annotations

import io
import re

from pypdf import PdfReader

ORDINAL = r"(\d+)(?:st|nd|rd|th)?"


# fact-sheet dwelling labels -> the app's dwelling keys (landed uses the cheapest landed tier, terrace)
DWELLING_LABELS = [
    (r"HDB 1 and 2 Room", "hdb12"), (r"HDB 3 Room", "hdb3"), (r"HDB 4 Room", "hdb4"), (r"HDB 5 Room", "hdb5"),
    (r"Condominium[^$]*?", "condo"), (r"Terrace", "landed"),
]


def pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return re.sub(r"\s+", " ", "\n".join(p.extract_text() or "" for p in reader.pages))


def document_text(content: bytes) -> str:
    """Fact sheets are PDFs for most retailers and HTML pages for some."""
    if content[:4] == b"%PDF":
        return pdf_text(content)
    from bs4 import BeautifulSoup
    return re.sub(r"\s+", " ", BeautifulSoup(content, "lxml").get_text(" ", strip=True))


def _by_dwelling(snippet: str) -> dict[str, float]:
    out = {}
    for label, key in DWELLING_LABELS:
        if m := re.search(label + r"\s*[-–:]\s*\$\s?([\d,]+(?:\.\d{2})?)", snippet):
            out[key] = float(m.group(1).replace(",", ""))
    return out


def _snippet(text: str, start_pat: str, stop_pats: list[str], limit: int = 320) -> str | None:
    m = re.search(start_pat, text)
    if not m:
        return None
    rest = text[m.end():m.end() + limit + 200]
    cut = len(rest)
    for sp in stop_pats:
        s = re.search(sp, rest)
        if s:
            cut = min(cut, s.start())
    out = rest[:min(cut, limit)].strip(" :;")
    return out or None


def extract_terms(text: str) -> dict:
    t = {}
    etf = _snippet(text, r"Early Termination\s*Charges?(?: \([^)]*\))*(?: \(see footnote \d+\))?\s*:?",
                   [r"Security Deposit", r"Any Other Fees", r"Late Payment"], 600)
    if etf:
        t["etf_text"] = etf
        if by_dw := _by_dwelling(etf):
            t["etf_by_dwelling"] = by_dw
            t["early_termination_fee_sgd"] = by_dw.get("hdb4", next(iter(by_dw.values())))
            return _rest(text, t)
        sched = [
            {"from_month": int(a), "to_month": int(b), "fee_sgd": float(fee)}
            for fee, a, b in re.findall(
                r"S?\$\s?(\d+(?:\.\d{2})?) if termination is (?:before or )?within (?:the )?" + ORDINAL
                + r" (?:to|-) " + ORDINAL + r" month", etf)
        ]
        if sched:
            t["etf_schedule"] = sched
            t["early_termination_fee_sgd"] = sched[0]["fee_sgd"]
        elif re.search(r"\b(not applicable|nil|no early termination|waived)\b", etf, re.I):
            t["early_termination_fee_sgd"] = 0.0
        elif m := re.search(r"S?\$\s?(\d+(?:\.\d{2})?)", etf):
            t["early_termination_fee_sgd"] = float(m.group(1))
    return _rest(text, t)


def _rest(text: str, t: dict) -> dict:
    kind = (re.search(r"FACT SHEET FOR (NON-STANDARD|STANDARD) PRICE PLAN", text, re.I)
            or re.search(r"Type of Price Plan \(see footnote \d+\)\s*:?\s*(Non-Standard|Standard)\b", text, re.I))
    if kind:
        t["standard"] = kind.group(1).upper() == "STANDARD"
    dep = _snippet(text, r"Security Deposit \(see footnote \d+\)\s*:?", [r"Any Other Fees", r"\bD\.\s"])
    if dep:
        t["security_deposit_text"] = dep
        t["deposit_waived"] = bool(re.match(r"(waived|not applicable|nil)\b", dep, re.I))
        if by_dw := _by_dwelling(dep):
            t["deposit_by_dwelling"] = by_dw
    if late := _snippet(text, r"Late Payment Charge\s*:?", [r"Early Termination", r"Company Registration", r"Security"], 160):
        t["late_payment_text"] = late
    if ren := _snippet(text, r"Automatic Renewal of Contract \(see footnote \d+\)\s*:?",
                       [r"Advanced Meter", r"Direct Billing", r"C\.\s"], 360):
        t["auto_renewal_text"] = ren
        t["auto_renews"] = ren.lower().startswith("yes")
    if dur := re.search(r"Contract Duration\s*:?\s*(\d+)\s*month", text, re.I):
        t["contract_months_factsheet"] = int(dur.group(1))
    return t
