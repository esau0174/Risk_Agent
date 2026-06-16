from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

from src.core.tool_registry import RiskTool, get_tool
from src.workflow.types import WorkflowPlan, WorkflowStep


DEFAULT_LLM_PLANNER_MODEL = "gpt-4o-mini"
SUPPORTED_MODULES = ["Market Risk", "Credit Risk", "Regulatory Risk"]


class LLMPlannerError(ValueError):
    """Raised when the LLM planner cannot produce a usable plan proposal."""


class LLMPlannerUnavailable(RuntimeError):
    """Raised when LLM planning is requested but no LLM client is configured."""


@dataclass(frozen=True)
class LLMPlannerProposal:
    detected_modules: list[str]
    plan: WorkflowPlan
    rationale: str
    planner_notes: list[str]


def is_llm_planner_available() -> bool:
    """Return whether the OpenAI-backed planner can be created from environment."""
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        return False
    try:
        import openai  # noqa: F401
    except ImportError:
        return False
    return True


def propose_llm_workflow_plan(
    user_query: str,
    scenario: str,
    available_input_schemas: list[str],
    registered_tools: list[RiskTool],
    client: Any | None = None,
    model: str | None = None,
) -> LLMPlannerProposal:
    """Ask an LLM to propose a tool plan without executing any tools."""
    if not isinstance(user_query, str) or not user_query.strip():
        raise ValueError("user_query must be a non-empty string.")

    client = client or _create_openai_client()
    model = model or os.getenv("OPENAI_PLANNER_MODEL", DEFAULT_LLM_PLANNER_MODEL)
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": _planner_system_prompt(registered_tools),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "user_query": user_query,
                        "scenario": scenario,
                        "available_input_schemas": available_input_schemas,
                        "supported_modules": SUPPORTED_MODULES,
                        "registered_tools": [
                            {
                                "name": tool.name,
                                "module": tool.module,
                                "description": tool.description,
                            }
                            for tool in registered_tools
                        ],
                    },
                    indent=2,
                ),
            },
        ],
    )

    try:
        payload = json.loads(response.output_text)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise LLMPlannerError("LLM planner returned malformed JSON.") from exc

    return parse_llm_plan_payload(payload, registered_tools)


def parse_llm_plan_payload(
    payload: dict,
    registered_tools: list[RiskTool],
) -> LLMPlannerProposal:
    """Convert a JSON-like LLM plan proposal into a WorkflowPlan."""
    if not isinstance(payload, dict):
        raise LLMPlannerError("LLM planner response must be a JSON object.")

    detected_modules = payload.get("detected_modules", [])
    proposed_tools = payload.get("proposed_tools", [])
    rationale = payload.get("rationale", "")
    planner_notes = payload.get("planner_notes", [])

    if not isinstance(detected_modules, list) or not all(
        isinstance(module, str) for module in detected_modules
    ):
        raise LLMPlannerError("LLM planner detected_modules must be a list of strings.")
    if not isinstance(proposed_tools, list) or not proposed_tools:
        raise LLMPlannerError("LLM planner proposed_tools must be a non-empty list.")
    if planner_notes is None:
        planner_notes = []
    if not isinstance(planner_notes, list):
        raise LLMPlannerError("LLM planner planner_notes must be a list.")

    steps = [
        _proposal_step(tool_proposal, registered_tools)
        for tool_proposal in proposed_tools
    ]
    return LLMPlannerProposal(
        detected_modules=detected_modules,
        plan=WorkflowPlan(
            objective="LLM-proposed RiskFlow Agent workflow plan.",
            steps=steps,
        ),
        rationale=str(rationale),
        planner_notes=[str(note) for note in planner_notes],
    )


def _proposal_step(tool_proposal: dict, registered_tools: list[RiskTool]) -> WorkflowStep:
    if not isinstance(tool_proposal, dict):
        raise LLMPlannerError("Each proposed tool must be an object.")
    tool_name = tool_proposal.get("tool_name")
    if not isinstance(tool_name, str) or not tool_name.strip():
        raise LLMPlannerError("Each proposed tool must include a tool_name.")

    reason = str(tool_proposal.get("reason") or "LLM-proposed workflow step.")
    try:
        tool = get_tool(tool_name)
        description = f"{tool.description} Reason: {reason}"
    except KeyError:
        registered_names = {tool.name for tool in registered_tools}
        description = (
            f"Unregistered LLM-proposed tool. Reason: {reason}"
            if tool_name not in registered_names
            else reason
        )

    return WorkflowStep(
        name=tool_name,
        description=description,
        status="proposed",
        tool_name=tool_name,
    )


def _create_openai_client():
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMPlannerUnavailable("OPENAI_API_KEY is not configured.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LLMPlannerUnavailable(
            "The OpenAI Python SDK is required for LLM planning."
        ) from exc
    return OpenAI(api_key=api_key)


def _planner_system_prompt(registered_tools: list[RiskTool]) -> str:
    tool_names = ", ".join(tool.name for tool in registered_tools)
    return (
        "You are the RiskFlow Agent workflow planner. Propose a workflow plan as "
        "strict JSON only. Do not execute tools. Do not calculate VaR, Expected "
        "Shortfall, PFE, SA-CCR, SIMM, RegIM, capital, margin, or any risk number. "
        "Risk calculations must be performed only by registered deterministic tools. "
        "SA-CCR / SIMM / RegIM capital or margin calculations are not implemented. "
        "Unsupported tools must not be proposed. The final plan will be rejected "
        "unless it passes deterministic validation. Supported modules are Market "
        "Risk, Credit Risk, and Regulatory Risk. Registered tools are: "
        f"{tool_names}. Return exactly this JSON shape: "
        "{"
        '"detected_modules":["Market Risk"],'
        '"proposed_tools":[{"tool_name":"load_portfolio_file","reason":"..."}],'
        '"rationale":"...",'
        '"planner_notes":["..."]'
        "}."
    )
