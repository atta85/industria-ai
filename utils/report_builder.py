"""
The final report is assembled by plain Python from data the human already
reviewed, never by a fresh LLM call, so nothing can change after approval.
"""

import uuid
from datetime import datetime, timezone

from crew.specialist_pool import label

DISCLAIMER = (
    "Decision-support output, not a substitute for qualified professional judgment. "
    "Verify the causes and actions before acting on them."
)


def build_report(*, industry, problem_statement, mode, interpretation, investigation, decision,
                 verified_by, feedback_history, data_profile=None, ai_assumed_fields=None,
                 models_note="", audit=None):
    rv = investigation.get("review", {})
    warnings = []
    if not investigation.get("evidence"):
        warnings.append("No external evidence was available. Findings are agent inference and need verification.")
    if mode == "one-step" and ai_assumed_fields:
        warnings.append("One-step mode: the AI filled some details itself and they were not checked "
                        "before the analysis (see 'AI assumptions').")
    if interpretation.get("high_risk"):
        warnings.append("Safety-relevant problem: have a qualified engineer verify every action before use. "
                        + (interpretation.get("risk_note") or ""))
    if rv.get("used_fallback_ranking"):
        warnings.append("The reviewer's ranking was incomplete, so the table was compiled from the specialists' findings.")
    if models_note:
        warnings.append(models_note)
    warnings.append(DISCLAIMER)

    return {
        "report_id": uuid.uuid4().hex[:8].upper(),
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "industry": industry,
        "problem_statement": problem_statement,
        "mode": mode,
        "decision": decision,
        "verified_by": verified_by or "Guest user",
        "interpretation": {k: interpretation.get(k) for k in (
            "problem_summary", "domains", "objectives", "constraints", "available_data",
            "desired_outcome", "assumptions", "missing_information", "high_risk", "risk_note")},
        "ai_assumed_fields": ai_assumed_fields or [],
        "specialists": [label(k) for k in interpretation.get("selected_specialists", [])],
        "agents_involved": investigation.get("agents_involved", []),
        "review": rv,
        "specialist_results": investigation.get("specialist_results", []),
        "evidence": investigation.get("evidence", []),
        "evidence_notes": investigation.get("evidence_notes", ""),
        "references": investigation.get("references", []),
        "related_literature": investigation.get("related_literature", []),
        "tool_usage": investigation.get("tool_usage", []),
        "data_profile": {k: data_profile.get(k) for k in ("summary", "rows", "columns")} if data_profile else None,
        "feedback_history": feedback_history or [],
        "audit": audit or [],
        "warnings": warnings,
    }


def _bullets(items):
    items = [i for i in (items or []) if str(i).strip()]
    return "\n".join(f"- {i}" for i in items) if items else "_None stated._"


def report_to_markdown(r: dict) -> str:
    rv = r.get("review", {})
    it = r.get("interpretation", {})
    out = [
        "# Verified Decision-Support Report",
        f"*Industria-AI · {r['industry']} · {r['generated_utc']} · Report {r['report_id']}*",
        "",
        f"**Human decision:** {r['decision']}  ·  **Verification:** {r['mode']}  ·  **Verified by:** {r['verified_by']}",
        "",
        "## Summary",
        rv.get("executive_summary") or "_Not available._",
        f"\n**Reviewer verdict:** {rv.get('verdict', 'Not stated')}",
        "",
        "## Ranked root causes",
        "| # | Root cause | Category | Likelihood | Evidence | Action | Priority | How to verify |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, c in enumerate(rv.get("ranked_causes", []), 1):
        cells = [str(i), c["cause"], c["category"], f"{c['likelihood']} ({c['likelihood_pct']}%)",
                 c.get("evidence", ""), c.get("action", ""), c.get("priority", ""), c.get("verification", "")]
        out.append("| " + " | ".join(x.replace("|", "/").replace("\n", " ") for x in cells) + " |")
    out += ["", "## Critical review", "**Critical findings**", _bullets(rv.get("critical_findings")),
            "", "**Alternative explanations**", _bullets(rv.get("alternative_explanations")),
            "", "**Uncertainties**", _bullets(rv.get("uncertainties")),
            "", "**Risks of the proposed actions**", _bullets(rv.get("risks")),
            "", "## Problem and interpretation", f"**Problem statement:** {r['problem_statement']}",
            "", f"**Interpretation:** {it.get('problem_summary', '')}",
            "", "**Objectives**", _bullets(it.get("objectives")),
            "", "**Constraints**", _bullets(it.get("constraints")),
            "", f"**Desired outcome:** {it.get('desired_outcome') or 'Not stated'}",
            "", "**Assumptions**", _bullets(it.get("assumptions")),
            "", "**Missing information**", _bullets(it.get("missing_information"))]
    if r.get("ai_assumed_fields"):
        out += ["", f"**AI assumptions (not checked before analysis):** {', '.join(r['ai_assumed_fields'])}"]
    if r.get("data_profile"):
        out += ["", "## Process data (computed from uploaded CSV)", r["data_profile"]["summary"]]
    out += ["", "## Evidence"]
    for e in r.get("evidence", []):
        cite = f" [{e['citation']}]" if e.get("citation") else ""
        src = f"[{e.get('source_title') or 'source'}]({e['source_url']})" if e.get("source_url") else (e.get("source_title") or "")
        out.append(f"- {e['finding']}{cite} ({e.get('source_type', '').title()}) {src}")
    if not r.get("evidence"):
        out.append("_No external evidence was available._")
    out += ["", "## Specialist analyses"]
    for s in r.get("specialist_results", []):
        out.append(f"### {s['specialist']} (confidence: {s.get('confidence', 'n/a')})")
        for c in s.get("root_causes", []):
            out.append(f"- **{c['cause']}** ({c['category']}, {c['likelihood']}, {c['basis']}): {c.get('reasoning', '')} "
                       f"Action: {c.get('action', '')}. Risk: {c.get('action_risk', '')}.")
        if s.get("parse_error") and s.get("raw_text"):
            out.append(f"\n> {s['raw_text'][:800]}")
    out += ["", "## Tools used by the agents"]
    for t in r.get("tool_usage", []):
        out.append(f"- `{t['time']}` {t['agent']} used `{t['tool']}` on \"{t['input']}\" → {t['status']} ({t['detail']})")
    out += ["", "## References"]
    out += [f"{x['number']}. {x['text']} {x['url']}" for x in r.get("references", [])] or ["_No academic papers were cited._"]
    if r.get("feedback_history"):
        out += ["", "## Human feedback"] + [f"- {f['time']}: {f['text']}" for f in r["feedback_history"]]
    out += ["", "## Important notes"] + [f"- {w}" for w in r.get("warnings", [])]
    return "\n".join(out)
