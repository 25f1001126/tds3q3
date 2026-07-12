import re
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
    if raw is None: return None
    raw = str(raw).strip().rstrip(".,")
    raw = raw.replace(",", "")
    try: return round(float(raw), 2)
    except ValueError: return None

NUM = r'([\d,]+\.\d{1,2}|[\d,]+)'
CUR_PREFIX = r'(?:Rs\.?|INR|₹|\$|USD|EUR|€|GBP|£)?'

def find_number(text: str, keywords: str) -> Optional[float]:
    pattern = rf'(?:{keywords})(?:[^0-9\n]*?)\s*(?:{CUR_PREFIX})\s*({NUM})'
    matches = re.findall(pattern, text, re.IGNORECASE)
    if matches:
        last_match = matches[-1]
        return clean_number(last_match[-1] if isinstance(last_match, tuple) else last_match)
    return None

def extract_vendor(text: str) -> Optional[str]:
    # Expanded patterns to include Client, Bill To, and common header structures
    patterns = [
        r'(?:Vendor|Sold\s*By|From|Supplier|Company|Client|Bill\s*To)\s*[:\-]\s*([^\n]+)',
        r'^([^\n]+?)\s*(?:—|–|-|\|)\s*(?:Tax\s*)?Invoice'
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m: return m.group(1).strip()
    
    # Fallback to the first line if it doesn't look like a generic header
    first_line = text.splitlines()[0].strip()
    if first_line and not re.match(r'^(invoice|tax invoice|bill)$', first_line, re.IGNORECASE):
        return first_line
    return None

def extract_fields(text: str) -> dict:
    # ... (Keep other helper functions as defined in the previous step)
    return {
        "invoice_no": None, # (Implement per previous step)
        "date": None,       # (Implement per previous step)
        "vendor": extract_vendor(text),
        "amount": find_number(text, r'Sub\s*Total|Subtotal|Net\s*Amount|Amount\s*before\s*tax'),
        "tax": find_number(text, r'IGST|CGST|SGST|GST|VAT|Tax'),
        "currency": None    # (Implement per previous step)
    }

@app.post("/extract")
def extract(payload: InvoiceIn):
    return extract_fields(payload.invoice_text)
