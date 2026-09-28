import json, re, time

# CrewAI 1.15.x may inject an unsupported cache_breakpoint field into Groq/LiteLLM messages.
try:
    import crewai.llms.cache as crew_cache
    crew_cache.mark_cache_breakpoint = lambda msg: msg
except Exception:
    pass

from crewai import Agent, Crew, Process, Task
from agents.core_agents import core_agents
from agents.specialists import SPECIALIST_ROLES
from tasks.prompts import scope_prompt, route_prompt, specialist_prompt, research_prompt, synthesis_prompt, review_prompt, final_prompt
from tools.research_tool import search_web

MODEL = 'groq/openai/gpt-oss-120b'
MAX_SPECIALISTS = 2


def _key():
    import os
    try:
        return os.environ.get('GROQ_API_KEY') or __import__('streamlit').secrets.get('GROQ_API_KEY')
    except Exception:
        return os.environ.get('GROQ_API_KEY')


class IndustriaOrchestrator:
    def __init__(self):
        if not _key():
            raise RuntimeError('GROQ_API_KEY is missing. Add it in Streamlit Cloud → Settings → Secrets.')
        self.audit = []

    def _llm(self):
        from crewai import LLM
        return LLM(model=MODEL, api_key=_key(), temperature=0.1, max_tokens=450)

    def _call(self, agent, description):
        last = None
        for attempt in range(4):
            try:
                task = Task(description=description, expected_output='Concise, factual output. Do not reveal private chain-of-thought.', agent=agent)
                crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
                out = str(crew.kickoff())
                self.audit.append({'agent': agent.role, 'status': 'completed', 'attempt': attempt + 1})
                return out
            except Exception as e:
                last = e
                msg = str(e).lower()
                if not any(x in msg for x in ['rate limit', 'ratelimit', 'rate_limit_exceeded', 'tokens per minute', 'tpm']):
                    self.audit.append({'agent': agent.role, 'status': 'failed', 'error': str(e)[:500]})
                    raise
                m = re.search(r'try again in\s*([0-9.]+)s', str(e), re.I)
                wait = min(float(m.group(1)) + 1.0 if m else 3.0, 12.0)
                time.sleep(wait)
        raise RuntimeError(f'Groq rate limit persisted after retries: {last}')

    def scope_and_route(self, problem, context=''):
        llm = self._llm()
        scope_agent = Agent(role='Problem Scoping Agent', goal='Clarify the engineering or industry problem.', backstory='A concise systems analyst.', llm=llm, verbose=False)
        scoped = self._call(scope_agent, scope_prompt(problem, context))
        router = Agent(role='Domain Router', goal='Select only the most relevant specialist domains.', backstory='A multidisciplinary triage expert.', llm=llm, verbose=False)
        raw = self._call(router, route_prompt(scoped, list(SPECIALIST_ROLES.keys()), MAX_SPECIALISTS))
        try:
            data = json.loads(raw[raw.find('{'):raw.rfind('}')+1])
        except Exception:
            data = {'selected_specialists': [], 'routing_reason': raw}
        valid = [x for x in data.get('selected_specialists', []) if x in SPECIALIST_ROLES][:MAX_SPECIALISTS]
        return scoped, {'selected_specialists': valid, 'routing_reason': data.get('routing_reason', '')}

    def investigate(self, problem, context, routing):
        selected = routing.get('selected_specialists', [])[:MAX_SPECIALISTS]
        llm = self._llm()
        findings = {}
        for name in selected:
            role = SPECIALIST_ROLES[name]
            agent = Agent(role=name, goal=role['goal'], backstory=role['backstory'], llm=llm, verbose=False)
            findings[name] = self._call(agent, specialist_prompt(problem, context, name, role))

        research_agent = Agent(role='Research & Evidence Agent', goal='Find traceable external evidence and separate evidence from inference.', backstory='A careful technical research analyst.', llm=llm, verbose=False)
        search_results = search_web(problem, max_results=4)
        evidence_text = self._call(research_agent, research_prompt(problem, findings, search_results))

        synth_agent = Agent(role='Synthesis Agent', goal='Combine specialist findings and evidence into decision-support options.', backstory='A systems integration analyst.', llm=llm, verbose=False)
        synthesis = self._call(synth_agent, synthesis_prompt(problem, findings, evidence_text))

        review_agent = Agent(role='Critical Reviewer / Devil’s Advocate', goal='Challenge assumptions, identify gaps, risks and contradictions.', backstory='An independent technical reviewer.', llm=llm, verbose=False)
        review = self._call(review_agent, review_prompt(problem, synthesis, evidence_text))

        return {
            'selected_specialists': selected,
            'specialist_findings': findings,
            'research': {'sources': search_results, 'analysis': evidence_text},
            'synthesis': synthesis,
            'review': review,
            'audit': list(self.audit),
        }

    def final_report(self, result, feedback=''):
        llm = self._llm()
        agent = Agent(role='Final Decision-Support Report Writer', goal='Produce a concise auditable report without autonomous decision-making.', backstory='A technical report writer who preserves uncertainty and human control.', llm=llm, verbose=False)
        return self._call(agent, final_prompt(result, feedback))
