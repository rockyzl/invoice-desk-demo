"""Serve the portfolio preview and write fixture drafts to the local ERPNext site."""
import argparse
import json
import os
import sys
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.error import URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

SITE = Path(__file__).resolve().parent / "docs"
STATE = Path.home() / ".local" / "state" / "invoice-desk"
HOST = "127.0.0.1"
PORT = 18782
ERP_URL = os.environ.get("INVOICE_ERP_URL", "http://127.0.0.1:18781").rstrip("/")
ERP_BROWSER_URL = "http://127.0.0.1:18781"
INVOICES = {
    "exception": {"bill_no": "INV-1048-R1", "qty": 90, "rate": 24},
    "clean": {"bill_no": "INV-1052", "qty": 40, "rate": 32},
}
DRAFTS = "/api/resource/Purchase%20Invoice"
draft_lock = Lock()


def erp_request(path, settings, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    with urlopen(Request(ERP_URL + path, data=body, headers={
        "Authorization": f"token {settings['token']}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }), timeout=5) as response:
        return json.load(response)


def write_draft(scenario, settings):
    invoice = INVOICES[scenario]
    supplier = settings["suppliers"][scenario]
    company = settings["company"]
    filters = [
        ["bill_no", "=", invoice["bill_no"]],
        ["supplier", "=", supplier],
        ["company", "=", company],
    ]
    query = urlencode({"filters": json.dumps(filters), "limit_page_length": 2})
    # Check the invoice key before writing. A retry after a lost response reuses the ERP record.
    with draft_lock:
        matches = erp_request(f"{DRAFTS}?{query}", settings)["data"]
        if len(matches) > 1:
            raise ValueError("ERPNext contains multiple records for this fixture.")
        if matches:
            name = matches[0]["name"]
        else:
            payload = {
                "supplier": supplier, "company": company, "currency": "USD",
                "posting_date": "2026-11-19", "bill_date": "2026-11-18",
                "due_date": "2026-12-19", "bill_no": invoice["bill_no"],
                "set_posting_time": 1,
                "items": [{"item_code": "INVOICE-DESK-PART", "qty": invoice["qty"], "rate": invoice["rate"]}],
            }
            name = erp_request(DRAFTS, settings, payload)["data"]["name"]
        draft = erp_request(f"{DRAFTS}/{quote(name, safe='')}", settings)["data"]
    expected_total = Decimal(invoice["qty"] * invoice["rate"])
    if (draft["docstatus"] != 0 or Decimal(str(draft["grand_total"])) != expected_total
            or draft["supplier"] != supplier or draft["bill_no"] != invoice["bill_no"]):
        raise ValueError("ERPNext draft differs from the approved fixture.")
    return {
        "name": draft["name"],
        "docstatus": draft["docstatus"],
        "total": float(draft["grand_total"]),
        "currency": draft["currency"],
        "reused": bool(matches),
        "url": f"{ERP_BROWSER_URL}/desk/purchase-invoice/{quote(name, safe='')}",
    }


class Handler(BaseHTTPRequestHandler):
    def send_content(self, status, content, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, status, obj):
        self.send_content(status, json.dumps(obj).encode(), "application/json")

    def valid_host(self):
        port = self.server.server_port
        return self.headers.get("Host") in {f"{HOST}:{port}", f"localhost:{port}"}

    def do_GET(self):
        if not self.valid_host():
            self.send_json(403, {"error": "Local server only."})
        elif self.path in {"/", "/index.html"}:
            self.send_content(200, (SITE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/erpnext-draft-proof.png":
            self.send_content(200, (SITE / "erpnext-draft-proof.png").read_bytes(), "image/png")
        elif self.path == "/api/status":
            try:
                reply = erp_request("/api/method/frappe.auth.get_logged_user", self.server.settings())
                self.send_json(200, {"available": reply.get("message") == "invoice-desk@example.test"})
            except (OSError, ValueError):
                self.send_json(200, {"available": False})
        else:
            self.send_json(404, {"error": "Unknown path."})

    def do_POST(self):
        if not self.valid_host() or self.headers.get("Origin") not in {None, "http://" + self.headers["Host"]}:
            self.send_json(403, {"error": "Local server only."})
            return
        if self.path != "/api/drafts" or self.headers.get_content_type() != "application/json":
            self.send_json(404, {"error": "Unknown operation."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 100:
                raise ValueError
            payload = json.loads(self.rfile.read(size))
            scenario = payload.get("scenario") if isinstance(payload, dict) else None
            if not isinstance(scenario, str) or scenario not in INVOICES:
                raise ValueError
        except ValueError:
            self.send_json(400, {"error": "Choose a clean or corrected sample invoice."})
            return
        try:
            result = write_draft(scenario, self.server.settings())
        except (URLError, OSError, ValueError, KeyError) as error:
            print(f"ERPNext writeback could not be verified: {type(error).__name__} {getattr(error, 'code', '')}", file=sys.stderr)
            self.send_json(502, {"error": "ERPNext did not confirm a draft."})
            return
        self.send_json(200, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, default=STATE / "api.json")
    args = parser.parse_args()
    with ThreadingHTTPServer((HOST, PORT), Handler) as server:
        server.settings = lambda: json.loads(args.settings.read_text())
        print(f"Invoice Desk: http://{HOST}:{PORT}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
