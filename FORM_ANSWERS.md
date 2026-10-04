# CentrAlign AI — Google Form Answers

## 1. Demo Video Link
```
https://github.com/ayushkumar1316/autonomous-ai-task-worker/blob/main/demo.mp4
```

---

## 2. In 3–5 sentences, what did you build?

I built an autonomous AI task worker that turns a natural-language business objective into completed, verified work. Given a goal like "find the latest invoice from Company X, extract the amount and due date, enter it into our internal system, and tell me once it is done," the system uses an LLM (Groq `openai/gpt-oss-20b`) to understand the goal and plan the action sequence, drives a real Chromium browser via Playwright to navigate a local invoice portal and read the DOM, then executes each step — search, extract, enter, verify — with confidence-scored retry and permanent-failure abort. Every step logs model-generated reasoning (`WHY:` lines) so the decision-making is inspectable. A cron-style scheduler allows the same worker to run recurring tasks against a shared browser instance. The scope is deliberately narrow: one task type that genuinely works end-to-end, rather than many mocked capabilities.

---

## 3. Briefly explain your architecture

The agent is a five-module pipeline in Python. `main.py` holds the CLI and the agent loop (Understand → Plan → Execute → Observe → Adapt → Verify → Complete) plus retry logic. `agent_core.py` owns the LLM decisions: `understand_goal()` extracts company/fields/task-type as JSON, `plan_actions()` returns an ordered action list with reasoning and expected outcome, and a plan validator repairs incomplete plans by forcing the full five-step pipeline. `llm_client.py` is a stdlib-only HTTP client for Groq and OpenRouter (no SDK dependency) with browser-User-Agent spoofing to satisfy Groq's edge and a `reasoning`-field fallback for reasoning models. `executor.py` dispatches the five tools (navigate, search, extract, enter, verify) and holds the simulated invoice portal and internal system; it accepts either a real `PlaywrightBrowser` or the deterministic `BrowserSimulator` so the loop runs with or without a browser. `browser_tools.py` runs `portal/invoices.html` over a local HTTP server (port 0 → OS-assigned) and drives real Chromium navigation, search-box input, and DOM row reads; one browser instance is created per process and reused across scheduler runs to avoid Sync-API/asyncio conflicts and port collisions. `scheduler.py` provides cron-style rules (`once`, `interval`, `daily`, `hourly`) and multi-task orchestration. `.env` is loaded via a dependency-free loader and never committed.

---

## 4. What parts of your system are genuinely autonomous?

Three things decide themselves without step-by-step instructions. First, **goal understanding**: the LLM parses the raw natural-language objective and extracts the company, the required data fields, and the task type — no regex, no user-supplied parameters beyond the sentence itself. Second, **action planning**: the LLM produces the ordered action sequence and the reasoning behind it; the validator only enforces the required pipeline shape, it does not dictate the order's justification. Third, **per-step reasoning**: before executing each action the system asks the LLM to state why that action is being taken given the current context, and those `WHY:` lines are emitted at runtime rather than scripted. Beyond that, the retry/adapt layer decides autonomously whether to retry (confidence ≥ 0.3) or abort (< 0.3), and the browser autonomously reads live DOM state to determine which invoice is latest rather than being handed one.

---

## 5. What is currently hard-coded or manually configured?

Honest list: the five-step pipeline shape (navigate → search → extract → enter → verify) is enforced, and the plan validator will repair any LLM plan that omits steps — so while the LLM supplies the plan, the required shape is not itself inferred. The five tool implementations are hard-wired; there is no dynamic tool discovery. The invoice portal is a static local HTML page with a fixed dataset (three companies), so "which system to operate" is a configuration, not a discovery. Retry policy (threshold 0.3, single retry) is a fixed constant rather than an LLM judgement call. Model choice, temperature, and token budgets are set in code/config rather than selected per task. The internal system is a local dict-backed store, not a real integration. Scheduler rules are passed via CLI flags.

---

## 6. What models, frameworks, APIs, libraries, AI coding tools, or existing projects did you use?

**Model:** Groq-hosted `openai/gpt-oss-20b` (OpenAI-compatible chat completions), with `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`, and `allam-2-7b` registered as alternates. OpenRouter (`meta-llama/llama-3.3-70b-instruct:free`) is supported behind the same client.

**Frameworks/libraries:** Python 3.10+ standard library only for the agent itself — `urllib.request` for the LLM HTTP calls, `http.server` for the local portal, `dataclasses`/`typing`/`json`/`re` for the agent model. `Playwright` (Chromium) for real browser automation. `Pillow` and `ffmpeg` were used only to generate the demo video from real terminal output — they are not part of the runtime.

**Deliberately not used:** LangChain, LlamaIndex, any agent framework, the OpenAI/Anthropic SDKs, and any web framework. The agent loop is ~40 readable lines, which mattered more for a technical walkthrough than framework ergonomics.

**AI coding tools:** Claude Code was used for authoring and debugging, in line with the JD's explicit statement that AI coding tools are welcome. No pre-built agent templates or third-party project scaffolding were used; all components were written for this submission.

---

## 7. What is the biggest technical limitation of your current solution?

Reliability under real-world variability. The portal is a static local page with a known layout, so the browser step succeeds deterministically — there is no handling for a changing DOM, a login wall, a CAPTCHA, a slow or failing network, or a site that restructures its markup. In production the search step would need DOM-locating strategies (role/label selectors, fallbacks, and screenshots on failure) and the plan loop would need to detect and recover from layout drift rather than assuming the selector still resolves. Compounding this, the system has no persistent memory: nothing is carried between runs, so an AI employee that encounters a new company state cannot learn it. There is also no auth layer and no audit trail beyond the in-process log, and the internal system is a local in-memory dict rather than a real integration with idempotency or transaction guarantees.

---

## 8. If you had another 2 weeks, what would you build/change next?

First, **real-world robustness**: swap the static portal for a set of heterogeneous mock applications with intentionally varying DOM structures, and add DOM-drift detection with screenshot-on-failure and a recovery loop — that is the actual hard problem and where most of the value lies. Second, **persistent company memory**: store per-company portal knowledge (selectors, procedures, past outcomes) in SQLite so the agent improves run over run and stops re-discovering the same layout each time. Third, **evaluation harness**: a task suite with ground-truth assertions (correct invoice selected, entry verified, evidence returned) and automated regression runs in CI, so reliability is measured rather than asserted. Fourth, **human-in-the-loop approval gates** for irreversible actions, with an approval channel and an audit log of every tool call. Fifth, **a second task type** (expense report or onboarding) to prove the planner generalises across workflows, not just across companies. Finally, I would move the LLM judgement call to the adapt step — replacing the fixed 0.3 confidence threshold with the model itself deciding whether to retry, switch strategy, or ask the user.

---

## Final Declaration Checklist

- [x] I built and understand the submission I am providing.
- [x] I have disclosed significant pre-built components/templates used.
- [x] I have disclosed the AI coding tools used.
- [x] I have not included confidential data or unauthorized access to third-party systems.
- [x] I am comfortable walking through, debugging, and modifying my submission during a technical interview.
