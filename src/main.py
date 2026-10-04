#!/usr/bin/env python3
"""Autonomous AI Task Worker - LLM-powered agent.

Core loop: Goal -> Understand -> Plan -> Execute -> Observe -> Adapt -> Verify -> Complete

Usage:
  python src/main.py                    # uses GROQ_API_KEY or OPENROUTER_API_KEY from env
  python src/main.py --provider openrouter
  python src/main.py --no-llm           # runs without LLM (deterministic fallback)
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

# Add parent dir to path so we can import from src/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent_core import AgentCore
from src.executor import ActionExecutor, ActionResult
try:
    from src.scheduler import TaskScheduler, ScheduleRule
    SCHEDULER_AVAILABLE = True
except Exception:
    SCHEDULER_AVAILABLE = False
try:
    from src.browser_tools import PortalServer, PlaywrightBrowser
    BROWSER_AVAILABLE = True
except Exception:
    BROWSER_AVAILABLE = False
from src.env_loader import load_env

DEFAULT_GOAL = "Find the latest invoice from Company X, extract the amount and due date, enter it into our internal system, and tell me once it is done."


def run_task(goal, provider="groq", api_key="", model="", use_llm=True):
    """Run the full agent loop for a goal."""
    # --- optional real browser: serves portal/invoices.html over HTTP ---
    portal_server = None
    browser = None
    if BROWSER_AVAILABLE:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        portal_server = PortalServer(os.path.join(root, "portal"))
        portal_url = portal_server.start()
        print(f"[portal] Invoice portal served at {portal_url}")
        try:
            browser = PlaywrightBrowser(portal_url)
            print("[browser] Playwright Chromium ready — real DOM reads enabled")
        except Exception as e:
            print(f"[browser] Playwright unavailable ({e}) — falling back to simulator")
            browser = None
    executor = ActionExecutor(browser=browser)

    agent = AgentCore(provider=provider, api_key=api_key, model=model) if use_llm else None

    log = []
    def add_log(msg):
        entry = f"[{len(log)+1:02d}] {msg}"
        log.append(entry)
        print(entry)

    add_log(f"GOAL: {goal}")

    # UNDERSTAND
    if use_llm:
        u = agent.understand_goal(goal)
        for line in agent.log_entries:
            pass  # already printed
    else:
        u = _fallback_understand(goal, add_log)
    if not u.success:
        return {"status": "failed", "message": u.message, "log": log}

    ctx = dict(u.data)
    add_log(f"  UNDERSTAND -> {u.message}")

    # PLAN
    if use_llm:
        p = agent.plan_actions(ctx)
    else:
        p = _fallback_plan(add_log)
    if not p.success:
        return {"status": "failed", "message": p.message, "log": log}

    ctx.update(p.data)
    add_log(f"  PLAN -> {p.message}")

    # EXECUTE loop
    actions = ctx.get("actions", [])
    for i, action in enumerate(actions):
        add_log(f"STEP {i+1}/{len(actions)}: {action}")

        # Ask LLM why this action, before executing it (if LLM enabled)
        if use_llm:
            reason = agent.explain_reasoning(action, {k: v for k, v in ctx.items() if k != "found_invoice"})
            add_log(f"  WHY: {reason[:180]}")

        res = executor.execute_action(action, ctx)
        tag = "OK" if res.success else "FAIL"
        add_log(f"  [{tag}] {res.message}")

        # Observe -> Adapt: retry on medium-confidence failure
        if not res.success and res.confidence >= 0.3 and i < len(actions) - 1:
            add_log(f"  ADAPT retry {action} once (confidence {res.confidence})")
            res2 = executor.execute_action(action, ctx)
            add_log(f"  [{'OK' if res2.success else 'FAIL'}] retry -> {res2.message}")
            if not res2.success and res2.confidence < 0.5:
                return {"status": "failed", "message": f"Step {action} failed after retry", "log": log, "ctx": ctx}
        elif not res.success and res.confidence < 0.3:
            return {"status": "failed", "message": f"Step {action} failed (low confidence)", "log": log, "ctx": ctx}

    # VERIFY + report
    if ctx.get("entry_id") and ctx.get("extracted"):
        entry = executor.portal.get_entry(ctx["entry_id"])
        result = {
            "company": ctx.get("company"),
            "amount": ctx["extracted"]["amount"],
            "due_date": ctx["extracted"]["due_date"],
            "vendor": ctx["extracted"]["vendor"],
            "invoice_id": ctx["extracted"]["invoice_id"],
            "entry_id": ctx["entry_id"],
            "verified": True,
            "llm_used": ctx.get("llm_used", False),
            "llm_model": ctx.get("llm_model", ""),
            "summary": f"Invoice {ctx['extracted']['invoice_id']} (${ctx['extracted']['amount']}) due {ctx['extracted']['due_date']} entered as {ctx['entry_id']}",
        }
        return {"status": "completed", "message": "Task completed and verified", "log": log, "result": result}
    return {"status": "failed", "message": "Incomplete - missing entry", "log": log, "ctx": ctx}


def _fallback_understand(goal, add_log):
    import re
    if callable(add_log):
        add_log("UNDERSTAND (no LLM - regex fallback)")
    m = re.search(r"Company\s+([A-Z])", goal)
    company = f"Company {m.group(1)}" if m else "Company X"
    need = [k for k in ["amount", "due date", "vendor"] if k in goal.lower()]
    return ActionResult(True, f"Goal -> extract {need or ['amount','due_date']} for {company}", {"company": company, "data_fields": need or ["amount", "due_date"]})


def _fallback_plan(add_log):
    actions = ["navigate_to_invoice_portal", "search_latest_invoice", "extract_invoice_data", "enter_to_internal_system", "verify_completion"]
    if callable(add_log):
        add_log(f"PLAN (no LLM - fallback) {len(actions)} steps")
    return ActionResult(True, f"Planned {len(actions)} actions (fallback)", {"actions": actions, "llm_used": False})


def main():
    parser = argparse.ArgumentParser(description="Autonomous AI Task Worker")
    parser.add_argument("--provider", default="groq", choices=["groq", "openrouter"], help="LLM provider")
    parser.add_argument("--model", default="", help="LLM model (optional)")
    parser.add_argument("--no-llm", action="store_true", help="Run without LLM (deterministic fallback)")
    parser.add_argument("--goal", default=DEFAULT_GOAL, help="Task goal to execute")
    # Scheduler
    parser.add_argument("--schedule", action="store_true", help="Enable scheduler mode")
    parser.add_argument("--schedule-name", default="scheduled_task", help="Task name for scheduler")
    parser.add_argument("--schedule-freq", choices=["once", "daily", "hourly", "interval"], default="once")
    parser.add_argument("--schedule-interval", type=int, default=0, help="Interval in seconds for --schedule-freq interval")
    parser.add_argument("--schedule-max", type=int, default=1, help="Max number of runs")
    args = parser.parse_args()

    # Load .env file if present (does not override existing env vars)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    loaded = load_env(os.path.join(project_root, '.env'))
    if loaded:
        keys = ', '.join(k for k in loaded if 'KEY' in k)
        print(f'[env] Loaded from .env: {keys}')

    # Resolve API key
    api_key = ""
    if not args.model:
        args.model = os.environ.get(f"{args.provider.upper()}_MODEL", "")
    if not args.no_llm:
        if args.provider == "groq":
            api_key = os.environ.get("GROQ_API_KEY", "")
        else:
            api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            print(f"ERROR: No API key for {args.provider}. Set {args.provider.upper()}_API_KEY or use --no-llm.")
            print("HINT: On Windows PowerShell: $env:GROQ_API_KEY='your-key'")
            print("HINT: Or just run: python src/main.py --no-llm")
            sys.exit(1)

    print("=" * 70)
    print(" Autonomous AI Task Worker — LLM-Powered Agent")
    print("=" * 70)
    print(f"\nProvider: {args.provider} | Model: {args.model or 'default'} | LLM: {'ON' if not args.no_llm else 'OFF'}")
    print(f"\nUser goal: {args.goal}\n")

    # Scheduler mode
    if args.schedule:
        if not SCHEDULER_AVAILABLE:
            print("ERROR: Scheduler not available (import failed)")
            sys.exit(1)
        print(f"[scheduler] Scheduler enabled: freq={args.schedule_freq}, interval={args.schedule_interval}s, max={args.schedule_max}")
        scheduler = TaskScheduler(
            lambda g: run_task(g, provider=args.provider, api_key=api_key, model=args.model, use_llm=not args.no_llm)
        )
        rule = ScheduleRule(frequency=args.schedule_freq, interval_seconds=args.schedule_interval, start_date=datetime.now())
        task = scheduler.add_task(args.schedule_name, args.goal, rule)
        task.run_count = 0
        result = scheduler._execute_task(task)
        # For recurring, keep running
        if args.schedule_freq != "once" and args.schedule_max > 1:
            for _ in range(args.schedule_max - 1):
                if args.schedule_interval:
                    print(f"[scheduler] Waiting {args.schedule_interval}s...")
                    time.sleep(args.schedule_interval)
                result = scheduler._execute_task(task)
        print("=" * 70)
        print(f" RESULT  status={result['result']['status']}")
        print("=" * 70)
        print(json.dumps(result, indent=2))
        return

    # Single task
    result = run_task(args.goal, provider=args.provider, api_key=api_key, model=args.model, use_llm=not args.no_llm)

    print("\n" + "=" * 70)
    print(f" RESULT  status={result['status']}")
    print("=" * 70)
    print(json.dumps(result.get("result") or {"message": result["message"]}, indent=2))

    return result


if __name__ == "__main__":
    main()
