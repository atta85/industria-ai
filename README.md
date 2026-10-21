# Industria-AI

**Industrial problem analyzer: a team of AI specialists, with a human in control.**

Describe an industrial problem, such as a rising defect rate, machine downtime or
batch variation. Industria-AI picks the right specialists, gathers web and
peer-reviewed evidence, challenges its own answer, and produces a short,
verified report with ranked root causes, actions, a fishbone diagram and
numbered references. Nothing is final until a human approves it.

> AI analyzes. AI cross-checks. Human verifies. AI finalizes.

## Features

- **Industry dropdown** with 26 industries plus "Other", each with an example problem statement.
- **Choice of verification:**
  - *Two-step (recommended):* a quick check of the AI's understanding, with suggested objectives and constraints you can edit, then a final review.
  - *One-step (faster):* you add the details yourself and review the result once. Anything the AI had to assume is flagged in the report.
- **Live agent progress:** a checklist showing each agent as it works.
- **Optional CSV upload:** statistics, trends and correlations are computed by code and passed to a Data specialist.
- **Compact report:** ranked root-cause table (likelihood, evidence, action, priority, how to verify), fishbone diagram, likelihood chart, critical review, and numbered references. Downloadable as PDF, with a full Markdown version.
- **No invented citations:** references are built from real OpenAlex metadata. Any reference ID the AI makes up is removed.
- **Automatic model fallback:** if a Groq model hits its daily free limit, the app switches to the other model and says so on screen and in the report.
- **Bring-your-own-key backup:** when the shared Groq key runs out for the day, users are asked for their own free Groq key and the analysis resumes on it. The key lives only in that browser session and is never saved. Users can also add one anytime from the sidebar.
- **Optional Google sign-in** with saved history, and an **in-app feedback form** for testers.
- **Light and dark themes**, a step-by-step guide panel, and an audit trail.

## Agents and tools

| Agent | Model | Tools | Role |
|---|---|---|---|
| Intake and Routing | gpt-oss-20b | none | Restates the problem, suggests details, picks 2 to 4 specialists, plans searches |
| Research and Evidence | gpt-oss-20b | `evidence_search`, `scholarly_search` | Turns search results into a short list of sourced findings |
| Specialists (pool of 10) | gpt-oss-120b | `safe_calculator` | Root causes, actions and risks in their own field; run in parallel |
| Critical Reviewer | gpt-oss-120b | none | Challenges the work and consolidates one ranked list |
| Human | — | — | Quick check, final decision (accept, modify once, reject) |

Specialist pool: Mechanical, Manufacturing, Electrical, Civil and structural,
Chemical process, Materials, Biotechnology, Software and automation, Data and
statistics, Quality and reliability.

| Tool | Service | Purpose |
|---|---|---|
| `evidence_search` | Serper.dev | Web and industry sources |
| `scholarly_search` | OpenAlex | Peer-reviewed papers with DOIs |
| `safe_calculator` | none | Exact arithmetic without `eval()` |

## Workflow

```
Describe ─► [two-step] Quick check ─► Evidence search (parallel)
        ─► Research agent ─► Specialists (parallel) ─► Critical Reviewer
        ─► Final review: Accept / Modify (1 re-run) / Reject ─► Verified report
```

## Tech stack

CrewAI 1.15 · Groq (gpt-oss-120b, gpt-oss-20b) · Streamlit (with built-in Google
login) · Serper.dev · OpenAlex · Supabase (optional) · pandas · matplotlib · ReportLab

Python 3.12 or 3.13 (CrewAI does not support 3.14).

## Setup

See **[SETUP_GUIDE.md](SETUP_GUIDE.md)** for step-by-step deployment, Google sign-in
and Supabase setup. Secrets template: `.streamlit/secrets.toml.example`.

| Secret | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | Yes | Language models |
| `SERPER_API_KEY` | No | Web evidence |
| `OPENALEX_API_KEY` | No | Academic references |
| `SUPABASE_URL`, `SUPABASE_KEY` | No | History and feedback storage |
| `[auth]` block | No | Sign in with Google |

Run locally:

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then fill in your keys
streamlit run app.py
```

## Project structure

```
app.py                     Screens, verification modes, live progress, login, history, feedback
crew/
  intake_crew.py           Intake and Routing agent
  investigation_crew.py    Parallel searches, research, parallel specialists, critical review
  specialist_pool.py       The 10 specialists
  config/agents.yaml       Agent roles and goals
  config/tasks.yaml        Task prompts and output formats
  tools/custom_tools.py    evidence_search, scholarly_search, safe_calculator
utils/
  llm_guard.py             Groq models, compatibility fixes, retry and daily-limit fallback
  json_parser.py           Tolerant parsing and normalization of agent output
  citations.py             Citation validation and numbered references
  industries.py            Industry list and example statements
  data_profile.py          CSV statistics and trend chart
  diagrams.py              Fishbone and likelihood charts
  report_builder.py        Deterministic report assembly and Markdown
  pdf_builder.py           Compact PDF report
  storage.py               Supabase history and feedback
  ui.py                    Theme, styling and UI components
supabase_setup.sql         Database tables (optional)
```

## Limitations

- Decision support only. Results can be wrong; a qualified person must verify actions, especially where safety is involved.
- The free Groq plan allows about 8,000 tokens per minute and 200,000 tokens per day per model, roughly 8 to 10 full analyses a day on the main model before the backup model takes over (an estimate; it depends on problem length). Runs take 1 to 3 minutes.
- Search quality depends on what Serper and OpenAlex return for the generated queries.
