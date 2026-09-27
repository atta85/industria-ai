import json, re
from crewai import Crew, Process
from agents.core_agents import scoper, router, specialist, research_agent, synthesis_agent, reviewer_agent, report_agent
from tasks.analysis_tasks import scope_task, route_task, research_task, specialist_task, synthesis_task, review_task, final_task

def parse_json(text):
    if hasattr(text, "raw"): text=text.raw
    text=str(text).strip()
    text=re.sub(r"^```json\s*|^```\s*|\s*```$", "", text, flags=re.I).strip()
    start=text.find("{"); end=text.rfind("}")
    if start>=0 and end>start:
        try: return json.loads(text[start:end+1])
        except Exception: pass
    raise ValueError("The AI returned an invalid structured response.")

class IndustriaOrchestrator:
    def scope_problem(self, problem, domain="", objective="", constraints="", outcome="", feedback=""):
        context={"domain":domain,"objective":objective,"constraints":constraints,"desired_outcome":outcome}
        a=scoper()
        result=Crew(agents=[a], tasks=[scope_task(a, problem, context, feedback)], process=Process.sequential, verbose=False).kickoff()
        return parse_json(result)

    def route_problem(self, problem, scope, feedback=""):
        a=router(); result=Crew(agents=[a], tasks=[route_task(a, problem, scope, feedback)], process=Process.sequential, verbose=False).kickoff()
        data=parse_json(result)
        allowed=set(__import__('agents.core_agents',fromlist=['SPECIALISTS']).SPECIALISTS)
        data["selected_specialists"]=[x for x in data.get("selected_specialists",[]) if x in allowed][:5]
        if not data["selected_specialists"]: raise ValueError("The router selected no valid specialists.")
        return data

    def investigate(self, problem, scope, routing, feedback=""):
        names=routing["selected_specialists"]
        ra=research_agent(); rt=research_task(ra, problem, scope, names)
        research_result=Crew(agents=[ra], tasks=[rt], process=Process.sequential, verbose=False).kickoff()
        research=str(research_result)
        specialists=[]; tasks=[]
        for name in names:
            a=specialist(name); specialists.append(a); tasks.append(specialist_task(a,name,problem,scope,research))
        specialist_result=Crew(agents=specialists,tasks=tasks,process=Process.sequential,verbose=False).kickoff()
        synthesis=synthesis_agent(); synth_result=Crew(agents=[synthesis],tasks=[synthesis_task(synthesis,problem,scope,research,str(specialist_result))],process=Process.sequential,verbose=False).kickoff()
        reviewer=reviewer_agent(); review_result=Crew(agents=[reviewer],tasks=[review_task(reviewer,str(synth_result))],process=Process.sequential,verbose=False).kickoff()
        return {"evidence":[research],"specialist_findings":str(specialist_result),"proposal":str(synth_result),"critical_review":str(review_result),"hypotheses":[str(synth_result)],"alternatives":[],"risks":[],"uncertainties":[]}

    def revise(self, problem, scope, routing, result, feedback):
        a=synthesis_agent()
        revised=Crew(agents=[a],tasks=[synthesis_task(a,problem,scope,str(result.get('evidence','')),str(result.get('specialist_findings',''))+"\n\nHUMAN REVISION REQUEST:\n"+feedback)],process=Process.sequential,verbose=False).kickoff()
        r=reviewer_agent(); critique=Crew(agents=[r],tasks=[review_task(r,str(revised))],process=Process.sequential,verbose=False).kickoff()
        result["proposal"]=str(revised); result["critical_review"]=str(critique); result["human_feedback"]=feedback
        return result

    def final_report(self, problem, scope, routing, result, status, feedback):
        a=report_agent(); out=Crew(agents=[a],tasks=[final_task(a,problem,scope,routing,result,status,feedback)],process=Process.sequential,verbose=False).kickoff()
        return str(out)
