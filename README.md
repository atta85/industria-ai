# Industria-AI

Human-in-the-Loop multi-agent decision-support for industrial and cross-disciplinary problems.

## Architecture
- CrewAI multi-agent workflow.
- Problem Scoping → Domain Router → selected specialists → Research & Evidence → Synthesis → Critical Review → Human decision → Final report.
- Only the most relevant specialists are activated; a maximum of **2** is used per run to reduce Groq TPM consumption.
- External research is optional and fails gracefully.
- The system never exposes private chain-of-thought; it returns concise findings, evidence labels, uncertainty and an audit trail.

## Streamlit Cloud deployment
1. Upload this repository to GitHub.
2. Create a Streamlit Cloud app using `app.py`.
3. Set Python version to **3.12**.
4. In App Settings → Secrets add:

```toml
GROQ_API_KEY = "your Groq API key"
```

Do not commit the real key.

## Important Groq note
The application uses `groq/openai/gpt-oss-120b`. The code includes a compatibility workaround for the `cache_breakpoint` field issue encountered with the CrewAI/LiteLLM stack and automatic retry handling for TPM rate limits.

## Demo scenarios
See `DEMO_SCRIPT.md` for manufacturing dimensional defects, software slowdown, and biotechnology batch inconsistency.


### Research & Evidence

Industria-AI uses a lightweight external research layer. It first attempts DuckDuckGo web search and, when that is unavailable or returns no parseable results, falls back to Crossref's public scholarly API. No additional search API key is required. The application displays the number and provider of retrieved sources and reports a diagnostic message when retrieval fails. The LLM is instructed to cite only URLs actually supplied by the research tool and never to fabricate references.
