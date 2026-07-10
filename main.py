import re
from dateutil import parser

def extract_invoice(text):
    result = {
        "invoice_no": None,
        "date": None,
        "vendor": None,
        "amount": None,
        "tax": None,
        "currency": None,
    }

    # ---------------- Invoice number ----------------
    patterns = [
        r"Invoice\s*(?:No|Number)?\s*[:#]?\s*([A-Za-z0-9\-\/]+)",
        r"Ref\s*[:#]?\s*([A-Za-z0-9\-\/]+)",
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            result["invoice_no"] = m.group(1).strip()
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
    ]

    for p in vendor_patterns:
        m = re.search(p, text, re.I)
        if m:
            result["vendor"] = m.group(1).strip()
            break

    # Fallback: first non-empty line that isn't INVOICE/TAX INVOICE
    if result["vendor"] is None:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.upper() in ["INVOICE", "TAX INVOICE"]:
                continue
            if "invoice" in line.lower():
                continue
            result["vendor"] = line
            break

    # ---------------- Currency ----------------
    m = re.search(r"Currency\s*:\s*([A-Z]{3})", text, re.I)
    if m:
        result["currency"] = m.group(1)
    elif "Rs" in text or "₹" in text:
        result["currency"] = "INR"

    # helper
    def num(s):
        return float(s.replace(",", ""))

    # ---------------- Amount (Subtotal) ----------------
    m = re.search(r"Subtotal.*?([\d,]+\.\d+)", text, re.I)
    if m:
        result["amount"] = num(m.group(1))

    # ---------------- Tax ----------------
    tax = 0.0

    # Sum ALL GST/CGST/SGST/IGST/VAT lines
    for m in re.finditer(
        r"(?:CGST|SGST|IGST|GST|VAT)[^\d]*([\d,]+\.\d+)",
        text,
        re.I,
    ):
        tax += num(m.group(1))

    if tax > 0:
        result["tax"] = tax

    return result
