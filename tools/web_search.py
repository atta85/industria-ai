from __future__ import annotations
import json
import re
from html.parser import HTMLParser
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen
from crewai.tools import BaseTool
from pydantic import Field

class _DDGParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.items=[]; self._a=None; self._text=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=="a" and attrs.get("class") and "result__a" in attrs.get("class",""):
            self._a=attrs.get("href"); self._text=[]
    def handle_data(self, data):
        if self._a is not None: self._text.append(data)
    def handle_endtag(self, tag):
        if tag=="a" and self._a is not None:
            title=" ".join("".join(self._text).split())
            if title: self.items.append((title,self._a))
            self._a=None; self._text=[]

def search_web(query: str, max_results: int = 5) -> list[dict]:
    url=f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    req=Request(url,headers={"User-Agent":"Mozilla/5.0 Industria-AI/1.0"})
    with urlopen(req,timeout=15) as r:
        html=r.read().decode("utf-8","ignore")
    p=_DDGParser(); p.feed(html)
    out=[]
    for title,link in p.items[:max_results]:
        out.append({"title":title,"url":link,"domain":urlparse(link).netloc})
    return out

class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = "Search the public web for recent technical evidence. Input should be a concise research query. Returns titles, URLs and domains."
    max_results: int = Field(default=5)
    def _run(self, query: str) -> str:
        try:
            return json.dumps(search_web(query, self.max_results), ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": f"Search failed: {type(e).__name__}"})
