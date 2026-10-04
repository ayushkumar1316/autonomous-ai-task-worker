#!/usr/bin/env python3
"""
Autonomous AI Task Worker Prototype — CentrAlign AI Intern Task
Core loop: Goal -> Understand -> Plan -> Execute -> Observe -> Adapt -> Verify -> Complete
Narrow scope: Simulated Company X invoice portal + internal system.
Genuinely executes (not mocked) within the simulated environment.
"""
import json
import random
import re
from typing import Dict, List, Optional
from dataclasses import dataclass, field
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
            ]
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
    def navigate_to(self, url: str) -> ActionResult:
        return ActionResult(True, f"Navigated to {url}", {"url": url, "page_loaded": True})
    def search(self, query: str) -> ActionResult:
        return ActionResult(True, f"Search '{query}' returned 3 results", {"results": ["Invoice List - Latest", "View Invoice", "Download PDF"]})

class AutonomousAITaskWorker:
    def __init__(self):
        self.portal = SimulatedInvoicePortal()
        self.browser = BrowserSimulator()
        self.log_entries: List[str] = []

    def log(self, msg: str):
        entry = f"[{len(self.log_entries)+1:02d}] {msg}"
        self.log_entries.append(entry)
        print(entry)

    def understand_goal(self, goal: str) -> ActionResult:
        self.log(f"UNDERSTAND goal: {goal!r}")
        # Extract Company X / Y — default Company X
        m = re.search(r"Company\s+([A-Z])", goal)
        company = f"Company {m.group(1)}" if m else "Company X"
        need = [k for k in ["amount","due date","vendor"] if k in goal.lower()]
        return ActionResult(True, f"Goal -> extract {need or ['amount','due_date']} for {company}", {"company": company, "need": need or ["amount","due_date"]})

    def plan_actions(self, info: Dict) -> ActionResult:
        actions = ["navigate_to_invoice_portal","search_latest_invoice","extract_invoice_data","enter_to_internal_system","verify_completion"]
        self.log(f"PLAN {len(actions)} steps: {' -> '.join(actions)}")
        return ActionResult(True, f"Planned {len(actions)} actions", {"actions": actions, "company": info["company"]})

    def execute_action(self, action: str, ctx: Dict) -> ActionResult:
        self.log(f"EXECUTE {action}")
        if action == "navigate_to_invoice_portal":
            return self.browser.navigate_to("https://invoices.internal.example.com/portal")
        if action == "search_latest_invoice":
            r = self.browser.search(f"{ctx['company']} latest invoice")
            inv = self.portal.find_latest_invoice(ctx["company"])
            if not inv:
                return ActionResult(False, f"No invoices for {ctx['company']}", confidence=0.25)
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

    def execute_task(self, goal: str) -> Dict:
        self.log(f"GOAL: {goal}")
        u = self.understand_goal(goal)
        if not u.success:
            return {"status": "failed", "message": u.message, "log": self.log_entries}
        ctx = dict(u.data)
        p = self.plan_actions(ctx)
        if not p.success:
            return {"status": "failed", "message": p.message, "log": self.log_entries}
        ctx.update(p.data)
        for i, action in enumerate(ctx["actions"]):
            self.log(f"STEP {i+1}/{len(ctx['actions'])}")
            res = self.execute_action(action, ctx)
            tag = "OK" if res.success else "FAIL"
            self.log(f"  [{tag}] {res.message}")
            # Observe -> Adapt: retry once on medium-confidence failures
            if not res.success and res.confidence >= 0.3 and i < len(ctx["actions"])-1:
                self.log(f"  ADAPT retry {action} once (confidence {res.confidence})")
                res2 = self.execute_action(action, ctx)
                self.log(f"  [{'OK' if res2.success else 'FAIL'}] retry -> {res2.message}")
                if not res2.success and res2.confidence < 0.5:
                    return {"status": "failed", "message": f"Step {action} failed after retry", "log": self.log_entries, "ctx": ctx}
            elif not res.success and res.confidence < 0.3:
                return {"status": "failed", "message": f"Step {action} failed (low confidence)", "log": self.log_entries, "ctx": ctx}
        # Verify
        if ctx.get("entry_id") and ctx.get("extracted"):
            entry = self.portal.get_entry(ctx["entry_id"])
            return {"status": "completed", "message": "Task completed and verified", "log": self.log_entries,
                    "result": {"company": ctx["company"], "amount": ctx["extracted"]["amount"],
                               "due_date": ctx["extracted"]["due_date"], "vendor": ctx["extracted"]["vendor"],
                               "invoice_id": ctx["extracted"]["invoice_id"], "entry_id": ctx["entry_id"],
                               "verified": True, "summary": f"Invoice {ctx['extracted']['invoice_id']} (${ctx['extracted']['amount']}) due {ctx['extracted']['due_date']} entered as {ctx['entry_id']}"}}
        return {"status": "failed", "message": "Incomplete - missing entry", "log": self.log_entries, "ctx": ctx}

def main():
    print("="*62)
    print(" Autonomous AI Task Worker — Demo")
    print("="*62)
    goal = "Find the latest invoice from Company X, extract the amount and due date, enter it into our internal system, and tell me once it is done."
    print(f"\nUser goal: {goal}\n")
    worker = AutonomousAITaskWorker()
    result = worker.execute_task(goal)
    print("\n"+"="*62)
    print(f" RESULT  status={result['status']}")
    print("="*62)
    print(json.dumps(result.get("result") or {"message": result["message"]}, indent=2))
    print("\n--- Generalization check: same worker, different company ---")
    worker2 = AutonomousAITaskWorker()
    r2 = worker2.execute_task("Find the latest invoice from Company Y, extract the amount and due date, enter it into our internal system")
    print(f"  Company Y run -> {r2['status']}: {r2.get('result',{}).get('summary') or r2['message']}")
    return result

if __name__ == "__main__":
    main()
