import streamlit as st
from workflow.orchestrator import IndustriaOrchestrator
from utils.audit import add_audit, render_audit
from utils.validation import get_groq_key, safe_text

st.set_page_config(page_title="Industria-AI", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.hero{padding:1.4rem 1.6rem;border-radius:18px;background:linear-gradient(135deg,#0f172a,#1e3a5f);color:white;margin-bottom:1rem}
.hero h1{margin:0;font-size:2.5rem}.hero p{font-size:1.05rem;opacity:.9}
.step{padding:.45rem .7rem;border-radius:10px;background:#eef2f7;text-align:center;font-size:.85rem}
.card{padding:1rem;border:1px solid #dbe3ec;border-radius:14px;background:#fff;margin-bottom:.7rem}
.warning{padding:.8rem 1rem;border-left:5px solid #e09f3e;background:#fff8e8;border-radius:8px}
</style>
<div class="hero"><h1>🏭 INDUSTRIA-AI</h1><p>Human-in-the-Loop Multi-Agent Problem Analysis & Decision Support</p></div>
""", unsafe_allow_html=True)

if "orch" not in st.session_state:
    st.session_state.orch = IndustriaOrchestrator()
if "phase" not in st.session_state:
    st.session_state.phase = "input"
if "audit" not in st.session_state:
    st.session_state.audit = []

orch = st.session_state.orch

with st.sidebar:
    st.markdown("### Workflow")
    labels = [("input","① DEFINE"),("scope","② VERIFY"),("analysis","③ INVESTIGATE"),("review","④ HUMAN CHECK"),("verified","⑤ REPORT")]
    for key,label in labels:
        mark = "●" if st.session_state.phase == key else "○"
        st.write(f"{mark} {label}")
    st.divider()
    st.caption("AI analyzes. AI cross-checks. Human verifies. AI finalizes the decision-support output.")
    if st.button("Reset analysis", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

if not get_groq_key():
    st.error("GROQ_API_KEY is missing. Add it to Streamlit Secrets or your local environment before running an analysis.")
    st.info("Expected secret name: GROQ_API_KEY")
    st.stop()

if st.session_state.phase == "input":
    st.subheader("Define the problem")
    col1,col2 = st.columns([2,1])
    with col1:
        problem = st.text_area("Describe the problem", height=220, placeholder="Example: A production line is experiencing increasing dimensional defects after several hours of operation.")
        objective = st.text_input("Objective (optional)")
        constraints = st.text_area("Constraints / known information (optional)", height=100)
    with col2:
        domain = st.selectbox("Known domain (optional)", ["Not sure", "Mechanical Engineering", "Manufacturing", "Electrical/Electronics", "Civil Engineering", "Chemical Engineering", "Materials Science", "Biotechnology", "Software/IT", "Data/AI", "Energy", "Environmental", "Quality/Reliability", "Operations"])
        outcome = st.text_area("Desired outcome (optional)", height=100)
        st.markdown('<div class="warning">For medical, legal, financial, hazardous, or safety-critical matters, qualified professionals must verify any output before action.</div>', unsafe_allow_html=True)
    if st.button("🔍 Analyze problem", type="primary", use_container_width=True):
        if len(problem.strip()) < 20:
            st.warning("Please provide a more detailed problem description (at least 20 characters).")
        else:
            with st.spinner("Problem Scoping Agent is analyzing the problem..."):
                try:
                    scope = orch.scope_problem(problem, domain, objective, constraints, outcome)
                    st.session_state.problem = problem
                    st.session_state.context = {"domain":domain,"objective":objective,"constraints":constraints,"outcome":outcome}
                    st.session_state.scope = scope
                    st.session_state.phase = "scope"
                    add_audit(st.session_state.audit, "Problem submitted", problem[:180])
                    add_audit(st.session_state.audit, "Problem scoped", scope.get("summary", "Scope generated"))
                    st.rerun()
                except Exception as e:
                    st.error(safe_text(e))

elif st.session_state.phase == "scope":
    st.subheader("AI Understanding of Your Problem")
    s = st.session_state.scope
    st.info(s.get("summary", "No summary returned."))
    c1,c2 = st.columns(2)
    with c1:
        st.markdown("**Relevant domains**")
        for x in s.get("domains",[]): st.write("•",x)
        st.markdown("**Objectives**")
        for x in s.get("objectives",[]): st.write("•",x)
        st.markdown("**Constraints**")
        for x in s.get("constraints",[]): st.write("•",x)
    with c2:
        st.markdown("**Assumptions**")
        for x in s.get("assumptions",[]): st.write("•",x)
        st.markdown("**Missing information**")
        for x in s.get("missing_information",[]): st.write("•",x)
    feedback = st.text_area("Correction (only if the AI misunderstood something)", height=100)
    a,b,c = st.columns(3)
    if a.button("✓ CONFIRM", type="primary", use_container_width=True):
        st.session_state.scope_feedback = feedback.strip()
        with st.spinner("Routing the problem to relevant specialists..."):
            try:
                routing = orch.route_problem(st.session_state.problem, st.session_state.scope, feedback)
                st.session_state.routing = routing
                st.session_state.phase = "analysis"
                add_audit(st.session_state.audit, "Human confirmed interpretation", feedback or "No modification")
                add_audit(st.session_state.audit, "Specialists selected", ", ".join(routing.get("selected_specialists",[])))
                st.rerun()
            except Exception as e: st.error(safe_text(e))
    if b.button("✏ MODIFY & RECHECK", use_container_width=True):
        if not feedback.strip(): st.warning("Enter the correction first.")
        else:
            with st.spinner("Rechecking the problem interpretation..."):
                try:
                    st.session_state.scope = orch.scope_problem(st.session_state.problem, st.session_state.context.get("domain",""), st.session_state.context.get("objective",""), st.session_state.context.get("constraints",""), st.session_state.context.get("outcome",""), feedback)
                    add_audit(st.session_state.audit, "Human modified interpretation", feedback)
                    st.rerun()
                except Exception as e: st.error(safe_text(e))
    if c.button("⛔ STOP", use_container_width=True):
        st.session_state.phase = "input"; st.warning("Analysis stopped.")

elif st.session_state.phase == "analysis":
    st.subheader("Multi-Agent Investigation")
    r = st.session_state.routing
    st.success("Selected expertise: " + ", ".join(r.get("selected_specialists",[])))
    st.caption(r.get("reasoning_summary", "The router selected the specialists based on the confirmed problem scope."))
    with st.expander("Agents active in this investigation", expanded=True):
        for name in ["Problem Scoping Agent","Domain Router"] + r.get("selected_specialists",[]) + ["Research & Evidence Agent","Synthesis Agent","Critical Reviewer"]:
            st.write("🟢", name)
    if st.button("▶ Run investigation", type="primary", use_container_width=True):
        with st.status("CrewAI agents are investigating the problem...", expanded=True) as status:
            try:
                result = orch.investigate(st.session_state.problem, st.session_state.scope, r, st.session_state.scope_feedback)
                st.session_state.result = result
                st.session_state.phase = "review"
                add_audit(st.session_state.audit, "Investigation completed", "Specialists, research, synthesis and critical review completed.")
                status.update(label="Investigation complete", state="complete")
                st.rerun()
            except Exception as e:
                status.update(label="Investigation failed", state="error")
                st.error(safe_text(e))

elif st.session_state.phase == "review":
    st.subheader("🧑‍🔬 Human Verification Required")
    result = st.session_state.result
    st.markdown("### AI-Proposed Decision Support")
    st.markdown(result.get("proposal", "No proposal generated."))
    cols = st.columns(2)
    with cols[0]:
        st.markdown("#### Evidence")
        for e in result.get("evidence",[]): st.write("•",e)
        st.markdown("#### Root-cause hypotheses")
        for x in result.get("hypotheses",[]): st.write("•",x)
        st.markdown("#### Alternative explanations")
        for x in result.get("alternatives",[]): st.write("•",x)
    with cols[1]:
        st.markdown("#### Risks & limitations")
        for x in result.get("risks",[]): st.write("•",x)
        st.markdown("#### Uncertainties")
        for x in result.get("uncertainties",[]): st.write("•",x)
        st.markdown("#### Critical review")
        st.write(result.get("critical_review", ""))
    st.markdown("### Human decision")
    feedback2 = st.text_area("Your verification comments / requested changes", height=120)
    a,b,c = st.columns(3)
    if a.button("🟢 ACCEPT", type="primary", use_container_width=True):
        with st.spinner("Generating the verified decision-support report..."):
            try:
                final = orch.final_report(st.session_state.problem, st.session_state.scope, r, result, "ACCEPT", feedback2)
                st.session_state.final = final; st.session_state.verification = "ACCEPTED"; st.session_state.phase="verified"
                add_audit(st.session_state.audit, "Human accepted proposed analysis", feedback2 or "No additional comments")
                add_audit(st.session_state.audit, "Verified report generated", "Human approval recorded.")
                st.rerun()
            except Exception as e: st.error(safe_text(e))
    if b.button("🟡 MODIFY / REANALYZE", use_container_width=True):
        if not feedback2.strip(): st.warning("Please enter feedback for the revision.")
        else:
            with st.spinner("Revising the analysis using your feedback..."):
                try:
                    revised = orch.revise(st.session_state.problem, st.session_state.scope, r, result, feedback2)
                    st.session_state.result = revised
                    add_audit(st.session_state.audit, "Human requested revision", feedback2)
                    st.rerun()
                except Exception as e: st.error(safe_text(e))
    if c.button("🔴 REJECT", use_container_width=True):
        st.session_state.verification="REJECTED"; st.session_state.phase="input"
        add_audit(st.session_state.audit, "Human rejected proposed analysis", feedback2 or "No reason supplied")
        st.warning("The proposed analysis was rejected. No verified report was generated.")

elif st.session_state.phase == "verified":
    st.subheader("✅ VERIFIED DECISION SUPPORT REPORT")
    st.success(f"Human verification status: {st.session_state.verification}")
    final = st.session_state.final
    st.markdown(final)
    st.download_button("⬇ Download report", final, file_name="industria_ai_verified_report.md", mime="text/markdown", use_container_width=True)

st.divider()
with st.expander("🧾 AI Audit Trail", expanded=False):
    render_audit(st.session_state.audit)
