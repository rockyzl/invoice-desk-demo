"""Seed the Invoice Desk sandbox. Run inside the ERPNext bench with its Python."""
import json
import os

import frappe
from erpnext.setup.setup_wizard.operations import install_fixtures

COMPANY = "Invoice Desk Sandbox"
API_USER = "invoice-desk@example.test"

os.chdir("/home/frappe/frappe-bench/sites")
frappe.init(site="frontend", sites_path=".")
frappe.connect()
frappe.set_user("Administrator")


def ensure(doctype, fields, filters):
    name = frappe.db.exists(doctype, filters)
    if not name:
        name = frappe.get_doc({"doctype": doctype, **fields}).insert().name
    return name


try:
    if not frappe.db.exists("Warehouse Type", "Transit"):
        install_fixtures.install("United States")
    ensure("Company", {
        "company_name": COMPANY, "abbr": "IVD", "country": "United States",
        "default_currency": "USD", "create_chart_of_accounts_based_on": "Standard Template",
    }, COMPANY)
    if not frappe.db.exists("Fiscal Year", "2026"):
        ensure("Fiscal Year", {
            "year": "2026", "year_start_date": "2026-01-01", "year_end_date": "2026-12-31",
        }, "2026")

    if frappe.db.get_single_value("Global Defaults", "default_company") != COMPANY:
        install_fixtures.install_defaults(frappe._dict({
            "company_name": COMPANY, "currency": "USD", "country": "United States",
        }))

    supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
    item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
    if not supplier_group or not item_group:
        raise RuntimeError("Sandbox requires an ERPNext supplier and item group.")
    suppliers = {}
    for key, name in {
        "exception": "Northstar Industrial Supply",
        "clean": "Meridian Parts Co.",
    }.items():
        suppliers[key] = ensure("Supplier", {
            "supplier_name": name, "supplier_group": supplier_group, "supplier_type": "Company",
            "default_currency": "USD",
        }, {"supplier_name": name})
    ensure("Item", {
        "item_code": "INVOICE-DESK-PART", "item_name": "Demo replacement part",
        "item_group": item_group, "stock_uom": "Nos", "is_stock_item": 0,
        "is_purchase_item": 1, "is_sales_item": 0,
        "description": "Synthetic item for the Invoice Desk sandbox",
    }, "INVOICE-DESK-PART")

    ensure("User", {
        "email": API_USER, "first_name": "Invoice Desk", "send_welcome_email": 0,
        "user_type": "System User", "roles": [{"role": "Accounts User"}],
    }, API_USER)
    user = frappe.get_doc("User", API_USER)
    if not user.api_key:
        user.api_key = frappe.generate_hash(length=24)
    secret = user.get_password("api_secret", raise_exception=False)
    if not secret:
        secret = frappe.generate_hash(length=40)
        user.api_secret = secret
    user.save()
    frappe.db.commit()
    print(json.dumps({
        "token": f"{user.api_key}:{secret}",
        "company": COMPANY,
        "suppliers": suppliers,
    }))
finally:
    frappe.destroy()
