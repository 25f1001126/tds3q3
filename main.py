from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dateutil import parser
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvoiceRequest(BaseModel):
    invoice_text: str


def find_money(patterns, text):
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            value = m.group(1)
            value = value.replace(",", "")
            try:
                return float(value)
            except:
                pass
    return None


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/extract")
def extract(req: InvoiceRequest):

    text = req.invoice_text

    invoice_no = None
    date = None
    vendor = None
    amount = None
    tax = None
    currency = None

    # ---------------- Invoice Number ----------------

    patterns = [
        r"Invoice\s*No[:#]?\s*([A-Za-z0-9\-\/]+)",
        r"Invoice\s*#\s*([A-Za-z0-9\-\/]+)",
        r"Inv(?:oice)?\s*No[:#]?\s*([A-Za-z0-9\-\/]+)"
    ]

    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            invoice_no = m.group(1).strip()
            break

    # ---------------- Vendor ----------------

    m = re.search(r"Vendor\s*:\s*(.+)", text, re.I)
    if m:
        vendor = m.group(1).strip()

    # ---------------- Date ----------------

    m = re.search(r"Date\s*:\s*(.+)", text, re.I)
    if m:
        try:
            date = parser.parse(m.group(1).strip(), dayfirst=True).date().isoformat()
        except:
            date = None

    # ---------------- Currency ----------------

    if re.search(r"\bRs\.?|\bINR\b|₹", text, re.I):
        currency = "INR"
    elif "$" in text:
        currency = "USD"
    elif "EUR" in text or "€" in text:
        currency = "EUR"

    # ---------------- Amount ----------------

    amount = find_money([
        r"Subtotal\s*:\s*(?:Rs\.?|₹|INR)?\s*([\d,]+\.\d+)",
        r"Sub\s*Total\s*:\s*(?:Rs\.?|₹|INR)?\s*([\d,]+\.\d+)"
    ], text)

    # ---------------- Tax ----------------

    tax = find_money([
        r"GST.*?:\s*(?:Rs\.?|₹|INR)?\s*([\d,]+\.\d+)",
        r"Tax.*?:\s*(?:Rs\.?|₹|INR)?\s*([\d,]+\.\d+)",
        r"VAT.*?:\s*(?:Rs\.?|₹|INR)?\s*([\d,]+\.\d+)"
    ], text)

    return {
        "invoice_no": invoice_no,
        "date": date,
        "vendor": vendor,
        "amount": amount,
        "tax": tax,
        "currency": currency,
    }
