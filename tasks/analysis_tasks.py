import json
from crewai import Task

def scope_task(agent, problem, context, feedback=""):
    return Task(agent=agent, description=f"""Analyze this user problem. Return ONLY valid JSON with keys: summary (string), domains (array), objectives (array), constraints (array), assumptions (array), missing_information (array), risk_level (NORMAL/ELEVATED/HIGH-RISK). Do not invent facts.\nPROBLEM:\n{problem}\nCONTEXT:\n{json.dumps(context, ensure_ascii=False)}\nHUMAN CORRECTION:\n{feedback or 'None'}""", expected_output="Valid JSON object with the requested keys.")

def route_task(agent, problem, scope, feedback=""):
    names=["Mechanical Engineering Specialist","Manufacturing Specialist","Materials Science Specialist","Electrical/Electronics Specialist","Civil Engineering Specialist","Chemical Engineering Specialist","Biotechnology Specialist","Software Engineering Specialist","Data/AI Specialist","Energy Specialist","Environmental Specialist","Quality/Reliability Specialist","Operations/Process Specialist"]
    return Task(agent=agent, description=f"""Select only relevant specialists from this exact list: {json.dumps(names)}. Return ONLY valid JSON with keys selected_specialists (array of exact names), reasoning_summary (string). Select 2-5 specialists unless the problem genuinely needs fewer.\nPROBLEM: {problem}\nSCOPE: {json.dumps(scope)}\nHUMAN CORRECTION: {feedback or 'None'}""", expected_output="Valid JSON object containing selected_specialists and reasoning_summary.")

def research_task(agent, problem, scope, specialists):
    return Task(agent=agent, description=f"""Research the problem using your web_search tool. Search for evidence relevant to the problem and the selected expertise. Prefer authoritative and recent sources. Return a concise evidence dossier with: claims, source title, URL, domain, and why each source is relevant. Do not fabricate citations. If search fails, explicitly say so.\nPROBLEM: {problem}\nSCOPE: {json.dumps(scope)}\nSPECIALISTS: {json.dumps(specialists)}""", expected_output="A traceable evidence dossier with source titles and URLs.")

def specialist_task(agent, name, problem, scope, research):
    return Task(agent=agent, description=f"""Analyze the problem as the {name}. Produce: 1) key findings, 2) plausible hypotheses, 3) evidence that supports/contradicts each hypothesis, 4) missing data, 5) safe verification tests or next steps, 6) risks. Use the research dossier as supporting context. Do not invent measurements or references.\nPROBLEM: {problem}\nSCOPE: {json.dumps(scope)}\nRESEARCH: {research}""", expected_output="A concise specialist analysis explicitly separating evidence, inference, assumptions and uncertainty.")

def synthesis_task(agent, problem, scope, research, specialist_outputs):
    return Task(agent=agent, description=f"""Integrate the multidisciplinary findings. Produce a proposed decision-support analysis containing: proposal, evidence, hypotheses, alternatives, risks, uncertainties, recommended verification steps, and source references. Do not choose an irreversible real-world action.\nPROBLEM: {problem}\nSCOPE: {json.dumps(scope)}\nRESEARCH: {research}\nSPECIALIST FINDINGS:\n{specialist_outputs}""", expected_output="A structured decision-support proposal with evidence and uncertainty clearly distinguished.")

def review_task(agent, synthesis):
    return Task(agent=agent, description=f"""Critically review the following proposed analysis. Identify unsupported claims, weak evidence, contradictions, alternative explanations, missing information, unsafe assumptions, and whether revision is required. Return a concise critical-review memo.\nPROPOSED ANALYSIS:\n{synthesis}""", expected_output="A critical review identifying weaknesses and required verification.")

def final_task(agent, problem, scope, routing, result, status, feedback):
    return Task(agent=agent, description=f"""Create the VERIFIED DECISION SUPPORT REPORT. Human verification status is {status}. Human feedback: {feedback or 'None'}. Preserve uncertainty and do not claim guaranteed correctness. Include: problem statement, human-confirmed interpretation, domains, agents consulted, evidence, key findings, root-cause hypotheses, alternative explanations, proposed solutions, risks/limitations, human feedback, verification status, final action plan, references and warnings.\nPROBLEM: {problem}\nSCOPE: {json.dumps(scope)}\nROUTING: {json.dumps(routing)}\nANALYSIS:\n{result}""", expected_output="A professional Markdown verified decision-support report.")
