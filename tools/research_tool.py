"""Lightweight web research for Industria-AI.

The tool uses DuckDuckGo's lightweight HTML interface and deliberately keeps
source retrieval separate from the LLM.  No additional API key is required.
If the search provider is unavailable, the caller receives a diagnostic status
instead of silently treating the failure as a successful zero-result search.
"""

import html
import re
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests


SEARCH_ENDPOINTS = (
    "https://lite.duckduckgo.com/lite/?q=",
    "https://html.duckduckgo.com/html/?q=",
)


def _clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _unwrap_url(url: str) -> str:
    """Turn common DuckDuckGo redirect URLs into the actual destination."""
    url = html.unescape((url or "").strip())
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("/"):
        return url
    try:
        parsed = urlparse(url)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            target = parse_qs(parsed.query).get("uddg", [None])[0]
            if target:
                return unquote(target)
    except Exception:
        pass
    return url


def _parse_lite(page: str, max_results: int):
    """Parse DuckDuckGo Lite result links/snippets."""
    results = []

    # Current Lite markup normally uses result-link / result-snippet classes.
    pattern = re.compile(
        r'<a[^>]*class=["\']result-link["\'][^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.I | re.S,
    )
    links = pattern.findall(page)

    for index, (href, title_html) in enumerate(links[:max_results]):
        title = _clean_html(title_html)
        url = _unwrap_url(href)
        if not title or not url.startswith(("http://", "https://")):
            continue

        # Grab a nearby snippet from the result block when available.
        window_start = page.find(href)
        window = page[window_start:window_start + 1800] if window_start >= 0 else ""
        snippet_match = re.search(
            r'class=["\']result-snippet["\'][^>]*>(.*?)</(?:td|div|span|a)>',
            window,
            re.I | re.S,
        )
        snippet = _clean_html(snippet_match.group(1)) if snippet_match else ""

        results.append({
            "title": title,
            "url": url,
            "snippet": snippet or "External search result retrieved from DuckDuckGo.",
            "provider": "DuckDuckGo",
        })

    return results


def _parse_html_endpoint(page: str, max_results: int):
    """Fallback parser for DuckDuckGo's HTML endpoint."""
    pattern = re.compile(
        r'<a[^>]+class=["\']result__a["\'][^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.I | re.S,
    )
    results = []
    for href, title_html in pattern.findall(page)[:max_results]:
        title = _clean_html(title_html)
        url = _unwrap_url(href)
        if title and url.startswith(("http://", "https://")):
            results.append({
                "title": title,
                "url": url,
                "snippet": "External search result retrieved from DuckDuckGo.",
                "provider": "DuckDuckGo",
            })
    return results


def _crossref_search(query: str, max_results: int):
    """Fallback scholarly search using Crossref's public API (no key required)."""
    try:
        url = "https://api.crossref.org/works"
        response = requests.get(
            url,
            params={"query.bibliographic": query[:500], "rows": max_results, "select": "DOI,title,URL,abstract,published-print,published-online"},
            timeout=12,
            headers={"User-Agent": "Industria-AI/1.0 (mailto:research@example.com)"},
        )
        response.raise_for_status()
        items = response.json().get("message", {}).get("items", [])
        results = []
        for item in items:
            titles = item.get("title") or []
            title = titles[0].strip() if titles else "Untitled research work"
            url = item.get("URL") or ("https://doi.org/" + item["DOI"] if item.get("DOI") else "")
            if not url:
                continue
            abstract = _clean_html(item.get("abstract", ""))
            year = ""
            for key in ("published-print", "published-online"):
                parts = item.get(key, {}).get("date-parts", [])
                if parts and parts[0]:
                    year = str(parts[0][0])
                    break
            results.append({
                "title": title,
                "url": url,
                "snippet": (abstract[:500] if abstract else f"Scholarly publication indexed by Crossref{(' (' + year + ')') if year else ''}."),
                "provider": "Crossref",
            })
        return results
    except Exception as exc:
        return [], f"Crossref: {type(exc).__name__}: {str(exc)[:140]}"


def search_web(query, max_results=4):
    """Search the public web and return sources plus a diagnostic status.

    Return shape:
        {"sources": [...], "status": "ok|no_results|error", "message": str}

    The function never raises for ordinary network/search failures so the
    decision-support workflow can continue safely.
    """
    query = re.sub(r"\s+", " ", str(query or "")).strip()
    if not query:
        return {"sources": [], "status": "no_results", "message": "Search query was empty."}

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Industria-AI/1.0; +https://streamlit.io/)",
        "Accept-Language": "en-US,en;q=0.8",
    }
    errors = []

    for endpoint in SEARCH_ENDPOINTS:
        try:
            url = endpoint + quote_plus(query[:600])
            response = requests.get(url, timeout=12, headers=headers, allow_redirects=True)
            response.raise_for_status()
            page = response.text

            if "lite.duckduckgo.com" in endpoint:
                results = _parse_lite(page, max_results)
            else:
                results = _parse_html_endpoint(page, max_results)

            if results:
                # Deduplicate by destination URL.
                unique = []
                seen = set()
                for item in results:
                    if item["url"] not in seen:
                        seen.add(item["url"])
                        unique.append(item)
                return {
                    "sources": unique[:max_results],
                    "status": "ok",
                    "message": f"Retrieved {len(unique[:max_results])} external sources from DuckDuckGo.",
                }

            errors.append(f"{endpoint.split('/')[2]} returned no parseable results")
        except Exception as exc:
            errors.append(f"{endpoint.split('/')[2]}: {type(exc).__name__}: {str(exc)[:140]}")

    # Scholarly fallback: useful for engineering, manufacturing, science and technology queries.
    scholarly, scholarly_error = _crossref_search(query, max_results)
    if scholarly:
        return {
            "sources": scholarly[:max_results],
            "status": "ok",
            "message": f"Retrieved {len(scholarly[:max_results])} scholarly sources from Crossref after web-search fallback.",
        }
    if scholarly_error:
        errors.append(scholarly_error)

    return {
        "sources": [],
        "status": "error",
        "message": "No usable external sources were retrieved. " + " | ".join(errors),
    }
