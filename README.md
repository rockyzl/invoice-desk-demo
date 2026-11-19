# Invoice Desk

[Open the interactive portfolio demo](https://rockyzl.github.io/invoice-desk-demo/)

Invoice Desk illustrates how a finance team can compare a supplier invoice with its purchase order and warehouse receipt, review a quantity discrepancy, and prepare a purchase invoice draft.

- **Public demo** uses synthetic records, scripted document extraction and review steps, and sample draft IDs. Try the $240 mismatch, a clean match, and a duplicate.
- **Local sandbox test** used ERPNext's Purchase Invoice REST API to create and read back a $2,160 draft after review. A retry returned the same record. [See the recorded test](https://rockyzl.github.io/invoice-desk-demo/#proof).

## Run the preview

Open `docs/index.html` in a browser. The preview also works on any static host.

## Reproduce the ERPNext test

1. Start a dedicated local ERPNext instance using the [official Frappe Docker demo](https://github.com/frappe/frappe_docker#try-on-your-environment). The included seed expects site `frontend`. Bind the installer’s frontend port to `127.0.0.1:18781` and set sandbox-specific passwords.
2. Send `seed_erpnext.py` to `env/bin/python -` in the ERPNext backend container. Store the final JSON line printed by the script in a local credentials file with restricted permissions.
3. Run `python3 sandbox_server.py --settings /path/to/local-credentials.json` and open `http://127.0.0.1:18782/`. Select **Mismatch**, request the corrected invoice, then approve it to test the writeback.

The bridge is loopback-only. It accepts the two fixed, synthetic invoice fixtures and checks the saved document’s amount and draft status. ERP credentials belong outside this repository. Production email intake, document extraction and finance identity are outside the scope of this prototype.
