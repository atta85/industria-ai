import streamlit as st
from workflow.orchestrator import IndustriaOrchestrator

st.set_page_config(page_title='Industria-AI', page_icon='🏭', layout='wide')

st.title('🏭 Industria-AI')
st.caption('Human-in-the-Loop Multi-Agent Industrial Problem Analysis & Decision Support')

if 'orch' not in st.session_state:
    st.session_state.orch = IndustriaOrchestrator()
if 'result' not in st.session_state:
    st.session_state.result = None
if 'scope' not in st.session_state:
    st.session_state.scope = None
if 'routing' not in st.session_state:
    st.session_state.routing = None

with st.sidebar:
    st.header('System status')
    st.success('CrewAI multi-agent architecture')
    st.info('Maximum 2 specialist agents per run to control Groq TPM usage.')
    st.markdown('**Human checkpoints**\n1. Confirm / Modify / Stop\n2. Accept / Reanalyze / Reject')

problem = st.text_area('Describe the problem', height=180, placeholder='Example: A CNC-machined aluminum housing has recurring dimensional errors on one bore after several hours of production.')
context = st.text_area('Optional context / constraints', height=100, placeholder='Process, equipment, symptoms, measurements, safety constraints, budget, etc.')

if st.button('1. Analyze & Route', type='primary', disabled=not problem.strip()):
    with st.spinner('Scoping the problem and selecting relevant specialists...'):
        try:
            scope, routing = st.session_state.orch.scope_and_route(problem, context)
            st.session_state.scope, st.session_state.routing = scope, routing
            st.session_state.result = None
        except Exception as e:
            st.error(f'Could not initialize analysis: {e}')

if st.session_state.scope:
    st.subheader('Checkpoint 1 — Human confirmation')
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('**Problem Scoping Agent**')
        st.write(st.session_state.scope)
    with c2:
        st.markdown('**Domain Router**')
        st.write(st.session_state.routing.get('routing_reason', ''))
        st.write('Selected: ' + ', '.join(st.session_state.routing.get('selected_specialists', [])))
    with c3:
        st.markdown('**Your control**')
        decision = st.radio('Choose', ['Confirm', 'Modify', 'Stop'], horizontal=True, key='cp1')
        modified = st.text_area('Modification (if needed)', key='mod1', height=90)
        if st.button('Continue', key='continue1'):
            if decision == 'Stop':
                st.warning('Investigation stopped by human decision.')
            else:
                p2 = problem if decision == 'Confirm' else (modified.strip() or problem)
                with st.spinner('Running the selected agents and evidence review...'):
                    try:
                        st.session_state.result = st.session_state.orch.investigate(p2, context, st.session_state.routing)
                    except Exception as e:
                        st.error(f'Investigation failed: {e}')

if st.session_state.result:
    r = st.session_state.result
    st.divider()
    st.subheader('Investigation')
    st.write('**Activated specialists:** ' + ', '.join(r['selected_specialists']))
    st.write('**Research sources:** ' + str(len(r['research'].get('sources', []))))

    tabs = st.tabs(['Agent Findings', 'Evidence', 'Synthesis', 'Critical Review', 'Audit Trail'])
    with tabs[0]:
        for name, finding in r['specialist_findings'].items():
            with st.expander(name, expanded=True): st.write(finding)
    with tabs[1]:
        for s in r['research'].get('sources', []):
            st.markdown(f"**{s.get('title','Source')}** — {s.get('url','')}\n\n{s.get('snippet','')}")
        if not r['research'].get('sources'): st.info('No external sources were retrieved; conclusions are marked accordingly.')
    with tabs[2]: st.write(r['synthesis'])
    with tabs[3]: st.write(r['review'])
    with tabs[4]: st.json(r['audit'])

    st.subheader('Checkpoint 2 — Human decision')
    decision2 = st.radio('Decision', ['Accept', 'Modify & Reanalyze', 'Reject'], horizontal=True, key='cp2')
    feedback = st.text_area('Human feedback / required changes', key='mod2', height=100)
    if st.button('Apply decision', key='apply2'):
        if decision2 == 'Accept':
            with st.spinner('Generating final decision-support report...'):
                try:
                    st.session_state.result['final_report'] = st.session_state.orch.final_report(r, feedback)
                    st.success('Final report generated.')
                    st.markdown(st.session_state.result['final_report'])
                except Exception as e: st.error(f'Final report failed: {e}')
        elif decision2 == 'Reject':
            st.warning('Analysis rejected by human decision. No final recommendation was generated.')
        else:
            with st.spinner('Reanalyzing with human feedback...'):
                try:
                    st.session_state.result = st.session_state.orch.investigate(problem, context + '\nHuman feedback: ' + feedback, st.session_state.routing)
                    st.rerun()
                except Exception as e: st.error(f'Reanalysis failed: {e}')

st.divider()
st.caption('Responsible AI: Industria-AI is decision support, not an autonomous decision-maker. High-risk decisions require qualified human review.')
