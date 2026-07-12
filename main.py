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
    # Ensure raw is a string before calling strip
    raw = str(raw).strip().rstrip(".,")
    raw = raw.replace(",", "")
    try:
        return round(float(raw), 2)
    except ValueError:
        return None

NUM = r'([\d,]+\.\d{1,2}|[\d,]+)'
CUR_PREFIX = r'(?:Rs\.?|INR|₹|\$|USD|EUR|€|GBP|£)?'

def find_number(text: str, keywords: str) -> Optional[float]:
    # Use non-capturing group for the prefix to avoid extra items in the tuple
    pattern = rf'(?:{keywords})(?:[^0-9\n]*?)\s*(?:{CUR_PREFIX})\s*({NUM})'
    matches = re.findall(pattern, text, re.IGNORECASE)
    
    if matches:
        # If regex has one capturing group, matches is a list of strings.
        # If it has multiple, it's a list of tuples. 
        # We access the last match found in the document.
        last_match = matches[-1]
        if isinstance(last_match, tuple):
            return clean_number(last_match[-1])
        return clean_number(last_match)
    return None

def extract_invoice_no(text: str) -> Optional[str]:
    pattern = r'(?:Invoice\s*(?:No|Number|#)\.?|Inv\.?\s*No\.?|Bill\s*No\.?|Ref(?:erence)?\.?(?:\s*No\.?)?)\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9/\-]{2,})'
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip().rstrip(".,;") if m else None

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
            try:
                dt = dateparser.parse(m.group(1), dayfirst=True)
                return dt.strftime('%Y-%m-%d')
            except: continue
    return None

def extract_vendor(text: str) -> Optional[str]:
    m = re.search(r'(?:Vendor|Sold\s*By|From|Supplier|Company)\s*[:\-]\s*([^\n]+)', text, re.IGNORECASE)
    return m.group(1).strip() if m else None

def extract_currency(text: str) -> Optional[str]:
    if re.search(r'Rs\.?|₹|INR', text, re.IGNORECASE): return 'INR'
    if re.search(r'\$|USD', text, re.IGNORECASE): return 'USD'
    if re.search(r'€|EUR', text, re.IGNORECASE): return 'EUR'
    if re.search(r'£|GBP', text, re.IGNORECASE): return 'GBP'
    return None

def extract_fields(text: str) -> dict:
    return {
        "invoice_no": extract_invoice_no(text),
        "date": extract_date(text),
        "vendor": extract_vendor(text),
        "amount": find_number(text, r'Sub\s*Total|Subtotal|Net\s*Amount|Amount\s*before\s*tax'),
        "tax": find_number(text, r'IGST|CGST|SGST|GST|VAT|Tax'),
        "currency": extract_currency(text),
    }

@app.post("/extract")
def extract(payload: InvoiceIn):
    return extract_fields(payload.invoice_text)
