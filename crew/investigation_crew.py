"""
Crew B: investigation.

Speed without losing quality:
  1. The web and academic searches planned at intake run in parallel, in code.
  2. The Research agent turns the results into a short evidence list.
  3. The selected specialists run in parallel (async tasks) on the larger model.
  4. The Critical Reviewer challenges their work and consolidates one ranked
     list of root causes with actions.

Progress is reported through `emit(stage, status, detail)` so the app can show
a live checklist. On a revision, cached search results are reused.
"""

from concurrent.futures import ThreadPoolExecutor

from crewai import Agent, Crew, Process, Task

from crew.intake_crew import load_config
from crew.specialist_pool import label
from crew.tools.custom_tools import (
    SafeCalculatorTool, ScholarlySearchTool, WebSearchTool,
    format_papers, format_web_results, openalex_search, record_tool_use, serper_search,
)
from utils.citations import apply_citations
from utils.json_parser import (
    as_evidence_list, as_str, as_str_list, normalize_ranked, normalize_root_causes,
    parse_json_output, task_raw,
)

RESEARCH = "Research and Evidence Agent"
MAX_SEARCH_CHARS = 5000


def run_searches(queries, keys, tool_log, registry, emit):
    emit("search", "running", "Searching web and academic sources in parallel")
    jobs = [("web", q) for q in queries.get("web", [])] + [("academic", q) for q in queries.get("academic", [])]

    def do(job):
        kind, q = job
        if kind == "web":
            items, status, detail = serper_search(q, keys.get("serper", ""))
            record_tool_use(tool_log, RESEARCH, "evidence_search", q, status, detail)
            return format_web_results(q, items) if items else f'Web search "{q}": {detail}.'
        papers, status, detail = openalex_search(q, keys.get("openalex", ""))
        record_tool_use(tool_log, RESEARCH, "scholarly_search", q, status, detail)
        for p in papers:
            registry[p["id"]] = p
        return format_papers(q, papers) if papers else f'Academic search "{q}": {detail}.'

    with ThreadPoolExecutor(max_workers=4) as pool:
        blocks = list(pool.map(do, jobs))
    text = "\n\n".join(blocks)
    if len(text) > MAX_SEARCH_CHARS:
        text = text[:MAX_SEARCH_CHARS] + "\n(results truncated)"
    found = sum(1 for t in tool_log if t["status"] == "ok")
    emit("search", "done", f"{found} of {len(jobs)} searches returned results")
    return text


def _fallback_ranked(specialist_results):
    pct = {"High": 70, "Medium": 45, "Low": 20}
    merged = []
    for s in specialist_results:
        for rc in s.get("root_causes", []):
            merged.append({
                "cause": rc["cause"], "category": rc["category"], "likelihood": rc["likelihood"],
                "likelihood_pct": pct[rc["likelihood"]], "evidence": rc.get("reasoning", ""),
                "action": rc.get("action", ""), "priority": "Short-term", "verification": "",
            })
    merged.sort(key=lambda r: r["likelihood_pct"], reverse=True)
    return merged[:5]


def run_investigation(context_text, specialist_keys, llm_heavy, llm_light, keys, queries,
                      data_summary="", feedback=None, cached=None, emit=None):
    emit = emit or (lambda *a, **k: None)
    agents_cfg, tasks_cfg = load_config("agents.yaml"), load_config("tasks.yaml")
    tool_log, registry = [], {}

    if cached:
        search_text = cached["search_text"]
        registry.update(cached["registry"])
        tool_log.extend(cached.get("tool_log", []))
        emit("search", "done", "Reusing the evidence already collected")
    else:
        search_text = run_searches(queries, keys, tool_log, registry, emit)
    search_log = list(tool_log)

    problem_context = context_text + (f"\n\nProcess data summary (computed from the uploaded CSV): {data_summary}"
                                      if data_summary else "")
    revision_note = (
        f'The human reviewer asked you to reconsider with this feedback: "{feedback}". '
        "Adjust your analysis to address it directly." if feedback else ""
    )

    research_agent = Agent(
        config=agents_cfg["research_agent"], llm=llm_light, verbose=False, allow_delegation=False,
        tools=[WebSearchTool(api_key=keys.get("serper", ""), usage_log=tool_log),
               ScholarlySearchTool(api_key=keys.get("openalex", ""), usage_log=tool_log, registry=registry)],
        max_iter=4,
    )
    research_task = Task(
        description=tasks_cfg["research_task"]["description"].format(
            problem_context=problem_context, search_results=search_text or "(no results)"),
        expected_output=tasks_cfg["research_task"]["expected_output"].format(),
        agent=research_agent,
    )

    spec_agents, spec_tasks, role_to_key = [], {}, {}
    for key in specialist_keys:
        if key not in agents_cfg:
            continue
        role = agents_cfg[key]["role"]
        role_to_key[role] = key
        agent = Agent(config=agents_cfg[key], llm=llm_heavy, verbose=False, allow_delegation=False,
                      tools=[SafeCalculatorTool(agent_label=role, usage_log=tool_log)], max_iter=5)
        spec_agents.append(agent)
        spec_tasks[key] = Task(
            description=tasks_cfg["specialist_task"].format(
                specialist_role=role, problem_context=problem_context, revision_note=revision_note),
            expected_output=tasks_cfg["specialist_output"].format(specialist_role=role),
            agent=agent, context=[research_task], async_execution=True,
        )

    reviewer = Agent(config=agents_cfg["critical_reviewer"], llm=llm_heavy, verbose=False, allow_delegation=False)
    review_task = Task(
        description=tasks_cfg["review_task"].format(problem_context=problem_context, revision_note=revision_note),
        expected_output=tasks_cfg["review_output"].format(),
        agent=reviewer, context=[research_task] + list(spec_tasks.values()),
    )

    pending = set(spec_tasks)
    reviewer_role = agents_cfg["critical_reviewer"]["role"]
    research_role = agents_cfg["research_agent"]["role"]

    def on_task_done(output):
        role = str(getattr(output, "agent", "") or "").strip()
        if role == research_role:
            emit("research", "done", "Evidence summarized")
            for k in spec_tasks:
                emit(k, "running", "Analyzing in parallel")
        elif role in role_to_key:
            k = role_to_key[role]
            pending.discard(k)
            emit(k, "done", "Analysis complete")
            if not pending:
                emit("review", "running", "Challenging and ranking the findings")
        elif role == reviewer_role:
            emit("review", "done", "Review complete")

    emit("research", "running", "Selecting the strongest evidence")
    Crew(
        agents=[research_agent] + spec_agents + [reviewer],
        tasks=[research_task] + list(spec_tasks.values()) + [review_task],
        process=Process.sequential, verbose=False, task_callback=on_task_done,
    ).kickoff()

    ev = parse_json_output(task_raw(research_task))
    specialist_results = []
    for key, task in spec_tasks.items():
        d = parse_json_output(task_raw(task))
        specialist_results.append({
            "key": key, "specialist": label(key),
            "root_causes": normalize_root_causes(d.get("root_causes")),
            "confidence": as_str(d.get("confidence"), "not stated"),
            "parse_error": bool(d.get("parse_error")) or not d.get("root_causes"),
            "raw_text": as_str(d.get("raw_text")),
        })

    rv = parse_json_output(task_raw(review_task))
    ranked = normalize_ranked(rv.get("ranked_causes")) or _fallback_ranked(specialist_results)
    review = {
        "executive_summary": as_str(rv.get("executive_summary")),
        "verdict": as_str(rv.get("verdict"), "Not stated"),
        "ranked_causes": ranked,
        "critical_findings": as_str_list(rv.get("critical_findings")),
        "alternative_explanations": as_str_list(rv.get("alternative_explanations")),
        "uncertainties": as_str_list(rv.get("uncertainties")),
        "risks": as_str_list(rv.get("risks")),
        "parse_error": bool(rv.get("parse_error")),
        "used_fallback_ranking": not normalize_ranked(rv.get("ranked_causes")),
    }
    if not review["executive_summary"] and ranked:
        review["executive_summary"] = (f"The most likely cause identified is: {ranked[0]['cause']}. "
                                       f"Recommended first action: {ranked[0]['action']}")

    result = {
        "evidence": as_evidence_list(ev.get("evidence")),
        "evidence_notes": as_str(ev.get("notes")),
        "specialist_results": specialist_results,
        "review": review,
        "agents_involved": [research_role] + [agents_cfg[k]["role"] for k in spec_tasks] + [reviewer_role],
        "tool_usage": tool_log,
        "search_cache": {"search_text": search_text, "registry": dict(registry), "tool_log": search_log},
    }
    return apply_citations(result, registry)
