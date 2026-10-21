"""
Tools used by the agents.

Every tool is defensive: it never raises into the agent's turn. Each failure
returns a plain "unavailable" string the agent can work with, and every call
is written to a per-run usage log so the app and report can show which agent
used which tool.

API keys are passed in when the tool is created (from Streamlit Secrets in
app.py), so tools also work inside background threads.
"""

import ast
import operator
from datetime import datetime
from typing import Any, Type

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class SearchInput(BaseModel):
    query: str = Field(..., description="Short, specific search query, 3 to 8 words")


def record_tool_use(log, agent, tool, tool_input, status, detail):
    if log is None:
        return
    log.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "agent": agent,
        "tool": tool,
        "input": str(tool_input)[:160],
        "status": status,
        "detail": str(detail)[:160],
    })


# ---------------------------------------------------------------------------
# Web search (Serper.dev)
# ---------------------------------------------------------------------------
def serper_search(query: str, api_key: str):
    """Returns (results, status, detail). results: list of {title, url, snippet}."""
    if not api_key:
        return [], "unavailable", "No SERPER_API_KEY configured"
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": 5},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.Timeout:
        return [], "error", "Request timed out"
    except requests.exceptions.RequestException:
        return [], "error", "Request failed"
    except ValueError:
        return [], "error", "Unreadable response"
    items = [
        {"title": i.get("title", "Untitled"), "url": i.get("link", ""), "snippet": i.get("snippet", "")}
        for i in (data.get("organic") or [])[:5]
    ]
    return items, ("ok" if items else "no results"), f"{len(items)} results"


def format_web_results(query, items):
    if not items:
        return f'Web search "{query}": no results.'
    lines = [f'Web search "{query}":']
    for n, i in enumerate(items, 1):
        lines.append(f"  {n}. {i['title']} | {i['url']} | {i['snippet']}")
    return "\n".join(lines)


class WebSearchTool(BaseTool):
    # Not named "web_search": gpt-oss models have a built-in tool with that
    # name, and the clash breaks tool calls.
    name: str = "evidence_search"
    args_schema: Type[BaseModel] = SearchInput
    description: str = (
        "Search the web for industry guidance, standards and manufacturer "
        "information. Input: a short query. Returns up to 5 results with "
        "title, URL and snippet."
    )
    api_key: str = ""
    agent_label: str = "Research and Evidence Agent"
    usage_log: Any = None

    def _run(self, query: str) -> str:
        items, status, detail = serper_search(query, self.api_key)
        record_tool_use(self.usage_log, self.agent_label, self.name, query, status, detail)
        if status in ("unavailable", "error"):
            return f"WEB SEARCH UNAVAILABLE ({detail}). Do not invent sources."
        return format_web_results(query, items)


# ---------------------------------------------------------------------------
# Academic search (OpenAlex)
# ---------------------------------------------------------------------------
def _abstract_snippet(inverted_index, max_words=40) -> str:
    if not isinstance(inverted_index, dict):
        return ""
    positions = sorted((i, w) for w, idxs in inverted_index.items() for i in (idxs or []))
    words = [w for _, w in positions[:max_words]]
    return " ".join(words) + (" ..." if len(positions) > max_words else "")


def openalex_meta(work: dict):
    if not isinstance(work, dict):
        return None
    wid = str(work.get("id") or "").rsplit("/", 1)[-1]
    title = work.get("display_name") or work.get("title")
    if not wid.startswith("W") or not title:
        return None
    authors = [((a or {}).get("author") or {}).get("display_name") for a in (work.get("authorships") or [])]
    authors = [a for a in authors if a]
    source = (work.get("primary_location") or {}).get("source") or {}
    doi = work.get("doi") or ""
    return {
        "id": wid,
        "title": str(title),
        "authors": authors,
        "year": work.get("publication_year") or "n.d.",
        "venue": source.get("display_name") or "",
        "doi": doi,
        "url": doi if doi else f"https://openalex.org/{wid}",
        "cited_by": work.get("cited_by_count") or 0,
        "abstract": _abstract_snippet(work.get("abstract_inverted_index")),
    }


def openalex_search(query: str, api_key: str):
    """Returns (papers, status, detail). papers: list of metadata dicts."""
    if not api_key:
        return [], "unavailable", "No OPENALEX_API_KEY configured"
    try:
        r = requests.get(
            "https://api.openalex.org/works",
            params={"search": query, "per_page": 5, "api_key": api_key},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.Timeout:
        return [], "error", "Request timed out"
    except requests.exceptions.RequestException:
        return [], "error", "Request failed"
    except ValueError:
        return [], "error", "Unreadable response"
    papers = [m for m in (openalex_meta(w) for w in (data.get("results") or [])) if m]
    return papers, ("ok" if papers else "no results"), f"{len(papers)} papers"


def format_papers(query, papers):
    if not papers:
        return f'Academic search "{query}": no papers.'
    lines = [f'Academic search "{query}":']
    for p in papers:
        a = p["authors"]
        who = (", ".join(a[:3]) + (" et al" if len(a) > 3 else "")) or "Unknown authors"
        lines.append(
            f"  [{p['id']}] {p['title']} ({p['year']}). {who}. {p['venue'] or 'Unknown venue'}. "
            f"Cited by {p['cited_by']}. Abstract: {p['abstract'] or 'n/a'}"
        )
    return "\n".join(lines)


class ScholarlySearchTool(BaseTool):
    """Every paper returned is stored in the run's registry, so the reference
    list is built from real metadata and invented IDs can be removed."""

    name: str = "scholarly_search"
    args_schema: Type[BaseModel] = SearchInput
    description: str = (
        "Search peer-reviewed academic literature. Input: a short query. "
        "Returns up to 5 papers, each labelled with a reference ID in square "
        "brackets like [W2741809807]. Cite papers only with these exact IDs."
    )
    api_key: str = ""
    agent_label: str = "Research and Evidence Agent"
    usage_log: Any = None
    registry: Any = None

    def _run(self, query: str) -> str:
        papers, status, detail = openalex_search(query, self.api_key)
        record_tool_use(self.usage_log, self.agent_label, self.name, query, status, detail)
        if status in ("unavailable", "error"):
            return f"ACADEMIC SEARCH UNAVAILABLE ({detail}). Do not cite or invent papers."
        if isinstance(self.registry, dict):
            for p in papers:
                self.registry[p["id"]] = p
        return format_papers(query, papers)


# ---------------------------------------------------------------------------
# Safe calculator
# ---------------------------------------------------------------------------
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        if isinstance(node.op, ast.Pow) and abs(_safe_eval(node.right)) > 100:
            raise ValueError("Exponent too large.")
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Only numbers and + - * / ** ( ) are allowed.")


class SafeCalculatorTool(BaseTool):
    """Arithmetic without eval(): the expression is parsed and only numbers
    and basic operators are evaluated."""

    name: str = "safe_calculator"
    description: str = (
        "Evaluate an arithmetic expression such as '(120 - 95) / 95 * 100'. "
        "Supports + - * / ** and parentheses only."
    )
    agent_label: str = ""
    usage_log: Any = None

    def _run(self, expression: str) -> str:
        try:
            result = _safe_eval(ast.parse(str(expression), mode="eval").body)
            result = round(result, 6) if isinstance(result, float) else result
            record_tool_use(self.usage_log, self.agent_label, self.name, expression, "ok", f"= {result}")
            return str(result)
        except ZeroDivisionError:
            record_tool_use(self.usage_log, self.agent_label, self.name, expression, "error", "Division by zero")
            return "Error: division by zero. Report this calculation as unavailable."
        except Exception as exc:  # noqa: BLE001 - must never raise
            record_tool_use(self.usage_log, self.agent_label, self.name, expression, "error", "Invalid expression")
            return f"Error: {exc} Report this calculation as unavailable."
