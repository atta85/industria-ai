"""
Crew A: one Intake and Routing agent that restates the problem, suggests the
optional details, picks the specialists and plans the searches, in a single
LLM call (merged for speed).
"""

import os

import yaml
from crewai import Agent, Crew, Process, Task

from crew.specialist_pool import clean_selection
from utils.json_parser import as_str, as_str_list, parse_json_output, task_raw

_CONFIG = os.path.join(os.path.dirname(__file__), "config")


def load_config(name: str) -> dict:
    with open(os.path.join(_CONFIG, name), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _details_text(details: dict) -> str:
    parts = [f"{k.replace('_', ' ')}: {v}" for k, v in (details or {}).items() if str(v).strip()]
    return "; ".join(parts) if parts else "(none)"


def run_intake(industry, problem_statement, user_details, data_summary, llm_light, emit=None):
    emit = emit or (lambda *a, **k: None)
    agents_cfg, tasks_cfg = load_config("agents.yaml"), load_config("tasks.yaml")

    agent = Agent(config=agents_cfg["intake_router"], llm=llm_light, verbose=False, allow_delegation=False)
    task = Task(
        description=tasks_cfg["intake_task"]["description"].format(
            industry=industry or "(not specified)",
            problem_statement=problem_statement.strip(),
            user_details=_details_text(user_details),
            data_summary=data_summary or "(none)",
        ),
        expected_output=tasks_cfg["intake_task"]["expected_output"].format(),
        agent=agent,
    )
    emit("intake", "running", "Reading your problem and choosing specialists")
    Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False).kickoff()
    data = parse_json_output(task_raw(task))
    emit("intake", "done", "Problem understood")

    queries = data.get("search_queries") if isinstance(data.get("search_queries"), dict) else {}
    fallback_q = f"{industry} {problem_statement[:60]}".strip()
    result = {
        "problem_summary": as_str(data.get("problem_summary")) or problem_statement.strip(),
        "short_title": (as_str(data.get("short_title")) or " ".join(problem_statement.split()[:4]))[:48],
        "domains": as_str_list(data.get("domains")),
        "selected_specialists": clean_selection(as_str_list(data.get("selected_specialists")), has_data=bool(data_summary)),
        "routing_rationale": as_str(data.get("routing_rationale")),
        "objectives": as_str_list(data.get("objectives")),
        "constraints": as_str_list(data.get("constraints")),
        "available_data": as_str_list(data.get("available_data")),
        "desired_outcome": as_str(data.get("desired_outcome")),
        "assumptions": as_str_list(data.get("assumptions")),
        "missing_information": as_str_list(data.get("missing_information")),
        "search_queries": {
            "web": (as_str_list(queries.get("web")) or [fallback_q])[:2],
            "academic": (as_str_list(queries.get("academic")) or [fallback_q])[:2],
        },
        "high_risk": str(data.get("high_risk")).lower() == "true",
        "risk_note": as_str(data.get("risk_note")),
        "parse_error": bool(data.get("parse_error")),
    }
    return result
