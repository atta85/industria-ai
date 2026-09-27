# INDUSTRIA-AI

**Human-in-the-Loop Multi-Agent Problem Analysis & Decision Support System**

Industria-AI is a CrewAI-powered Streamlit application that assembles relevant domain specialists to investigate complex real-world problems, gathers traceable evidence, challenges its own analysis, and requires human verification before producing a **Verified Decision Support Report**.

## Core workflow

`SCOPE → HUMAN VERIFY → ROUTE → INVESTIGATE → CHALLENGE → HUMAN VERIFY → REPORT`

## Features

- General-purpose, multi-domain problem analysis
- CrewAI specialist agents selected dynamically
- Research & Evidence Agent with web search tool
- Multidisciplinary synthesis
- Critical Reviewer / Devil's Advocate
- Two real human-in-the-loop checkpoints
- Human ACCEPT / MODIFY / REJECT control
- Visible audit trail
- Traceable research URLs when available
- Clear separation of evidence, inference, assumptions and uncertainty
- Graceful error handling
- Downloadable Markdown report

## Technology

- Python 3.12
- CrewAI 1.15.22
- Streamlit 1.64.0
- Groq `openai/gpt-oss-120b`

The project deliberately avoids Groq Compound because it was decommissioned on September 21, 2026.

## Project structure

```text
industria-ai/
├── app.py
├── requirements.txt
├── runtime.txt
├── README.md
├── .gitignore
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── agents/
├── tasks/
├── tools/
├── config/
├── workflow/
├── utils/
└── assets/
```

## Local installation

1. Install Python 3.12.
2. Open a terminal in this folder.
3. Create a virtual environment:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

4. Install packages:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

5. Set your Groq key.

Windows PowerShell:

```powershell
$env:GROQ_API_KEY="YOUR_KEY"
```

macOS/Linux:

```bash
export GROQ_API_KEY="YOUR_KEY"
```

6. Run:

```bash
streamlit run app.py
```

## Streamlit Cloud

Push the repository to GitHub, create an app in Streamlit Community Cloud, select `app.py` as the main file, and add the following secret in the app's Secrets settings:

```toml
GROQ_API_KEY = "your-real-key"
```

Never commit `.streamlit/secrets.toml` or an API key to GitHub.

## Demo scenarios

### Manufacturing
A production line is experiencing increasing dimensional defects after several hours of operation.

### Software
An application became significantly slower after a software update.

### Biotechnology
A bioprocess is producing inconsistent output between batches.

## Safety

Industria-AI is a decision-support system, not an autonomous decision-maker. Outputs may contain errors, omissions or incorrect inferences. High-risk engineering, medical, legal, financial, chemical and safety-critical matters require qualified human verification before action.

## Limitations of this MVP

- Web search is intentionally lightweight and may fail or return incomplete results.
- The application does not guarantee source completeness.
- It does not execute real-world actions or control equipment.
- It does not expose hidden chain-of-thought; it displays concise findings, evidence and uncertainty.

## Future improvements

- Stronger search provider / source-quality scoring
- PDF and user-document evidence ingestion
- Structured evidence database
- Persistent project history
- More domain specialists
- CrewAI Flows for a production-grade state machine
- Automated evaluation tests

## Responsible AI principle

**AI analyzes. AI cross-checks. Human verifies. AI finalizes the decision-support output.**
