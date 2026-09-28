import html, re, requests
from urllib.parse import quote_plus

def search_web(query, max_results=4):
    '''Lightweight optional web research. Uses DuckDuckGo HTML and fails gracefully.'''
    try:
        url = 'https://html.duckduckgo.com/html/?q=' + quote_plus(query[:500])
        r = requests.get(url, timeout=8, headers={'User-Agent':'Industria-AI/1.0'})
        r.raise_for_status()
        text = r.text
        blocks = re.findall(r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', text, re.I|re.S)
        out=[]
        for href, title in blocks[:max_results]:
            clean_title = re.sub('<.*?>','',html.unescape(title)).strip()
            clean_url = html.unescape(href)
            out.append({'title':clean_title,'url':clean_url,'snippet':'Search result retrieved from DuckDuckGo.'})
        return out
    except Exception:
        return []
