# Autonomous AI Task Worker

**Submission for CentrAlign AI — AI Engineering Intern**

An LLM-powered agent that takes a natural-language business objective and autonomously plans, executes, observes, adapts, and verifies the work — instead of waiting to be told each step.

---

## What changed in v2 (LLM integration)

The v1 prototype had the agent loop but made every decision with regex and a hardcoded plan. v2 replaces that decision layer with a real LLM:

| Layer | v1 | v2 |
|---|---|---|
| **Understand** | Regex to find "Company X" | LLM extracts company, required fields, task type, context |
| **Plan** | Fixed list of 5 actions | LLM produces the action sequence + reasoning + expected outcome, then validated against the required pipeline |
| **Execute** | Same | Same |
| **Reasoning** | None | LLM explains *why* each action is taken, before it is taken |
| **Provider** | N/A | Groq (`openai/gpt-oss-20b`) or OpenRouter, switchable via flag |

The loop itself is unchanged: **Goal → Understand → Plan → Execute → Observe → Adapt → Verify → Complete**.

### Why this matters for the evaluation criteria

- **Autonomy** — the action sequence is now decided by the model, not hardcoded. The user supplies only an outcome.
- **Technical Understanding** — every decision is accompanied by model-generated reasoning, so the walkthrough can show *why*, not just *what*.
- **Reliability** — if the LLM returns a plan missing required steps, the planner detects it and repairs the plan rather than executing an incomplete flow. If the API call fails entirely, it falls back to a deterministic plan so the system still completes.

---

## Quick start

```bash
git clone <your-repo-url>
cd autonomous-ai-task-worker

# No install needed — standard library only for the core agent
python src/main.py --no-llm          # deterministic mode, no API key required
```

### With a real LLM

```bash
cp .env.example .env
# edit .env and paste your key:
#   GROQ_API_KEY=gsk_...
#   (or OPENROUTER_API_KEY=sk-or-...)

python src/main.py                                   # Groq, default model
python src/main.py --provider openrouter             # OpenRouter
python src/main.py --provider groq --model openai/gpt-oss-120b
```

`.env` is git-ignored. `src/env_loader.py` reads it at startup without overriding variables already set in your shell.

### Try a different task

```bash
python src/main.py --goal "Find the latest invoice from Company Y, extract the amount and due date, enter it into our internal system, and tell me once it is done."
```

---

## Architecture

```
src/
├── main.py          CLI entry point, agent loop, retry/adapt logic
├── agent_core.py    LLM-backed understand + plan + explain_reasoning
├── llm_client.py    Groq / OpenRouter HTTP client (urllib only)
├── executor.py      Tool implementations + simulated invoice portal
└── env_loader.py    .env loader (no external deps)

invoice_task.py      v1 standalone agent — kept for comparison
portal/              Local invoice portal (static HTML served via HTTP)
```

### The loop, in code

| Stage | Where | Behaviour |
|---|---|---|
| Understand | `agent_core.understand_goal()` | LLM returns JSON: company, data_fields, task_type, context |
| Plan | `agent_core.plan_actions()` | LLM returns JSON: actions, reasoning, expected_outcome |
| Plan validation | `agent_core.plan_actions()` | Plan shorter than the required pipeline is repaired |
| Execute | `executor.ActionExecutor.execute_action()` | Dispatches to the tool |
| Observe | result of `execute_action()` | `ActionResult` carries success, message, confidence |
| Adapt | `main.run_task()` | Retry once on medium confidence; abort on low |
| Verify | `executor` `verify_completion` | Reads back the internal system entry |
| Explain | `agent_core.explain_reasoning()` | LLM states why the action is being taken |

### Failure handling

`ActionResult` carries a confidence value, which drives the adapt step:

- `confidence >= 0.3` → retry the action once
- `confidence < 0.3` → abort, treat as a permanent failure
- LLM unavailable or returns malformed JSON → fall back to the deterministic plan

---

## Sample run

```
[env] Loaded from .env: GROQ_API_KEY
Provider: groq | Model: default | LLM: ON

[01] GOAL: Find the latest invoice from Company X, extract the amount and due date,
     enter it into our internal system, and tell me once it is done.
[02]   LLM understood: company=Company X, fields=['amount', 'due_date'], type=invoice_extraction
[03] PLAN: Using LLM to plan action sequence
[04]   LLM planned 5 actions
[05]   Reasoning: The user requests extraction of amount and due_date from the latest
       invoice of Company X. The required pipeline mandates navigating to the portal...
[06] STEP 1/5: navigate_to_invoice_portal
[07]   WHY: I'm navigating to the invoice portal so I can access and locate Company X's
       latest invoice, which is the first step required to extract the amount and due date.
[08]   [OK] Navigated to https://invoices.companyx.example.com/portal
[09] STEP 2/5: search_latest_invoice
[10]   WHY: I am searching for the latest invoice from Company X to extract its amount...
[11]   [OK] Found INV-2024-004 amount=$45000.0 vendor=Enterprise Corp
...
[17]   WHY: I am verifying that the internal system has correctly recorded the amount
       and due date for Company X's latest invoice...
[18]   [OK] Verified ENTRY-0001 — status=verified

 RESULT  status=completed
```

---

## CLI Usage

### Single task
```bash
python src/main.py --no-llm                                    # deterministic, no key needed
python src/main.py --provider groq                             # Groq LLM
python src/main.py --provider openrouter                       # OpenRouter
python src/main.py --no-llm --goal "Find the latest invoice from Company Y, extract the amount..."
```

### Real browser (Playwright)
```bash
pip install playwright
python -m playwright install chromium
python src/main.py --no-llm    # real DOM reads against the local portal
```

If Playwright is not installed or fails to start, the agent transparently falls back to the built-in `BrowserSimulator` — the core loop always runs.

### Scheduler (multi-task)
```bash
python src/main.py --no-llm --schedule --schedule-name "daily_invoice" --schedule-freq once
python src/main.py --no-llm --schedule --schedule-name "demo" --schedule-freq interval --schedule-interval 10 --schedule-max 3
python src/main.py --no-llm --schedule --schedule-name "daily" --schedule-freq daily --schedule-max 30
```

Frequencies: `once`, `interval`, `daily`, `hourly`.

---

## Evaluation against the criteria

| Criterion | Where it shows up |
|---|---|
| **Autonomy** | LLM-derived plan from an outcome-only prompt; plan validation + repair |
| **Execution** | Five tools actually run; state mutates in the internal system |
| **Reliability** | Confidence-scored retry, permanent-failure abort, LLM-failure fallback |
| **Verification** | `verify_completion` reads the entry back instead of assuming success |
| **Generalization** | Company X / Y / Z handled by the same code path; verified for X and Y |
| **Engineering Quality** | Module separation, typed dataclasses, single stdlib-based HTTP client, no framework lock-in |
| **Product Thinking** | Input is a business objective, not a step list; output is a verified outcome plus evidence |
| **Technical Understanding** | Every stage logs model-generated reasoning; documented trade-offs below |

---

## Design decisions

**Why a local invoice portal instead of a live site.** The brief allows a sandboxed environment. A local portal keeps the run reproducible and avoids touching third-party systems. `browser_tools.py` serves `portal/invoices.html` over HTTP because `file://` breaks JavaScript in some Chromium builds; Playwright then drives real navigation, fills the search box, and reads DOM rows. Without Playwright, `executor.py` falls back to `BrowserSimulator` and nothing above it changes.

**Why JSON prompts rather than a framework.** No LangChain, no agent SDK. The loop is 40 lines and readable end to end, which matters more for a technical discussion than framework ergonomics would. Structured JSON also means a malformed response is caught by `json.loads` and routed to the fallback, rather than silently producing a bad plan.

**Why plan validation.** An early run had the model return three actions for Company Y, skipping the entry and verification steps, and the task failed at the final check. Rather than trusting the model, the planner now checks the plan against the required pipeline and repairs it. Model output is treated as a proposal, not a command.

**Why retry only once.** Retrying indefinitely hides real failures and makes the demo non-deterministic. One retry on medium confidence, abort on low, is enough to show the adapt path without pretending to be a production retry policy.

**Why a scheduler at all.** An agent that only runs on demand is a script. `scheduler.py` adds cron-style rules and multi-task orchestration so a run can recur and several goals can be queued — the smallest honest step toward "employed" rather than "invoked". It is deliberately single-process and in-memory; a production version would put the queue behind Redis.

**Why `.env` instead of shell exports.** Reviewers cloning the repo should not have to learn PowerShell quoting to run it. `env_loader.py` is ~40 lines and has no dependencies.

---

## Known limitations

1. **Tools are simulated when Playwright is absent.** With Playwright installed the agent drives a real Chromium — navigation, a real search box, and DOM row reads against `portal/invoices.html`. Without it, `BrowserSimulator` returns a constructed response and the loop still completes, so reviewers without Playwright can still run the demo.
2. **Playwright needs system libraries.** Minimal Linux images lack libXdamage, libgbm, libnss3 and friends. `playwright install chromium --with-deps` installs them when sudo is available; otherwise extract the .deb packages and point `LD_LIBRARY_PATH` at them.
2. **One task type.** Invoice processing only. The loop generalises across companies, not across workflows.
3. **Reasoning models need care.** `gpt-oss-*` returns a `reasoning` field alongside `content`; the client falls back to `reasoning` when `content` is empty. Models that spend their whole token budget on reasoning return empty content — `openai/gpt-oss-20b` at `max_tokens` 2048 is a practical default.
4. **No persistent memory.** State lives for one process. Nothing is carried between runs.
5. **No auth, no audit trail.** The internal system accepts any entry.
6. **Single-agent, no parallelism.** Steps are strictly sequential.
7. **Groq blocks default Python clients.** The edge returns `403 error code: 1010` for the stock `urllib` User-Agent; the client sets a browser UA. This is a workaround, noted here because it will look arbitrary otherwise.

---

## Next steps

1. ~~Replace `BrowserSimulator` with Playwright~~ **Done** — real navigation, search input and DOM reads against `portal/invoices.html` served over HTTP.
2. Add a second task type (expense report or onboarding) to prove workflow generalization, not just company generalization.
3. Persist company memory across runs so the agent learns portal layouts.
4. Replace confidence heuristics with an LLM judgement call at the adapt step.
5. Add approval gates for irreversible actions.
6. Structured audit log of every tool call, for compliance use cases.

---

## Assumptions

1. The simulated portal is representative enough to demonstrate the loop; it is not a claim about any real product.
2. Goals are stated in natural language with the company named explicitly.
3. The five-step pipeline is the correct shape for invoice processing; other workflows need different tool sets.
4. A single LLM call per decision is sufficient at this scale.
5. Reviewers have a Groq or OpenRouter key, or run in `--no-llm` mode.
6. No credentials or third-party systems are used anywhere in this repo.

---

## Tech used

**Runtime:** Python 3.10+, standard library only (`urllib`, `json`, `re`, `dataclasses`, `typing`, `pathlib`)

**LLM providers:** Groq (`openai/gpt-oss-20b`), OpenRouter (any chat model)

**Not used:** LangChain, OpenAI SDK, Anthropic SDK, any agent framework, any web framework — deliberately, to keep the loop readable.

**Optional extras:** Playwright (real browser), pytest (tests). See `requirements.txt`.

---

## License

MIT — see `LICENSE`.
