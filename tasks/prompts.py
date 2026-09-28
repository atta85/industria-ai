def scope_prompt(problem, context):
    return f'''Problem:\n{problem}\nContext:\n{context}\n\nClarify objective, symptoms, known facts, constraints, missing information and 2-4 testable questions. Keep under 180 words.'''

def route_prompt(scope, specialists, max_n):
    return f'''Scoping summary:\n{scope}\n\nAvailable specialist domains: {specialists}\nSelect at most {max_n} domains. Return ONLY JSON: {{"selected_specialists":["..."],"routing_reason":"..."}}. Do not select unrelated domains.'''

def specialist_prompt(problem, context, name, role):
    return f'''Problem: {problem}\nContext: {context}\nRole: {name}\nGoal: {role['goal']}\n\nGive: likely mechanisms/causes, evidence needed, practical checks, and 1-2 possible interventions. Label assumptions. Keep under 220 words. Do not fabricate citations.'''

def research_prompt(problem, findings, sources):
    return f'''Problem: {problem}\nSpecialist findings: {findings}\nExternal search results: {sources}\n\nAssess which claims are supported by sources. Cite only the URLs/titles supplied. Separate Evidence, Agent inference, Assumption, and Uncertainty. If sources are weak or absent, say so. Keep under 250 words.'''

def synthesis_prompt(problem, findings, evidence):
    return f'''Problem: {problem}\nFindings: {findings}\nEvidence review: {evidence}\n\nSynthesize root-cause hypotheses, alternatives, recommended diagnostic sequence, options, risks and uncertainty. Do not make an irreversible decision. Keep under 260 words.'''

def review_prompt(problem, synthesis, evidence):
    return f'''Problem: {problem}\nSynthesis: {synthesis}\nEvidence: {evidence}\n\nAct as Devil's Advocate. Identify unsupported assumptions, contradictions, missing tests, safety concerns and what would falsify the leading hypotheses. Keep under 220 words.'''

def final_prompt(result, feedback):
    return f'''Create a final human-reviewable decision-support report from this investigation.\nInvestigation: {result}\nHuman feedback: {feedback}\n\nUse sections: Problem, Evidence, Findings, Options, Risks, Validation Plan, Uncertainty, Human Decision Required. Preserve source URLs where supplied. Do not claim certainty or autonomous approval. Keep under 500 words.'''
