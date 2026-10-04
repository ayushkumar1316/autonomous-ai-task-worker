"""Action executor - implements the actual tool operations."""
import json
import random
import re
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


@dataclass
class ActionResult:
    success: bool
    message: str
    data: Dict = None
    confidence: float = 1.0
    verification_needed: bool = False


class SimulatedInvoicePortal:
    """Simulated company invoice portal + internal system."""
    def __init__(self):
        self.invoices = {
            "Company X": [
                {"id": "INV-2024-001", "amount": 15000.00, "due_date": "2024-12-15", "date": "2024-11-01", "vendor": "Tech Solutions Ltd"},
                {"id": "INV-2024-002", "amount": 25000.00, "due_date": "2024-12-20", "date": "2024-11-15", "vendor": "Global Services Inc"},
                {"id": "INV-2024-003", "amount": 8500.00,  "due_date": "2024-12-10", "date": "2024-11-20", "vendor": "Digital Innovations"},
                {"id": "INV-2024-004", "amount": 45000.00, "due_date": "2024-12-25", "date": "2024-11-25", "vendor": "Enterprise Corp"},
            ],
            "Company Y": [
                {"id": "INV-Y-001", "amount": 12000.00, "due_date": "2024-12-18", "date": "2024-11-10", "vendor": "Alpha Corp"},
            ],
            "Company Z": [
                {"id": "INV-Z-001", "amount": 50000.00, "due_date": "2024-12-30", "date": "2024-11-28", "vendor": "Omega Industries"},
            ],
        }
        self.system_data: Dict[str, Dict] = {}
        self._next_entry = 1

    def find_latest_invoice(self, company: str) -> Optional[Dict]:
        lst = self.invoices.get(company)
        if not lst:
            return None
        return max(lst, key=lambda x: x["date"])

    def extract_invoice_data(self, invoice: Dict) -> Dict:
        return {"amount": invoice["amount"], "due_date": invoice["due_date"],
                "vendor": invoice["vendor"], "invoice_id": invoice["id"], "date": invoice["date"]}

    def enter_to_internal_system(self, invoice_data: Dict) -> Optional[str]:
        if not invoice_data.get("amount") or not invoice_data.get("due_date"):
            return None
        entry_id = f"ENTRY-{self._next_entry:04d}"
        self._next_entry += 1
        self.system_data[entry_id] = {**invoice_data, "status": "verified", "entered_by": "AI_Task_Worker"}
        return entry_id

    def get_entry(self, entry_id: str) -> Optional[Dict]:
        return self.system_data.get(entry_id)


class BrowserSimulator:
    """Simulated browser operations."""
    def navigate_to(self, url: str) -> ActionResult:
        return ActionResult(True, f"Navigated to {url}", {"url": url, "page_loaded": True})

    def search(self, query: str) -> ActionResult:
        return ActionResult(True, f"Search '{query}' returned 3 results", {"results": ["Invoice List - Latest", "View Invoice", "Download PDF"]})


class ActionExecutor:
    """Executes actions using available tools.

    Pass a real PlaywrightBrowser to run against the live portal, or omit it
    to use the deterministic BrowserSimulator (no browser, no deps).
    """

    def __init__(self, browser=None):
        self.portal = SimulatedInvoicePortal()
        self.browser = browser if browser is not None else BrowserSimulator()
        self.mode = type(self.browser).__name__

    def execute_action(self, action: str, ctx: Dict) -> ActionResult:
        if action == "navigate_to_invoice_portal":
            company = ctx.get("company", "Company X")
            url = f"https://invoices.{company.lower().replace(' ', '')}.example.com/portal"
            return self.browser.navigate_to(url)

        if action == "search_latest_invoice":
            company = ctx.get("company", "Company X")
            r = self.browser.search(f"{company} latest invoice")
            results = r.data.get("results") if isinstance(r.data, dict) else None
            # Only treat as browser rows when every entry is a dict with a date key.
            # BrowserSimulator returns plain strings, which must fall through to the portal.
            if (isinstance(results, list) and results
                    and all(isinstance(x, dict) and "date" in x for x in results)):
                rows = results
                latest = max(rows, key=lambda x: x.get("date") or "")
                ctx["found_invoice"] = {
                    "id": latest.get("id"), "company": latest.get("company"),
                    "vendor": latest.get("vendor"), "amount": float(latest.get("amount") or 0),
                    "due_date": latest.get("due_date"), "date": latest.get("date"),
                }
                return ActionResult(True, f"Browser found {latest.get('id')} amount=${latest.get('amount')} vendor={latest.get('vendor')}",
                                   {"invoice": ctx["found_invoice"], "source": "browser"})
            inv = self.portal.find_latest_invoice(company)
            if not inv:
                return ActionResult(False, f"No invoices for {company}", confidence=0.25)
            ctx["found_invoice"] = inv
            return ActionResult(True, f"Found {inv['id']} amount=${inv['amount']} vendor={inv['vendor']}", {"invoice": inv})

        if action == "extract_invoice_data":
            inv = ctx.get("found_invoice")
            if not inv:
                return ActionResult(False, "No invoice to extract", confidence=0.2)
            data = self.portal.extract_invoice_data(inv)
            ctx["extracted"] = data
            return ActionResult(True, f"Extracted amount=${data['amount']} due={data['due_date']} vendor={data['vendor']}", data, verification_needed=True)

        if action == "enter_to_internal_system":
            data = ctx.get("extracted")
            if not data:
                return ActionResult(False, "No extracted data", confidence=0.3)
            eid = self.portal.enter_to_internal_system(data)
            if not eid:
                return ActionResult(False, "Validation failed on entry", confidence=0.4)
            ctx["entry_id"] = eid
            return ActionResult(True, f"Entered to internal system as {eid}", {"entry_id": eid})

        if action == "verify_completion":
            eid = ctx.get("entry_id")
            entry = self.portal.get_entry(eid) if eid else None
            if entry and entry["status"] == "verified":
                return ActionResult(True, f"Verified {eid} — status=verified", {"entry": entry, "verified": True})
            return ActionResult(False, "Entry not verified", confidence=0.4)

        return ActionResult(False, f"Unknown action {action}", confidence=0.0)
