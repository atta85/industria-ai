from crewai import Agent, LLM
from config.settings import SETTINGS, groq_api_key
from tools.web_search import WebSearchTool

SPECIALISTS = {
    "Mechanical Engineering Specialist": "mechanics, machine systems, forces, vibration, deformation, tolerances and engineering design",
    "Manufacturing Specialist": "manufacturing processes, production systems, tooling, process parameters and process variation",
    "Materials Science Specialist": "material properties, degradation, thermal behavior, composition, interfaces and failure mechanisms",
    "Electrical/Electronics Specialist": "electrical systems, electronics, power, instrumentation, controls and faults",
    "Civil Engineering Specialist": "structures, geotechnics, construction, infrastructure, loads and civil systems",
    "Chemical Engineering Specialist": "chemical processes, reaction systems, mass/energy balances, transport and process safety",
    "Biotechnology Specialist": "bioprocesses, biological systems, fermentation, batch variation and biotechnology operations",
    "Software Engineering Specialist": "software architecture, code performance, databases, APIs, testing, deployment and debugging",
    "Data/AI Specialist": "data quality, statistics, machine learning, analytics, model behavior and data pipelines",
    "Energy Specialist": "energy systems, efficiency, power generation, storage and thermal-energy interactions",
    "Environmental Specialist": "environmental systems, emissions, waste, water, sustainability and environmental constraints",
    "Quality/Reliability Specialist": "quality systems, defect patterns, reliability, FMEA, root-cause analysis and process capability",
    "Operations/Process Specialist": "operations, workflows, bottlenecks, capacity, maintenance, scheduling and process optimization",
}

def llm():
    key=groq_api_key()
    if not key: raise RuntimeError("GROQ_API_KEY is missing")
    return LLM(model=SETTINGS.model, api_key=key, base_url="https://api.groq.com/openai/v1", temperature=SETTINGS.temperature, max_tokens=SETTINGS.max_tokens)

def scoper():
    return Agent(role="Problem Scoping Agent", goal="Convert an ambiguous real-world problem into a precise, bounded analysis brief.", backstory="You are a senior systems analyst. You separate facts, user-provided information, assumptions, unknowns and objectives. Never invent missing facts.", llm=llm(), allow_delegation=False, verbose=False)

def router():
    return Agent(role="Domain Expertise Router", goal="Select only the specialist expertise genuinely relevant to the confirmed problem.", backstory="You are an interdisciplinary coordinator. You route problems to a small set of relevant experts and explain why each is needed.", llm=llm(), allow_delegation=False, verbose=False)

def specialist(name):
    expertise=SPECIALISTS[name]
    return Agent(role=name, goal=f"Analyze the problem from the perspective of {expertise}. Identify mechanisms, hypotheses, evidence needs, risks and practical verification steps.", backstory=f"You are a specialist in {expertise}. You must distinguish evidence from inference and never pretend uncertain claims are established facts.", llm=llm(), allow_delegation=False, verbose=False)

def research_agent():
    return Agent(role="Research & Evidence Agent", goal="Gather traceable external evidence relevant to the problem and proposed hypotheses.", backstory="You are a technical research analyst. Prefer official, government, standards, manufacturer, peer-reviewed and reputable technical sources. Never fabricate references. Clearly mark search failures and uncertainty.", llm=llm(), tools=[WebSearchTool()], allow_delegation=False, verbose=False)

def synthesis_agent():
    return Agent(role="Synthesis Agent", goal="Integrate specialist findings and evidence into competing hypotheses and practical decision-support options.", backstory="You reconcile multidisciplinary findings without forcing agreement. You explicitly identify evidence, inference, assumptions and uncertainty.", llm=llm(), allow_delegation=False, verbose=False)

def reviewer_agent():
    return Agent(role="Critical Reviewer / Devil's Advocate", goal="Challenge the analysis, expose unsupported claims and alternative explanations, and identify what must be verified by a human.", backstory="You are an adversarial technical reviewer. Your success is finding what could be wrong, not agreeing with the team.", llm=llm(), allow_delegation=False, verbose=False)

def report_agent():
    return Agent(role="Decision-Support Report Agent", goal="Produce a clear, traceable verified decision-support report after human verification.", backstory="You are a technical report editor. You never claim certainty beyond the evidence and always preserve human verification status.", llm=llm(), allow_delegation=False, verbose=False)
