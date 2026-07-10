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


def num(s):
    return float(s.replace(",", "").strip())


def extract_invoice(text):
    result = {
        "invoice_no": None,
        "date": None,
        "vendor": None,
        "amount": None,
        "tax": None,
        "currency": None,
    }

    # ---------------- Invoice Number ----------------

    # ---------------- Invoice Number ----------------

    invoice_patterns = [
        r"Invoice\s*(?:No|Number|ID)?\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9/\-]*)",
        r"Invoice\s*#\s*([A-Za-z0-9][A-Za-z0-9/\-]*)",
        r"Ref(?:erence)?\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9/\-]*)",
        r"Document\s*(?:No|ID)?\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9/\-]*)",
    ]
    
    for pat in invoice_patterns:
        m = re.search(pat, text, re.I)
        if m:
            result["invoice_no"] = m.group(1).strip()
            break
    
    # Generic fallback: anything that looks like an invoice id
    if result["invoice_no"] is None:
        candidates = re.findall(
            r"\b[A-Za-z0-9]+(?:[-/][A-Za-z0-9]+){2,}\b",
            text
        )
    
        blacklist = {
            "yyyy-mm-dd",
            "dd-mm-yyyy",
        }
    
        for c in candidates:
            if c.lower() not in blacklist:
                result["invoice_no"] = c
                break

    # ---------------- Date ----------------

    date_patterns = [
        r"Date\s*[:\-]?\s*(.+)",
        r"Issued\s*[:\-]?\s*(.+)",
    ]

    for p in date_patterns:
        m = re.search(p, text, re.I)
        if m:
            try:
                d = parser.parse(m.group(1).strip(), dayfirst=True)
                result["date"] = d.strftime("%Y-%m-%d")
                break
            except:
                pass

    # ---------------- Vendor ----------------

    vendor_patterns = [
        r"Vendor\s*:\s*(.+)",
        r"Supplier\s*:\s*(.+)",
        r"Seller\s*:\s*(.+)",
        r"From\s*:\s*(.+)",
        r"Company\s*:\s*(.+)",
        r"Business\s*:\s*(.+)",
    ]

    for p in vendor_patterns:
        m = re.search(p, text, re.I)
        if m:
            result["vendor"] = m.group(1).strip()
            break

    # Fallback: first meaningful line
    if result["vendor"] is None:
        for line in text.splitlines():
            line = line.strip()

            if not line:
                continue

            low = line.lower()

            if any(x in low for x in [
                "invoice",
                "bill to",
                "client",
                "subtotal",
                "total",
                "gst",
                "igst",
                "cgst",
                "sgst",
                "currency",
                "date",
                "issued",
                "ref",
            ]):
                continue

            result["vendor"] = line
            break

    # ---------------- Currency ----------------

    m = re.search(r"Currency\s*:\s*([A-Z]{3})", text, re.I)
    if m:
        result["currency"] = m.group(1).upper()
    elif "Rs" in text or "₹" in text:
        result["currency"] = "INR"
    elif "$" in text:
        result["currency"] = "USD"

    # ---------------- Amount (Subtotal) ----------------

    subtotal_patterns = [
        r"Subtotal.*?([\d,]+\.\d+)",
        r"Sub\s*Total.*?([\d,]+\.\d+)",
        r"Amount Before Tax.*?([\d,]+\.\d+)",
    ]

    for p in subtotal_patterns:
        m = re.search(p, text, re.I | re.S)
        if m:
            result["amount"] = num(m.group(1))
            break

    # ---------------- Tax ----------------

    tax = 0.0

    for m in re.finditer(
        r"(?:CGST|SGST|IGST|GST|VAT).*?([\d,]+\.\d+)",
        text,
        re.I | re.S,
    ):
        tax += num(m.group(1))

    if tax > 0:
        result["tax"] = tax

    return result


@app.post("/extract")
def extract(req: InvoiceRequest):
    return extract_invoice(req.invoice_text)


@app.get("/")
def root():
    return {"status": "ok"}
