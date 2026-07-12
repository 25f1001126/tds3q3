import re
from datetime import datetime
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dateutil import parser as dateparser

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvoiceIn(BaseModel):
    invoice_text: str


def clean_number(raw: str) -> Optional[float]:
    if raw is None:
        return None
    raw = raw.strip().rstrip(".,")
    raw = raw.replace(",", "")
    try:
        return round(float(raw), 2)
    except ValueError:
        return None


NUM = r'([\d,]+\.\d{1,2}|[\d,]+)'
CUR_PREFIX = r'(?:Rs\.?|INR|₹|\$|USD|EUR|€|GBP|£)?'


def find_number(text: str, keywords: str) -> Optional[float]:
    pattern = rf'(?:{keywords})\s*(?:\([^)]*\))?\s*[\.:\-\s]*\s*{CUR_PREFIX}\s*{NUM}'
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        return clean_number(m.group(1))
    return None


def extract_invoice_no(text: str) -> Optional[str]:
    patterns = [
        r'(?:Invoice\s*(?:No|Number|#)\.?|Inv\.?\s*No\.?|Bill\s*No\.?|Ref(?:erence)?\.?(?:\s*No\.?)?)\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9/\-]{2,})',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            val = re.sub(r'[.,;]+$', '', val)
            return val
    return None


def extract_date(text: str) -> Optional[str]:
    patterns = [
        r'(?:Invoice\s*Date|Date|Issued|Dated)\s*[:\-]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2})',
        r'(?:Invoice\s*Date|Date|Issued|Dated)\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})',
        r'(?:Invoice\s*Date|Date|Issued|Dated)\s*[:\-]?\s*([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})',
        r'(?:Invoice\s*Date|Date|Issued|Dated)\s*[:\-]?\s*([A-Za-z]+\s+[0-9]{1,2},?\s+[0-9]{4})',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            raw = m.group(1)
            try:
                dt = dateparser.parse(raw, dayfirst=True, yearfirst=('-' in raw and raw.index('-') < 4))
                return dt.strftime('%Y-%m-%d')
            except (ValueError, OverflowError):
                continue
    return None


def extract_vendor(text: str) -> Optional[str]:
    m = re.search(r'(?:Vendor|Sold\s*By|From|Supplier|Company)\s*[:\-]\s*([^\n]+)', text, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    first_line = text.strip().splitlines()[0].strip() if text.strip() else ""
    if first_line:
        for sep in ['—', ' - ', '–']:
            if sep in first_line:
                candidate = first_line.split(sep)[0].strip()
                if candidate and not re.match(r'^(invoice|tax invoice|bill)$', candidate, re.IGNORECASE):
                    return candidate
        if not re.match(r'^(invoice|tax invoice|bill)\b', first_line, re.IGNORECASE):
            return first_line
    return None


def extract_currency(text: str) -> Optional[str]:
    m = re.search(r'Currency\s*[:\-]\s*([A-Za-z]{3})', text, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    if re.search(r'Rs\.?|₹|INR', text):
        return 'INR'
    if re.search(r'\$|USD', text):
        return 'USD'
    if re.search(r'€|EUR', text):
        return 'EUR'
    if re.search(r'£|GBP', text):
        return 'GBP'
    return None


def extract_fields(text: str) -> dict:
    invoice_no = extract_invoice_no(text)
    date = extract_date(text)
    vendor = extract_vendor(text)
    currency = extract_currency(text)

    amount = find_number(text, r'Sub\s*Total|Subtotal|Net\s*Amount|Amount\s*before\s*tax')
    tax = find_number(text, r'IGST|CGST|SGST|GST|VAT|Tax')
    total = find_number(text, r'Total\s*Due|Grand\s*Total|Total\s*Amount|Total')

    if amount is None and total is not None and tax is not None:
        amount = round(total - tax, 2)
    if tax is None and total is not None and amount is not None:
        tax = round(total - amount, 2)

    return {
        "invoice_no": invoice_no,
        "date": date,
        "vendor": vendor,
        "amount": amount,
        "tax": tax,
        "currency": currency,
    }


@app.post("/extract")
def extract(payload: InvoiceIn):
    return extract_fields(payload.invoice_text)


@app.get("/")
def root():
    return {"status": "ok", "endpoint": "POST /extract"}
