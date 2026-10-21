"""
Turns OpenAlex reference IDs cited by the agents (e.g. [W2741809807]) into
numbered citations [1], [2] ... and builds the reference list from the real
metadata the academic search returned.

Safety rule: an ID is accepted only if that paper was actually returned in
this run. Any other ID is removed, so an invented reference can never reach
the report.
"""

import re

_ID = re.compile(r"\[?\b(W\d{5,})\b\]?")


def format_reference(meta: dict) -> str:
    authors = meta.get("authors") or []
    if not authors:
        who = "Unknown authors"
    elif len(authors) > 3:
        who = ", ".join(authors[:3]) + ", et al."
    else:
        who = ", ".join(authors)
    who = who.rstrip(".")
    venue = f" {meta['venue']}." if meta.get("venue") else ""
    return f"{who}. ({meta.get('year', 'n.d.')}). {str(meta.get('title', '')).rstrip('.')}.{venue}"


def apply_citations(inv: dict, registry: dict) -> dict:
    registry = registry or {}
    order = []

    def number_for(wid):
        if wid not in registry:
            return None
        if wid not in order:
            order.append(wid)
        return order.index(wid) + 1

    def sub(text):
        def repl(m):
            n = number_for(m.group(1))
            return f"[{n}]" if n else ""
        out = _ID.sub(repl, str(text or ""))
        out = re.sub(r"\[(\d+)\](\s*\[\1\])+", r"[\1]", out)          # [1] [1] -> [1]
        out = re.sub(r"\s+(?:and|or|,)\s*(?=[.;:)]|$)", "", out)   # "by [1] and" -> "by [1]"
        out = re.sub(r"\s{2,}", " ", out).replace(" .", ".").replace(" ,", ",").replace("()", "")
        return out.strip()

    for e in inv.get("evidence", []):
        m = _ID.search(e.get("reference_id", "")) or _ID.search(e.get("finding", ""))
        n = number_for(m.group(1)) if m else None
        if n:
            meta = registry[m.group(1)]
            e.update(citation=n, source_type="academic", source_title=meta["title"], source_url=meta["url"])
        else:
            e["citation"] = None
            e["source_type"] = "web" if str(e.get("source_url", "")).startswith("http") else "unverified"
        e.pop("reference_id", None)
        e["finding"] = sub(e.get("finding"))
        if e.get("citation"):
            e["finding"] = re.sub(r"\s*\[" + str(e["citation"]) + r"\]", "", e["finding"]).strip()

    for s in inv.get("specialist_results", []):
        for rc in s.get("root_causes", []):
            for f in ("cause", "reasoning", "action", "action_risk"):
                rc[f] = sub(rc.get(f))

    rv = inv.get("review", {})
    if not rv.get("parse_error"):
        rv["executive_summary"] = sub(rv.get("executive_summary"))
        for rc in rv.get("ranked_causes", []):
            for f in ("cause", "evidence", "action", "verification"):
                rc[f] = sub(rc.get(f))
        for f in ("critical_findings", "alternative_explanations", "uncertainties", "risks"):
            rv[f] = [sub(x) for x in rv.get(f, [])]

    inv["references"] = [
        {"number": i + 1, "id": w, "text": format_reference(registry[w]), "url": registry[w]["url"]}
        for i, w in enumerate(order)
    ]
    inv["related_literature"] = [
        {"text": format_reference(m), "url": m["url"]} for w, m in registry.items() if w not in order
    ][:5]
    return inv
