"""
Agents are asked for JSON, but LLM output can arrive wrapped in code fences,
with stray text, or in slightly wrong shapes. Everything here degrades
gracefully: a bad answer becomes visible data with a warning, never a crash.
"""

import json
import re

LIKELIHOODS = ("High", "Medium", "Low")
CATEGORIES = ("People", "Machine", "Method", "Material", "Measurement", "Environment")
PRIORITIES = ("Immediate", "Short-term", "Long-term")


def _as_dict(obj, raw):
    return obj if isinstance(obj, dict) else {"raw_text": raw or "", "parse_error": True}


def parse_json_output(raw_text) -> dict:
    if raw_text is None:
        return {"raw_text": "", "parse_error": True}
    text = str(raw_text).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return _as_dict(json.loads(text), raw_text)
    except (json.JSONDecodeError, TypeError):
        pass
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        try:
            return _as_dict(json.loads(brace.group(0)), raw_text)
        except json.JSONDecodeError:
            pass
    return {"raw_text": raw_text, "parse_error": True}


def task_raw(task):
    out = getattr(task, "output", None)
    return getattr(out, "raw", None) if out is not None else None


def as_str(value, default="") -> str:
    if value is None:
        return default
    if isinstance(value, (list, tuple)):
        return "; ".join(as_str(v) for v in value if as_str(v))
    if isinstance(value, dict):
        return "; ".join(f"{k}: {v}" for k, v in value.items())
    return str(value).strip()


def as_str_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, (str, int, float, dict)):
        value = [value]
    return [s for s in (as_str(v) for v in value) if s]


def _pick(value, options, default):
    v = as_str(value).lower()
    for opt in options:
        if opt.lower().split("-")[0] in v:
            return opt
    return default


def norm_likelihood(value) -> str:
    return _pick(value, LIKELIHOODS, "Medium")


def norm_category(value) -> str:
    v = as_str(value).lower()
    aliases = {"man": "People", "human": "People", "operator": "People", "labour": "People",
               "equipment": "Machine", "tool": "Machine", "process": "Method", "procedure": "Method",
               "raw": "Material", "inspection": "Measurement", "gauge": "Measurement",
               "temperature": "Environment", "humidity": "Environment"}
    for c in CATEGORIES:
        if c.lower() in v:
            return c
    for k, c in aliases.items():
        if k in v:
            return c
    return "Method"


def norm_priority(value) -> str:
    v = as_str(value).lower()
    if "immed" in v or "urgent" in v:
        return "Immediate"
    if "long" in v:
        return "Long-term"
    return "Short-term"


def norm_pct(value, likelihood) -> int:
    try:
        n = int(round(float(str(value).strip().rstrip("%"))))
        return max(0, min(100, n))
    except (TypeError, ValueError):
        return {"High": 70, "Medium": 45, "Low": 20}[likelihood]


def as_evidence_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, (str, dict)):
        value = [value]
    out = []
    for item in value:
        if isinstance(item, dict):
            out.append({
                "finding": as_str(item.get("finding") or item.get("summary")),
                "source_title": as_str(item.get("source_title") or item.get("title")),
                "source_url": as_str(item.get("source_url") or item.get("url")),
                "source_type": as_str(item.get("source_type")).lower(),
                "reference_id": as_str(item.get("reference_id")),
            })
        elif as_str(item):
            out.append({"finding": as_str(item), "source_title": "", "source_url": "",
                        "source_type": "", "reference_id": ""})
    return [e for e in out if e["finding"]]


def normalize_root_causes(value) -> list:
    if value is None:
        return []
    if isinstance(value, (str, dict)):
        value = [value]
    out = []
    for item in value:
        if not isinstance(item, dict):
            item = {"cause": as_str(item)}
        lk = norm_likelihood(item.get("likelihood"))
        cause = as_str(item.get("cause"))
        if not cause:
            continue
        out.append({
            "cause": cause,
            "category": norm_category(item.get("category")),
            "likelihood": lk,
            "basis": "Evidence-based" if "evidence" in as_str(item.get("basis")).lower() else "Agent-inference",
            "reasoning": as_str(item.get("reasoning")),
            "action": as_str(item.get("action")),
            "action_risk": as_str(item.get("action_risk")),
        })
    return out[:3]


def normalize_ranked(value) -> list:
    if value is None:
        return []
    if isinstance(value, (str, dict)):
        value = [value]
    out = []
    for item in value:
        if not isinstance(item, dict):
            item = {"cause": as_str(item)}
        cause = as_str(item.get("cause"))
        if not cause:
            continue
        lk = norm_likelihood(item.get("likelihood"))
        out.append({
            "cause": cause,
            "category": norm_category(item.get("category")),
            "likelihood": lk,
            "likelihood_pct": norm_pct(item.get("likelihood_pct"), lk),
            "evidence": as_str(item.get("evidence")),
            "action": as_str(item.get("action")),
            "priority": norm_priority(item.get("priority")),
            "verification": as_str(item.get("verification")),
        })
    out.sort(key=lambda r: r["likelihood_pct"], reverse=True)
    return out[:5]
