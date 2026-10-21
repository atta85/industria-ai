"""
Industria-AI: industrial problem analyzer.

Flow (two-step mode):  Describe -> Quick check -> Analysis -> Final review -> Report
Flow (one-step mode):  Describe -> Analysis -> Final review -> Report

The human decides at every gate. The final report is assembled by code from
what the human reviewed.
"""

import queue
import threading
import time
import warnings
from datetime import datetime

import streamlit as st

st.set_page_config(page_title="Industria-AI", page_icon=":material/precision_manufacturing:", layout="wide")
warnings.filterwarnings("ignore", message=".*callbacks cannot be serialized.*")

import litellm  # noqa: E402

from crew.intake_crew import run_intake  # noqa: E402
from crew.investigation_crew import run_investigation  # noqa: E402
from crew.specialist_pool import MAX_SPECIALISTS, SPECIALIST_POOL, clean_selection, label  # noqa: E402
from utils import llm_guard, ui  # noqa: E402
from utils.data_profile import DataError, load_csv, profile, trend_chart  # noqa: E402
from utils.diagrams import fishbone, likelihood_chart  # noqa: E402
from utils.industries import OTHER, example_for, industry_options  # noqa: E402
from utils.pdf_builder import build_pdf  # noqa: E402
from utils.report_builder import build_report, report_to_markdown  # noqa: E402
from utils.storage import Storage  # noqa: E402

llm_guard.apply_llm_guard()
ui.inject_css()

TWO_STEPS = [("Describe", "Industry, problem and optional data"), ("Quick check", "Confirm I understood you"),
             ("Analysis", "Specialists investigate"), ("Final review", "Accept, modify or reject"),
             ("Report", "Download and give feedback")]
ONE_STEPS = [("Describe", "Problem plus details you know"), ("Analysis", "Specialists investigate"),
             ("Final review", "Accept, modify or reject"), ("Report", "Download and give feedback")]
DETAIL_FIELDS = [("objectives", "Objectives"), ("constraints", "Constraints"),
                 ("available_data", "Available data"), ("desired_outcome", "Desired outcome")]
MODE_LABELS = {"two-step": "Two-step check (recommended)", "one-step": "One-step check (faster)"}
MODE_CAPTIONS = [
    "I first show how I understood your problem and suggest objectives and constraints. You correct them, "
    "then I analyze and you give the final decision. Best for new or unclear problems. About 30 seconds extra.",
    "I go straight to the analysis and you review the result at the end. You add the optional details "
    "yourself. A misunderstanding is only caught at the end, after a full analysis run.",
]

DEFAULTS = {
    "view": "app", "stage": "input", "mode": "two-step", "job": None, "error": None,
    "inputs": None, "data_profile": None, "trend_png": None,
    "intake": None, "confirmed": None, "ai_assumed": [], "investigation": None,
    "revision_used": False, "feedback_history": [], "audit": [], "report": None, "pdf_bytes": None,
    "models_note": "", "saved_msg": "", "show_modify": False, "fb_sent": False, "pending_feedback": None,
    "local_feedback": [], "keep_data": False, "restore_inputs": False, "need_key": False, "retry_job": None,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def secret(name, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:  # noqa: BLE001 - no secrets file at all
        return default


def auth_configured() -> bool:
    try:
        return bool(st.secrets["auth"].get("client_id"))
    except Exception:  # noqa: BLE001
        return False


def current_user():
    if not auth_configured():
        return None
    try:
        if st.user.is_logged_in:
            return {"name": st.user.get("name") or "", "email": st.user.get("email") or ""}
    except Exception:  # noqa: BLE001
        return None
    return None


@st.cache_resource(show_spinner=False)
def get_owner_llms(api_key):
    return llm_guard.build_llms(api_key)


def owner_key():
    return secret("GROQ_API_KEY") or ""


def own_key():
    """A personal Groq key the user added in this session (never stored)."""
    return st.session_state.get("user_groq_key") or ""


def active_key():
    return own_key() or owner_key()


def llms_for(key):
    # The shared key's LLM objects are cached; a personal key is used for this
    # session only and never cached or saved.
    return get_owner_llms(key) if key == owner_key() else llm_guard.build_llms(key)


@st.cache_resource(show_spinner=False)
def get_storage(url, key):
    return Storage(url, key)


def init_state():
    for k, v in DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v if not isinstance(v, (list, dict)) else type(v)(v)


def reset_analysis():
    keep_view = "app"
    for k in list(st.session_state.keys()):
        if k.startswith(("in_", "qc_", "mod_", "fb_")) or k in DEFAULTS:
            del st.session_state[k]
    init_state()
    st.session_state.view = keep_view


def log(event, detail=""):
    st.session_state.audit.append({"time": datetime.now().strftime("%H:%M:%S"), "event": event, "detail": detail})


def lines(text):
    return [x.strip(" -•\t") for x in str(text or "").splitlines() if x.strip(" -•\t")]


def context_text(c, inputs):
    def j(items):
        return "; ".join(items) if items else "not stated"
    return (f"Industry: {inputs['industry']}\n"
            f"Problem (confirmed interpretation): {c['problem_summary']}\n"
            f"Original problem statement: {inputs['problem']}\n"
            f"Objectives: {j(c.get('objectives'))}\nConstraints: {j(c.get('constraints'))}\n"
            f"Available data: {j(c.get('available_data'))}\nDesired outcome: {c.get('desired_outcome') or 'not stated'}\n"
            f"Assumptions: {j(c.get('assumptions'))}\nKnown missing information: {j(c.get('missing_information'))}")


def step_index():
    two = st.session_state.mode == "two-step"
    stage, job = st.session_state.stage, st.session_state.job
    if stage == "input":
        return 1
    if stage == "quick_check":
        return 2
    if stage == "analyzing":
        return 2 if (two and job == "intake") else (3 if two else 2)
    if stage == "review":
        return 4 if two else 3
    return 5 if two else 4


def friendly_error(exc) -> str:
    if isinstance(exc, llm_guard.AllModelsExhausted):
        if own_key():
            return ("Your own Groq key has also reached today's free limit on both models. It resets at "
                    "midnight UTC (5:00 am Pakistan time).")
        return ("Today's shared free AI allowance is used up. Add your own free Groq key below to continue.")
    if isinstance(exc, litellm.AuthenticationError):
        return "The Groq API key was rejected. Check GROQ_API_KEY in the app's Secrets."
    if isinstance(exc, litellm.RateLimitError):
        return "The AI service is busy right now. Wait a minute and try again."
    if isinstance(exc, (litellm.APIConnectionError, litellm.Timeout)):
        return "Couldn't reach the AI service. Check your connection and try again."
    return "Something went wrong during the analysis. Try again, or start a new analysis."


# ---------------------------------------------------------------------------
# Live progress
# ---------------------------------------------------------------------------
def run_with_progress(title, initial_rows, work):
    q, holder = queue.Queue(), {}

    def emit(stage, status, detail=""):
        q.put((stage, status, detail))

    def target():
        try:
            holder["result"] = work(emit)
        except Exception as exc:  # noqa: BLE001
            holder["error"] = exc

    rows = {r["key"]: dict(r, status="pending", detail=r.get("detail", "Waiting")) for r in initial_rows}
    order = [r["key"] for r in initial_rows]
    ph = st.empty()
    start = time.time()
    t = threading.Thread(target=target, daemon=True)
    t.start()
    while t.is_alive() or not q.empty():
        while not q.empty():
            stage, status, detail = q.get()
            if stage == "plan":                      # specialists chosen during a one-step run
                pos = order.index("review") if "review" in order else len(order)
                for k in status:
                    if k not in rows:
                        rows[k] = {"key": k, "name": f"{label(k)} Specialist", "status": "pending", "detail": "Waiting"}
                        order.insert(pos, k)
                        pos += 1
                continue
            if stage in rows:
                rows[stage]["status"] = status
                rows[stage]["detail"] = detail
        ph.markdown(ui.progress_html([rows[k] for k in order], title, time.time() - start), unsafe_allow_html=True)
        time.sleep(0.35)
    t.join()
    if "error" in holder:
        raise holder["error"]
    return holder["result"]


def investigation_rows(spec_keys):
    rows = [{"key": "search", "name": "Evidence search · web and academic"},
            {"key": "research", "name": "Research and Evidence Agent"}]
    rows += [{"key": k, "name": f"{label(k)} Specialist"} for k in spec_keys]
    rows.append({"key": "review", "name": "Critical Reviewer"})
    return rows


# ---------------------------------------------------------------------------
# Layout pieces
# ---------------------------------------------------------------------------
def render_header(user):
    if not auth_configured():
        ui.hero()
        return
    left, right = st.columns([5, 1.35], vertical_alignment="center")
    with left:
        ui.hero()
    with right:
        if user:
            st.markdown(f"<div style='text-align:right;font-size:.84rem'><b>{ui.e(user['name'] or user['email'])}</b></div>",
                        unsafe_allow_html=True)
            st.button("Sign out", key="btn_signout", on_click=st.logout, width="stretch")
        else:
            st.button("Sign in with Google", key="btn_signin", icon=":material/login:", on_click=st.login,
                      width="stretch", help="Optional. Signing in saves your analyses to your history.")


def render_sidebar(user, storage):
    with st.sidebar:
        st.markdown("#### How it works")
        steps = TWO_STEPS if st.session_state.mode == "two-step" else ONE_STEPS
        ui.step_guide(steps, step_index())
        st.write("")
        if st.button("New analysis", icon=":material/add:", width="stretch", key="btn_new_side"):
            reset_analysis()
            st.rerun()
        if user and storage.enabled:
            if st.button("My history", icon=":material/history:", width="stretch", key="btn_hist"):
                st.session_state.view = "history"
                st.rerun()
        st.divider()
        st.caption("**Services**")
        st.caption(("✅" if secret("SERPER_API_KEY") else "⚪") + " Web evidence (Serper)")
        st.caption(("✅" if secret("OPENALEX_API_KEY") else "⚪") + " Academic references (OpenAlex)")
        st.caption(("🔑 Your own Groq key" if own_key() else "🔑 Shared Groq key") + " in use")
        st.caption(("✅" if (user and storage.enabled) else "⚪") + " History"
                   + ("" if auth_configured() else " (sign-in not set up)"))
        with st.expander("Use my own Groq key", icon=":material/key:"):
            if render_key_form("side"):
                resume_after_key()
        st.divider()
        st.caption("Industria-AI is a decision-support tool. AI can be wrong, so every result is reviewed by you "
                   "before a report is issued.")


# ---------------------------------------------------------------------------
# Personal Groq key (only needed when the shared allowance is used up)
# ---------------------------------------------------------------------------
KEY_STEPS = ("1. Open <a href='https://console.groq.com/keys' target='_blank'>console.groq.com/keys</a> "
             "and sign in (Google sign-in works). It's free.<br>"
             "2. Click <b>Create API Key</b>, give it any name, and copy the key (it starts with <b>gsk_</b>).<br>"
             "3. Paste it below. It's used only in this browser session and is never saved or shown to anyone.")


def render_key_form(where):
    if own_key():
        st.caption("Your own key is active for this session.")
        if st.button("Remove my key", key=f"btn_rmkey_{where}", icon=":material/delete:"):
            st.session_state.user_groq_key = ""
            log("Personal Groq key removed")
            st.rerun()
        return False
    if where == "side":
        st.caption("Optional. Runs your analyses on your own free Groq limits. Used only in this session.")
    k = st.text_input("Groq API key", type="password", key=f"key_input_{where}", placeholder="gsk_...",
                      label_visibility="collapsed" if where == "side" else "visible")
    if st.button("Use my key" if where == "side" else "Use my key and continue", key=f"btn_key_{where}",
                 type="secondary" if where == "side" else "primary", icon=":material/key:"):
        ok, msg = llm_guard.validate_key(k)
        if not ok:
            ui.banner("err", ui.e(msg))
            return False
        st.session_state.user_groq_key = k.strip()
        st.session_state.need_key = False
        log("Personal Groq key added", "session only")
        if msg:
            st.session_state.key_note = msg
        return True
    return False


def render_key_card():
    with st.container(key="card_key"):
        ui.section("Add your own free Groq key to continue", "key",
                   "The shared free AI allowance for today is used up. It resets at midnight UTC "
                   "(5:00 am Pakistan time). With your own free key you can continue right now.")
        st.markdown(f"<div class='ia-banner ia-b-info'>{ui.icon('help')}<div>{KEY_STEPS}</div></div>",
                    unsafe_allow_html=True)
        if render_key_form("card"):
            resume_after_key()


def resume_after_key():
    """After a personal key is added, continue the run that was interrupted."""
    job = st.session_state.get("retry_job")
    st.session_state.retry_job = None
    if job:
        if job == "revise":
            st.session_state.revision_used = True
        st.session_state.update(job=job, stage="analyzing", error=None)
    st.rerun()


# ---------------------------------------------------------------------------
# Stage: describe
# ---------------------------------------------------------------------------
def restore_inputs():
    """After a failed run, put the user's inputs back into the form."""
    inp = st.session_state.inputs
    st.session_state.restore_inputs = False
    if not inp:
        return
    if inp["industry"] in industry_options():
        st.session_state.in_industry = inp["industry"]
    else:
        st.session_state.in_industry = OTHER
        st.session_state.in_industry_other = inp["industry"]
    st.session_state.in_problem = inp["problem"]
    st.session_state.mode_choice = inp["mode"]
    for field, widget in (("objectives", "in_objectives"), ("constraints", "in_constraints"),
                          ("available_data", "in_available"), ("desired_outcome", "in_outcome")):
        if inp["details"].get(field):
            st.session_state[widget] = inp["details"][field]
    st.session_state.keep_data = bool(st.session_state.data_profile)


def render_input():
    if st.session_state.restore_inputs:
        restore_inputs()
    with st.container(key="card_input"):
        ui.section("Describe your problem", "edit_note")
        industry = st.selectbox("Industry", industry_options(), index=None, placeholder="Select your industry",
                                key="in_industry")
        if industry == OTHER:
            st.text_input("Your industry", key="in_industry_other", placeholder="Furniture manufacturing")
        st.text_area(
            "Problem statement", key="in_problem", height=150,
            placeholder=example_for(industry if industry and industry != OTHER else None),
            help="Say what is going wrong, how much it changed, since when, and what you already checked.")
        st.caption("Tip: numbers and recent changes (new supplier, new setting, new season) help the specialists most.")
        csv = st.file_uploader("Process data (optional CSV, up to 5 MB)", type=["csv"], key="in_csv",
                               help="Readings, defect counts or logs. Statistics are computed by code, not guessed.")
        if csv is not None:
            st.session_state.keep_data = False
            try:
                df = load_csv(csv.getvalue())
                prof = profile(df)
                st.session_state.data_profile = prof
                st.session_state.trend_png = trend_chart(df)
                st.caption(f"Loaded {prof['rows']} rows and {prof['columns']} columns. "
                           "A Data and Statistics specialist will join the analysis.")
            except DataError as exc:
                st.session_state.data_profile, st.session_state.trend_png = None, None
                ui.banner("err", ui.e(str(exc)))
        elif st.session_state.keep_data and st.session_state.data_profile:
            st.caption("Using the data file you uploaded earlier. Upload again to replace it.")
        else:
            st.session_state.data_profile, st.session_state.trend_png = None, None

        st.write("")
        mode = st.radio("How do you want to verify the analysis?", ["two-step", "one-step"],
                        format_func=lambda m: MODE_LABELS[m], captions=MODE_CAPTIONS, key="mode_choice")
        st.session_state.mode = mode

        details = {}
        if mode == "one-step":
            ui.banner("info", "Add what you know. Skipping these? I'll assume reasonable defaults and list them "
                              "in your report as AI assumptions.", "tips_and_updates")
            c1, c2 = st.columns(2)
            details["objectives"] = c1.text_area("Objectives", key="in_objectives", height=90,
                                                 placeholder="Bring breakage back below 4 per hour")
            details["constraints"] = c2.text_area("Constraints", key="in_constraints", height=90,
                                                  placeholder="No production stoppage; budget under PKR 500,000")
            details["available_data"] = c1.text_area("Available data", key="in_available", height=90,
                                                     placeholder="Shift breakage logs, HVI test reports")
            details["desired_outcome"] = c2.text_area("Desired outcome", key="in_outcome", height=90,
                                                      placeholder="A ranked list of causes and a first action")

        st.write("")
        clicked = st.button("Analyze problem", type="primary", icon=":material/play_arrow:",
                            width="stretch", key="btn_analyze")
    ui.note("Your inputs are processed by third-party AI and search services (Groq, Serper, OpenAlex). "
            "Avoid confidential or personal data.")

    if clicked:
        problem = (st.session_state.get("in_problem") or "").strip()
        ind = industry if industry != OTHER else (st.session_state.get("in_industry_other") or "").strip()
        if not industry:
            ui.banner("err", "Select your industry first.")
            return
        if not ind:
            ui.banner("err", "Type the name of your industry.")
            return
        if len(problem) < 25:
            ui.banner("err", "Describe the problem in a little more detail (at least one full sentence).")
            return
        st.session_state.inputs = {"industry": ind, "problem": problem, "mode": mode,
                                   "details": {k: v.strip() for k, v in details.items() if (v or "").strip()}}
        log("Problem submitted", f"{ind} · {mode} · {problem[:90]}")
        if st.session_state.data_profile:
            log("Process data attached", f"{st.session_state.data_profile['rows']} rows")
        st.session_state.job = "intake" if mode == "two-step" else "one_step"
        if not own_key() and llm_guard.all_exhausted(owner_key()):
            st.session_state.need_key = True
            st.session_state.retry_job = st.session_state.job
            st.session_state.job = None
            st.rerun()
        st.session_state.stage = "analyzing"
        st.session_state.error = None
        st.rerun()


# ---------------------------------------------------------------------------
# Stage: analyzing (runs the queued job with live progress)
# ---------------------------------------------------------------------------
def keys():
    return {"serper": secret("SERPER_API_KEY") or "", "openalex": secret("OPENALEX_API_KEY") or ""}


def merge_one_step(intake, details):
    confirmed, assumed = dict(intake), []
    for f, _ in DETAIL_FIELDS:
        given = details.get(f)
        if given:
            confirmed[f] = given if f == "desired_outcome" else lines(given)
        elif intake.get(f):
            assumed.append(f)
    return confirmed, assumed


def run_job():
    key = active_key()
    heavy, light = llms_for(key)
    inp = st.session_state.inputs
    data_summary = (st.session_state.data_profile or {}).get("summary", "")
    job = st.session_state.job
    switch_start = llm_guard.switch_event_count()
    ui.section("Analysis in progress", "neurology",
               "Specialists are working. This usually takes 1 to 3 minutes on the free plan.")
    try:
        if job == "intake":
            intake = run_with_progress(
                "Understanding your problem", [{"key": "intake", "name": "Intake and Routing Agent"}],
                lambda emit: run_intake(inp["industry"], inp["problem"], inp["details"], data_summary, light, emit))
            st.session_state.intake = intake
            log("Problem interpreted", f"specialists: {', '.join(label(k) for k in intake['selected_specialists'])}")
            st.session_state.stage = "quick_check"

        elif job == "one_step":
            def work(emit):
                intake = run_intake(inp["industry"], inp["problem"], inp["details"], data_summary, light, emit)
                confirmed, assumed = merge_one_step(intake, inp["details"])
                emit("plan", confirmed["selected_specialists"])
                inv = run_investigation(context_text(confirmed, inp), confirmed["selected_specialists"], heavy, light,
                                        keys(), confirmed["search_queries"], data_summary, emit=emit)
                return intake, confirmed, assumed, inv
            rows = [{"key": "intake", "name": "Intake and Routing Agent"}] + investigation_rows([])
            intake, confirmed, assumed, inv = run_with_progress("Analyzing your problem", rows, work)
            st.session_state.update(intake=intake, confirmed=confirmed, ai_assumed=assumed, investigation=inv)
            log("Analysis complete", f"{len(inv['agents_involved'])} agents, {len(inv['tool_usage'])} tool calls")
            st.session_state.stage = "review"

        elif job in ("investigate", "revise"):
            c = st.session_state.confirmed
            feedback = st.session_state.feedback_history[-1]["text"] if job == "revise" else None
            cached = st.session_state.investigation.get("search_cache") if job == "revise" else None
            inv = run_with_progress(
                "Re-analyzing with your feedback" if feedback else "Investigating your problem",
                investigation_rows(c["selected_specialists"]),
                lambda emit: run_investigation(context_text(c, inp), c["selected_specialists"], heavy, light, keys(),
                                               c["search_queries"], data_summary, feedback=feedback, cached=cached,
                                               emit=emit))
            st.session_state.investigation = inv
            log("Revised analysis complete" if feedback else "Analysis complete",
                f"{len(inv['agents_involved'])} agents, {len(inv['tool_usage'])} tool calls")
            st.session_state.stage = "review"
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, llm_guard.AllModelsExhausted) and not own_key():
            st.session_state.need_key = True          # ask for a personal key, then resume
            st.session_state.retry_job = job
        else:
            st.session_state.error = (friendly_error(exc), f"{type(exc).__name__}: {str(exc)[:300]}")
        st.session_state.stage = {"intake": "input", "one_step": "input"}.get(job, "quick_check" if job == "investigate" else "review")
        st.session_state.restore_inputs = st.session_state.stage == "input"
        if job == "revise":
            st.session_state.revision_used = False
        log("Analysis failed", type(exc).__name__)
    events = llm_guard.switch_events_since(switch_start)
    if events:
        pairs = sorted({f"{e['from']} → {e['to']}" for e in events})
        st.session_state.models_note = (f"Daily free limit reached ({', '.join(pairs)}); part of this analysis "
                                        "used the backup model. Quality may be slightly lower.")
        log("Model fallback", ", ".join(pairs))
    st.session_state.job = None
    st.rerun()


# ---------------------------------------------------------------------------
# Stage: quick check (two-step only)
# ---------------------------------------------------------------------------
def render_quick_check():
    it = st.session_state.intake
    with st.container(key="card_quick"):
        ui.section("Quick check: did I understand you?", "fact_check",
                   "Catching a misunderstanding now saves a full analysis run. Correct anything that's wrong, "
                   "then continue.")
        if it.get("high_risk"):
            ui.banner("warn", "<b>Safety-relevant problem.</b> " + ui.e(it.get("risk_note") or "")
                      + " Every action must be verified by a qualified engineer.")
        st.text_area("My understanding of your problem", value=it["problem_summary"], key="qc_summary", height=110)
        st.multiselect("Specialists I will consult", options=list(SPECIALIST_POOL), default=it["selected_specialists"],
                       format_func=label, max_selections=MAX_SPECIALISTS, key="qc_specs",
                       help="Up to 4. Fewer specialists means a faster run.")
        if it.get("routing_rationale"):
            st.caption("Why these: " + it["routing_rationale"])
        if it.get("missing_information"):
            ui.banner("info", "<b>Worth adding if you know it:</b> " + ui.e("; ".join(it["missing_information"]))
                      + ". Add it to the text above.", "help")
        with st.expander("Edit details · system suggestions", icon=":material/tune:"):
            st.caption("These are the system's suggestions, not facts. Change anything that's wrong, "
                       "one item per line.")
            c1, c2 = st.columns(2)
            c1.text_area("Objectives", value="\n".join(it["objectives"]), key="qc_objectives", height=110)
            c2.text_area("Constraints", value="\n".join(it["constraints"]), key="qc_constraints", height=110)
            c1.text_area("Available data", value="\n".join(it["available_data"]), key="qc_available", height=110)
            c2.text_area("Desired outcome", value=it["desired_outcome"], key="qc_outcome", height=110)
            st.text_area("Assumptions", value="\n".join(it["assumptions"]), key="qc_assumptions", height=90)
        b1, b2 = st.columns([3, 1])
        go = b1.button("Yes, continue", type="primary", icon=":material/arrow_forward:", width="stretch",
                       key="btn_continue")
        stop = b2.button("Stop", icon=":material/close:", width="stretch", key="btn_stop")

    if stop:
        log("Stopped at quick check")
        st.session_state.stage = "stopped"
        st.rerun()
    if go:
        specs = clean_selection(st.session_state.get("qc_specs") or [], has_data=bool(st.session_state.data_profile))
        ss = st.session_state
        confirmed = dict(it)
        confirmed.update(
            problem_summary=(ss.get("qc_summary") or it["problem_summary"]).strip(),
            selected_specialists=specs,
            objectives=lines(ss.get("qc_objectives", "\n".join(it["objectives"]))),
            constraints=lines(ss.get("qc_constraints", "\n".join(it["constraints"]))),
            available_data=lines(ss.get("qc_available", "\n".join(it["available_data"]))),
            desired_outcome=(ss.get("qc_outcome", it["desired_outcome"]) or "").strip(),
            assumptions=lines(ss.get("qc_assumptions", "\n".join(it["assumptions"]))),
        )
        edited = [k for k in ("problem_summary", "selected_specialists", "objectives", "constraints",
                              "available_data", "desired_outcome", "assumptions") if confirmed[k] != it[k]]
        log("Quick check confirmed", ("edited: " + ", ".join(edited)) if edited else "no changes")
        st.session_state.update(confirmed=confirmed, ai_assumed=[], job="investigate", stage="analyzing")
        st.rerun()


# ---------------------------------------------------------------------------
# Report body (shared by final review and final report)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def diagram_pngs(causes_key, causes, title):
    return fishbone(causes, title), likelihood_chart(causes)


def render_report_body(inv, confirmed):
    rv = inv["review"]
    if st.session_state.models_note:
        ui.banner("warn", ui.e(st.session_state.models_note), "swap_horiz")
    if confirmed.get("high_risk"):
        ui.banner("warn", "<b>Safety-relevant problem.</b> " + ui.e(confirmed.get("risk_note") or "")
                  + " Have a qualified engineer verify every action.")
    if not inv.get("evidence"):
        ui.banner("warn", "No external evidence was available, so findings are agent inference and need verification.")
    if st.session_state.ai_assumed:
        ui.banner("info", "<b>AI assumptions (not checked before analysis):</b> "
                  + ui.e(", ".join(dict(DETAIL_FIELDS)[f] for f in st.session_state.ai_assumed))
                  + ". They are marked in the report.", "info")
    ui.summary_box(rv.get("executive_summary") or "No summary was produced.", rv.get("verdict", ""))

    causes = rv.get("ranked_causes", [])
    ui.section("Ranked root causes and actions", "format_list_numbered")
    ui.ranked_table(causes)

    if causes:
        ui.section("Cause map and likelihood", "account_tree")
        key = "|".join(f"{c['cause']}{c['category']}{c['likelihood_pct']}" for c in causes)
        fish, bars = diagram_pngs(key, causes, confirmed.get("short_title", "Problem"))
        st.image(fish, width="stretch")
        c1, _ = st.columns([4, 1])
        c1.image(bars, width="stretch")

    ui.section("Critical review", "gavel")
    c1, c2 = st.columns(2)
    with c1:
        ui.list_card("Critical findings", rv.get("critical_findings"), "report")
        st.write("")
        ui.list_card("Uncertainties", rv.get("uncertainties"), "help")
    with c2:
        ui.list_card("Alternative explanations", rv.get("alternative_explanations"), "alt_route")
        st.write("")
        ui.list_card("Risks of the proposed actions", rv.get("risks"), "warning")

    ui.section("Evidence and references", "menu_book")
    if inv.get("evidence"):
        for ev in inv["evidence"]:
            kind = {"academic": "🎓 Academic", "web": "🌐 Web"}.get(ev.get("source_type"), "⚠️ Unverified")
            cite = f" **[{ev['citation']}]**" if ev.get("citation") else ""
            src = f"[{ev.get('source_title') or 'source'}]({ev['source_url']})" if ev.get("source_url") else (ev.get("source_title") or "")
            st.markdown(f"- {ev['finding']}{cite} · {kind} · {src}")
    else:
        st.caption("No external evidence was available for this analysis.")
    if inv.get("references"):
        st.markdown("**References**")
        for r in inv["references"]:
            st.markdown(f"[{r['number']}] {r['text']} [{r['url']}]({r['url']})")
    if inv.get("related_literature"):
        with st.expander(f"Related papers found but not cited ({len(inv['related_literature'])})"):
            for r in inv["related_literature"]:
                st.markdown(f"- {r['text']} [{r['url']}]({r['url']})")

    if st.session_state.data_profile:
        with st.expander("Process data", icon=":material/monitoring:"):
            if st.session_state.trend_png:
                st.image(st.session_state.trend_png, width="stretch")
            st.caption(st.session_state.data_profile["summary"])

    with st.expander("Full analysis · specialists, tools and audit trail", icon=":material/description:"):
        st.markdown(f"**Interpretation:** {confirmed['problem_summary']}")
        ui.pills([label(k) for k in confirmed["selected_specialists"]])
        for s in inv["specialist_results"]:
            st.markdown(f"##### {s['specialist']} specialist · confidence: {s.get('confidence', 'n/a')}")
            if s.get("root_causes"):
                for c in s["root_causes"]:
                    st.markdown(f"- **{c['cause']}** ({c['category']}, {c['likelihood']}, {c['basis']}). "
                                f"{c.get('reasoning', '')} *Action:* {c.get('action', '')}. "
                                f"*Risk:* {c.get('action_risk', '')}.")
            else:
                st.caption("This specialist's answer could not be read in a structured way.")
                if s.get("raw_text"):
                    st.code(s["raw_text"][:1500], language=None)
        st.markdown("##### Tools used by the agents")
        if inv.get("tool_usage"):
            st.dataframe([{"Time": t["time"], "Agent": t["agent"], "Tool": t["tool"], "Input": t["input"],
                           "Result": f"{t['status']}: {t['detail']}"} for t in inv["tool_usage"]],
                         width="stretch", hide_index=True)
        else:
            st.caption("No tools were called in this run.")
        st.markdown("##### Audit trail")
        for a in st.session_state.audit:
            st.markdown(f"`{a['time']}` **{a['event']}** {a['detail']}")


# ---------------------------------------------------------------------------
# Stage: final review
# ---------------------------------------------------------------------------
def finalize(decision, user, storage):
    inp, c, inv = st.session_state.inputs, st.session_state.confirmed, st.session_state.investigation
    who = f"{user['name']} ({user['email']})" if user else "Guest user"
    report = build_report(industry=inp["industry"], problem_statement=inp["problem"], mode=inp["mode"],
                          interpretation=c, investigation=inv, decision=decision, verified_by=who,
                          feedback_history=st.session_state.feedback_history,
                          data_profile=st.session_state.data_profile, ai_assumed_fields=st.session_state.ai_assumed,
                          models_note=st.session_state.models_note, audit=st.session_state.audit)
    st.session_state.report = report
    if user and storage.enabled:
        ok, msg = storage.save_analysis(user_email=user["email"], report=report, problem_label=c.get("short_title", ""))
        st.session_state.saved_msg = "Saved to your history." if ok else f"Couldn't save to history: {msg}"
    return report


def render_review(user, storage):
    ui.section("Final review: your decision", "rule",
               "Check the findings, then accept, ask for one revision, or reject. Nothing is final until you decide.")
    render_report_body(st.session_state.investigation, st.session_state.confirmed)

    st.write("")
    with st.container(key="card_decision"):
        st.markdown("**Your decision**")
        c1, c2, c3 = st.columns(3)
        accept = c1.button("Accept", icon=":material/check_circle:", width="stretch", key="btn_accept")
        modify = c2.button("Modify", icon=":material/edit:", width="stretch", key="btn_modify",
                           disabled=st.session_state.revision_used)
        reject = c3.button("Reject", icon=":material/cancel:", width="stretch", key="btn_reject")
        if st.session_state.revision_used:
            st.caption("You've used the one revision for this problem. Accept, reject, or start a new analysis.")
        if modify:
            st.session_state.show_modify = True
        if st.session_state.show_modify and not st.session_state.revision_used:
            fb = st.text_area("What should the specialists reconsider?", key="mod_text",
                              placeholder="Consider whether temperature variation in the hall could be responsible.")
            if st.button("Re-run with my feedback", type="primary", icon=":material/refresh:", key="btn_rerun"):
                if len((fb or "").strip()) < 8:
                    ui.banner("err", "Write your feedback first.")
                else:
                    st.session_state.feedback_history.append({"time": datetime.now().strftime("%H:%M:%S"),
                                                              "text": fb.strip()})
                    log("Revision requested", fb.strip()[:90])
                    st.session_state.update(revision_used=True, show_modify=False, job="revise", stage="analyzing")
                    st.rerun()
    if accept:
        log("Accepted by human reviewer")
        report = finalize("ACCEPTED", user, storage)
        st.session_state.pdf_bytes = build_pdf(report, st.session_state.confirmed.get("short_title", "Problem"))
        st.session_state.stage = "final"
        st.rerun()
    if reject:
        log("Rejected by human reviewer")
        finalize("REJECTED", user, storage)
        st.session_state.stage = "stopped"
        st.rerun()


# ---------------------------------------------------------------------------
# Stage: final report / stopped, with feedback
# ---------------------------------------------------------------------------
def render_feedback(user, storage):
    ui.section("Help improve Industria-AI", "rate_review", "Twenty seconds. Your answers go straight to the developer.")
    if st.session_state.fb_sent:
        ui.banner("ok", "Thanks, your feedback was recorded.")
        return
    mode = (st.session_state.inputs or {}).get("mode", "two-step")
    with st.form("fb_form", border=True):
        st.markdown("**Overall, how useful was this analysis?**")
        stars = st.feedback("stars", key="fb_stars")
        plausible = st.radio("Was the most likely root cause plausible?", ["Yes", "Partly", "No"], index=None,
                             horizontal=True, key="fb_plausible")
        mode_right = st.radio(f"Was the {mode} check right for this problem?", ["Yes", "No", "Not sure"], index=None,
                              horizontal=True, key="fb_mode")
        qc_clear = None
        if mode == "two-step" and st.session_state.intake is not None:
            qc_clear = st.radio("Was the quick check clear?", ["Yes", "Somewhat", "No"], index=None, horizontal=True,
                                key="fb_qc")
        comment = st.text_area("Anything else? (optional)", key="fb_comment",
                               placeholder="What was missing, wrong, or confusing?")
        sent = st.form_submit_button("Send feedback", type="primary", icon=":material/send:")
    if sent:
        if stars is None and not plausible and not comment:
            ui.banner("err", "Give a star rating or answer at least one question first.")
            return
        report = st.session_state.report or {}
        row = {"user_email": (user or {}).get("email", ""), "report_id": report.get("report_id"),
               "industry": (st.session_state.inputs or {}).get("industry"), "mode": mode,
               "decision": report.get("decision") or ("STOPPED" if st.session_state.stage == "stopped" else ""),
               "rating": (stars + 1) if stars is not None else None, "root_cause_plausible": plausible,
               "mode_right": mode_right, "quick_check_clear": qc_clear, "comment": (comment or "").strip()}
        ok = False
        if storage.enabled:
            ok, _ = storage.save_feedback(row)
        if not ok:
            st.session_state.local_feedback.append(row)
        st.session_state.fb_sent = True
        log("Feedback sent", "stored" if ok else "kept for this session only")
        st.rerun()


def render_final(user, storage):
    report = st.session_state.report
    ui.banner("ok", f"<b>Report verified.</b> Accepted by {ui.e(report['verified_by'])} · Report {report['report_id']}",
              "verified")
    if st.session_state.saved_msg:
        st.caption(st.session_state.saved_msg)
    c1, c2, c3 = st.columns([1.4, 1, 1])
    c1.download_button("Download PDF report", data=st.session_state.pdf_bytes,
                       file_name=f"industria-ai-report-{report['report_id']}.pdf", mime="application/pdf",
                       type="primary", icon=":material/picture_as_pdf:", width="stretch")
    c2.download_button("Full analysis (Markdown)", data=report_to_markdown(report),
                       file_name=f"industria-ai-full-{report['report_id']}.md", mime="text/markdown",
                       icon=":material/description:", width="stretch")
    if c3.button("New analysis", icon=":material/add:", width="stretch", key="btn_new_final"):
        reset_analysis()
        st.rerun()
    render_report_body(st.session_state.investigation, st.session_state.confirmed)
    render_feedback(user, storage)


def render_stopped(user, storage):
    decision = (st.session_state.report or {}).get("decision")
    msg = ("You rejected the proposed analysis, so no report was issued." if decision == "REJECTED"
           else "You stopped the analysis at the quick check, so no further analysis was run.")
    ui.banner("info", f"<b>Analysis stopped.</b> {msg} A rejection is never treated as an acceptance.", "block")
    if st.session_state.saved_msg:
        st.caption(st.session_state.saved_msg)
    if st.button("Start a new analysis", type="primary", icon=":material/add:", key="btn_new_stop"):
        reset_analysis()
        st.rerun()
    render_feedback(user, storage)


# ---------------------------------------------------------------------------
# History view
# ---------------------------------------------------------------------------
def render_history(user, storage):
    ui.section("My history", "history", "Your past analyses and decisions.")
    if st.button("Back to analysis", icon=":material/arrow_back:", key="btn_back"):
        st.session_state.view = "app"
        st.rerun()
    items, err = storage.list_analyses(user["email"])
    if err:
        ui.banner("err", ui.e(err))
    if not items:
        st.caption("No saved analyses yet. Accepted or rejected analyses appear here when you're signed in.")
    for it in items:
        decision = it.get("decision") or ""
        color = "ok" if decision == "ACCEPTED" else "err"
        st.markdown(
            f"<div class='ia-hist'><div class='top'><span>{ui.e(str(it.get('created_at', ''))[:16].replace('T', ' '))} UTC · "
            f"{ui.e(it.get('industry'))} · {ui.e(it.get('mode'))}</span><span class='ia-banner ia-b-{color}' "
            f"style='padding:1px 8px;margin:0;font-size:.74rem'>{ui.e(decision)}</span></div>"
            f"<div class='ttl'>{ui.e(it.get('problem_label') or 'Analysis')}</div>"
            f"<div class='sum'>{ui.e(it.get('summary'))}</div></div>", unsafe_allow_html=True)
        if decision == "ACCEPTED" and isinstance(it.get("report"), dict):
            k = f"pdf_{it.get('id')}"
            if st.session_state.get(k):
                st.download_button("Download PDF", data=st.session_state[k], mime="application/pdf",
                                   file_name=f"industria-ai-report-{it.get('report_id')}.pdf", key=f"dl_{it.get('id')}",
                                   icon=":material/download:")
            elif st.button("Prepare PDF", key=f"prep_{it.get('id')}", icon=":material/picture_as_pdf:"):
                st.session_state[k] = build_pdf(it["report"], it.get("problem_label") or "Problem")
                st.rerun()
        st.write("")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    init_state()
    user = current_user()
    storage = get_storage(secret("SUPABASE_URL") or "", secret("SUPABASE_KEY") or "")
    render_header(user)
    st.write("")
    render_sidebar(user, storage)

    if not secret("GROQ_API_KEY"):
        ui.banner("err", "<b>GROQ_API_KEY is missing.</b> Add it in the app's Settings → Secrets, then reload.")
        st.stop()

    if st.session_state.get("key_note"):
        ui.banner("info", ui.e(st.session_state.pop("key_note")), "key")
    if not own_key() and llm_guard.all_exhausted(owner_key()) and st.session_state.stage in ("input", "quick_check", "review"):
        st.session_state.need_key = True
    if st.session_state.get("need_key") and not own_key():
        render_key_card()
        st.write("")
    exhausted = llm_guard.fallback_status(active_key())
    if exhausted and len(exhausted) < 2 and st.session_state.stage != "analyzing":
        ui.banner("warn", f"Today's free limit is reached on {', '.join(exhausted)}. Analyses now use the backup model, "
                          "so quality may be slightly lower. Limits reset at midnight UTC (5:00 am Pakistan time).",
                  "swap_horiz")

    if st.session_state.view == "history" and user and storage.enabled:
        render_history(user, storage)
        return

    if st.session_state.error:
        msg, detail = st.session_state.error
        ui.banner("err", ui.e(msg))
        with st.expander("Technical details"):
            st.code(detail, language=None)
        st.session_state.error = None

    stage = st.session_state.stage
    if stage == "input":
        render_input()
    elif stage == "analyzing":
        run_job()
    elif stage == "quick_check":
        render_quick_check()
    elif stage == "review":
        render_review(user, storage)
    elif stage == "final":
        render_final(user, storage)
    elif stage == "stopped":
        render_stopped(user, storage)


main()
