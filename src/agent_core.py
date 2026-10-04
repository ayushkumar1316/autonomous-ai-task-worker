"""Agent core - LLM-powered understanding, planning, execution, verification."""
import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass

from .llm_client import call_llm

# Tool definitions for the agent (passed to LLM)
AGENT_TOOLS = [
    {
        "name": "navigate_to_invoice_portal",
        "description": "Navigate to the company invoice portal",
        "parameters": {"company": "string"},
    },
    {
        "name": "search_latest_invoice",
        "description": "Search for the latest invoice from a specific company",
        "parameters": {"company": "string"},
    },
    {
        "name": "extract_invoice_data",
        "description": "Extract invoice data (amount, due_date, vendor) from an invoice",
        "parameters": {"invoice_id": "string"},
    },
    {
        "name": "enter_to_internal_system",
        "description": "Enter invoice data into the internal system",
        "parameters": {"invoice_data": "object"},
    },
    {
        "name": "verify_completion",
        "description": "Verify that invoice data was successfully entered",
        "parameters": {"entry_id": "string"},
    },
]


@dataclass
class ActionResult:
    success: bool
    message: str
    data: Dict = None
    confidence: float = 1.0
    verification_needed: bool = False


class AgentCore:
    def __init__(
        self,
        provider: str = "groq",
        api_key: str = "",
        model: str = "",
        max_plan_iterations: int = 3,
    ):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.max_plan_iterations = max_plan_iterations
        self.log_entries: List[str] = []

    def log(self, msg: str):
        entry = f"[{len(self.log_entries)+1:02d}] {msg}"
        self.log_entries.append(entry)
        print(entry)

    def understand_goal(self, goal: str) -> ActionResult:
        """Use LLM to understand the user's goal and extract key entities."""
        self.log(f"UNDERSTAND goal: {goal!r}")

        system_prompt = """You are an AI agent that understands natural language task goals for invoice processing.

Extract from the user's goal:
1. company_name: The exact company name mentioned (e.g., "Company X", "Acme Corp")
2. data_fields: List of data fields to extract (e.g., ["amount", "due_date", "vendor"])
3. task_type: Classification of the task (e.g., "invoice_extraction", "invoice_verification")
4. context: Any additional context provided

Return ONLY a JSON object with these fields. No other text."""

        prompt = f"User goal: {goal}"

        result = call_llm(
            prompt=prompt,
            system=system_prompt,
            provider=self.provider,
            api_key=self.api_key,
            model=self.model,
            temperature=0.2,
            max_tokens=500,
        )

        if not result["success"]:
            self.log(f"  LLM call failed: {result['error']}")
            return ActionResult(
                False,
                f"LLM understanding failed: {result['error']}",
                confidence=0.1,
            )

        try:
            # Parse JSON from LLM response
            content = result["content"].strip()
            # Remove markdown code block if present
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            understanding = json.loads(content)

            company = understanding.get("company_name", "Company X")
            data_fields = understanding.get("data_fields", ["amount", "due_date"])
            task_type = understanding.get("task_type", "invoice_extraction")
            context = understanding.get("context", "")

            self.log(f"  LLM understood: company={company}, fields={data_fields}, type={task_type}")

            return ActionResult(
                True,
                f"Goal understood: extract {data_fields} for {company} ({task_type})",
                {
                    "company": company,
                    "data_fields": data_fields,
                    "task_type": task_type,
                    "context": context,
                    "llm_model": result["model"],
                    "llm_latency_ms": result["latency_ms"],
                },
            )

        except json.JSONDecodeError as e:
            self.log(f"  LLM JSON parse error: {e}")
            return ActionResult(
                False,
                f"Failed to parse LLM response as JSON: {result['content'][:200]}",
                confidence=0.2,
            )

    def plan_actions(self, understanding: Dict) -> ActionResult:
        """Use LLM to plan the sequence of actions."""
        self.log("PLAN: Using LLM to plan action sequence")

        system_prompt = """You are an AI agent that plans action sequences for invoice processing tasks.

The invoice processing pipeline ALWAYS requires these 5 actions IN THIS ORDER. Do NOT skip or omit any step, even if the goal seems to only ask for extraction:
1. navigate_to_invoice_portal
2. search_latest_invoice
3. extract_invoice_data
4. enter_to_internal_system
5. verify_completion

Based on the user's goal understanding, plan the optimal sequence of actions using the available tools.

Available tools:
- navigate_to_invoice_portal: Navigate to company invoice portal
- search_latest_invoice: Search for latest invoice from a company
- extract_invoice_data: Extract invoice data (amount, due_date, vendor)
- enter_to_internal_system: Enter invoice data into internal system
- verify_completion: Verify that invoice data was successfully entered

Return ONLY a JSON object with:
1. actions: List of action names in execution order
2. reasoning: Brief explanation of why this sequence was chosen
3. expected_outcome: What success looks like

No other text."""

        prompt = f"""Understanding:
Company: {understanding.get('company', 'Company X')}
Data fields needed: {understanding.get('data_fields', ['amount', 'due_date'])}
Task type: {understanding.get('task_type', 'invoice_extraction')}

Plan the action sequence."""

        result = call_llm(
            prompt=prompt,
            system=system_prompt,
            provider=self.provider,
            api_key=self.api_key,
            model=self.model,
            temperature=0.2,
            max_tokens=800,
        )

        if not result["success"]:
            self.log(f"  LLM planning failed: {result['error']}")
            # Fallback to hardcoded plan
            fallback_actions = [
                "navigate_to_invoice_portal",
                "search_latest_invoice",
                "extract_invoice_data",
                "enter_to_internal_system",
                "verify_completion",
            ]
            self.log(f"  Using fallback plan: {fallback_actions}")
            return ActionResult(
                True,
                f"Planned {len(fallback_actions)} actions (fallback)",
                {
                    "actions": fallback_actions,
                    "reasoning": "Fallback to standard invoice processing pipeline",
                    "llm_used": False,
                },
            )

        try:
            content = result["content"].strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            plan = json.loads(content)
            actions = plan.get("actions", [])
            reasoning = plan.get("reasoning", "")
            expected = plan.get("expected_outcome", "")

            self.log(f"  LLM planned {len(actions)} actions")
            self.log(f"  Reasoning: {reasoning}")
            self.log(f"  Expected: {expected}")

            # Validate: pipeline needs all 5 steps for the invoice task to complete
            REQUIRED = ["navigate_to_invoice_portal", "search_latest_invoice",
                        "extract_invoice_data", "enter_to_internal_system", "verify_completion"]
            if len(actions) < 5:
                self.log(f"  ADAPT plan had only {len(actions)} actions — forcing full 5-step pipeline")
                actions = REQUIRED

            return ActionResult(
                True,
                f"Planned {len(actions)} actions via {result['model']}",
                {
                    "actions": actions,
                    "reasoning": reasoning,
                    "expected_outcome": expected,
                    "llm_used": True,
                    "llm_model": result["model"],
                    "llm_latency_ms": result["latency_ms"],
                },
            )

        except json.JSONDecodeError as e:
            self.log(f"  LLM JSON parse error in planning: {e}")
            # Fallback
            fallback_actions = [
                "navigate_to_invoice_portal",
                "search_latest_invoice",
                "extract_invoice_data",
                "enter_to_internal_system",
                "verify_completion",
            ]
            return ActionResult(
                True,
                f"Planned {len(fallback_actions)} actions (fallback after parse error)",
                {
                    "actions": fallback_actions,
                    "reasoning": "Fallback due to LLM response parse error",
                    "llm_used": False,
                },
            )

    def explain_reasoning(self, action: str, context: Dict) -> str:
        """Use LLM to explain why an action was taken."""
        system_prompt = """You are an AI agent explaining your reasoning to the user.

Given the current action and context, explain in 1-2 sentences why you're taking this action.

Return ONLY the explanation, no other text."""

        prompt = f"""Action: {action}
Context: {json.dumps(context, indent=2)}

Why are you taking this action?"""

        result = call_llm(
            prompt=prompt,
            system=system_prompt,
            provider=self.provider,
            api_key=self.api_key,
            model=self.model,
            temperature=0.3,
            max_tokens=200,
        )

        if result["success"]:
            return result["content"].strip()
        else:
            return f"Executing {action} based on current task context."
