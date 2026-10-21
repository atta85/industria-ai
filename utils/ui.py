"""
Look and feel: the "Industrial Slate" palette (light and dark), custom CSS,
and small HTML components. Every custom block sets both its own background
and text color, so it stays readable whichever theme the user picks.
"""

from html import escape

import streamlit as st

PALETTES = {
    "light": {
        "bg": "#F8FAFC", "card": "#FFFFFF", "border": "#E2E8F0", "text": "#0F172A", "muted": "#475569",
        "navy": "#1E293B", "navy_text": "#FFFFFF", "navy_sub": "#CBD5E1",
        "primary": "#4F46E5", "primary_hover": "#4338CA", "primary_soft": "#EEF2FF", "primary_text": "#3730A3",
        "green": "#047857", "green_hover": "#065F46", "green_soft": "#D1FAE5", "green_text": "#065F46",
        "amber": "#B45309", "amber_soft": "#FEF3C7", "amber_text": "#92400E",
        "red": "#B91C1C", "red_soft": "#FEE2E2", "red_text": "#991B1B",
        "teal_soft": "#CCFBF1", "teal_text": "#115E59", "sky_soft": "#E0F2FE", "sky_text": "#075985",
        "row_alt": "#F8FAFC", "shadow": "0 1px 2px rgba(15,23,42,.06), 0 4px 14px rgba(15,23,42,.05)",
    },
    "dark": {
        "bg": "#0B1220", "card": "#111827", "border": "#273449", "text": "#E5E7EB", "muted": "#94A3B8",
        "navy": "#1E293B", "navy_text": "#FFFFFF", "navy_sub": "#CBD5E1",
        "primary": "#6366F1", "primary_hover": "#818CF8", "primary_soft": "#1E1B4B", "primary_text": "#C7D2FE",
        "green": "#059669", "green_hover": "#10B981", "green_soft": "#064E3B", "green_text": "#A7F3D0",
        "amber": "#F59E0B", "amber_soft": "#451A03", "amber_text": "#FDE68A",
        "red": "#EF4444", "red_soft": "#450A0A", "red_text": "#FECACA",
        "teal_soft": "#134E4A", "teal_text": "#99F6E4", "sky_soft": "#0C4A6E", "sky_text": "#BAE6FD",
        "row_alt": "#0F172A", "shadow": "0 1px 2px rgba(0,0,0,.4), 0 4px 14px rgba(0,0,0,.3)",
    },
}


def theme_type() -> str:
    try:
        return "dark" if st.context.theme.type == "dark" else "light"
    except Exception:  # noqa: BLE001
        return "light"


def palette():
    return PALETTES[theme_type()]


def inject_css():
    p = palette()
    css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..24,400,0,0&display=block');
:root {{ {' '.join(f'--ia-{k.replace("_", "-")}: {v};' for k, v in p.items())} }}
.msr {{ font-family: 'Material Symbols Rounded'; font-weight: normal; font-style: normal; font-size: 20px;
        line-height: 1; display: inline-block; vertical-align: middle; -webkit-font-smoothing: antialiased; }}
.block-container {{ padding-top: 1.6rem; max-width: 1180px; }}
h1, h2, h3 {{ letter-spacing: -0.01em; }}

/* Cards: bordered containers with a key */
div[class*="st-key-card"] {{ background: var(--ia-card); border: 1px solid var(--ia-border) !important;
    border-radius: 14px; box-shadow: var(--ia-shadow); padding: 1.1rem 1.25rem 1.2rem; }}

/* Buttons */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
    border-radius: 10px; font-weight: 600; padding: 0.55rem 1.1rem; min-height: 2.75rem;
    transition: transform .08s ease, box-shadow .15s ease, background-color .15s ease; }}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {{
    transform: translateY(-1px); box-shadow: 0 6px 16px rgba(79,70,229,.18); }}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
    background: var(--ia-primary); border: 1px solid var(--ia-primary); color: #FFFFFF; }}
.stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {{
    background: var(--ia-primary-hover); border-color: var(--ia-primary-hover); }}
.stButton > button[kind="secondary"], .stDownloadButton > button[kind="secondary"] {{
    background: var(--ia-card); border: 1.5px solid var(--ia-border); color: var(--ia-text); }}
.stButton > button[kind="secondary"]:hover {{ border-color: var(--ia-primary); color: var(--ia-primary); }}
.st-key-btn_accept button {{ background: var(--ia-green) !important; border-color: var(--ia-green) !important; color: #FFFFFF !important; min-height: 3.1rem; font-size: 1rem; }}
.st-key-btn_accept button:hover {{ background: var(--ia-green-hover) !important; box-shadow: 0 6px 16px rgba(4,120,87,.25); }}
.st-key-btn_modify button {{ background: var(--ia-card) !important; border: 1.8px solid var(--ia-amber) !important; color: var(--ia-amber) !important; min-height: 3.1rem; font-size: 1rem; }}
.st-key-btn_modify button:hover {{ background: var(--ia-amber-soft) !important; }}
.st-key-btn_reject button, .st-key-btn_stop button {{ background: var(--ia-card) !important; border: 1.8px solid var(--ia-red) !important; color: var(--ia-red) !important; }}
.st-key-btn_reject button {{ min-height: 3.1rem; font-size: 1rem; }}
.st-key-btn_reject button:hover, .st-key-btn_stop button:hover {{ background: var(--ia-red-soft) !important; }}

/* Mode choice cards */
.st-key-mode_choice div[role="radiogroup"] {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 12px; width: 100%; }}
.st-key-mode_choice div[role="radiogroup"] > div {{ background: var(--ia-card); border: 1.5px solid var(--ia-border);
    border-radius: 12px; padding: 12px 14px 10px; margin: 0; transition: border-color .15s ease, background .15s ease; }}
.st-key-mode_choice div[role="radiogroup"] > div:hover {{ border-color: var(--ia-primary); }}
.st-key-mode_choice div[role="radiogroup"] > div[data-selected="true"] {{ border-color: var(--ia-primary);
    background: var(--ia-primary-soft); box-shadow: 0 0 0 1px var(--ia-primary) inset; }}
.st-key-mode_choice div[role="radiogroup"] > div p {{ color: var(--ia-text); }}
.st-key-mode_choice div[role="radiogroup"] > div label p {{ font-weight: 600; }}
.st-key-mode_choice .stRadio {{ width: 100%; }}

/* Inputs */
.stTextArea textarea, .stTextInput input {{ border-radius: 10px; }}
[data-testid="stFileUploaderDropzone"] {{ border-radius: 12px; }}

/* Sidebar */
section[data-testid="stSidebar"] .block-container {{ padding-top: 1.2rem; }}

/* Components */
.ia-hero {{ background: var(--ia-navy); border-radius: 16px; padding: 18px 22px; display: flex; gap: 14px; align-items: center; }}
.ia-hero .logo {{ width: 46px; height: 46px; border-radius: 12px; background: var(--ia-primary); display: flex;
    align-items: center; justify-content: center; color: #FFFFFF; flex-shrink: 0; }}
.ia-hero .logo .msr {{ font-size: 28px; }}
.ia-hero h1 {{ color: var(--ia-navy-text); font-size: 1.5rem; margin: 0; padding: 0; font-weight: 700; }}
.ia-hero p {{ color: var(--ia-navy-sub); margin: 2px 0 0; font-size: 0.92rem; }}
.ia-steps {{ display: flex; flex-direction: column; gap: 6px; }}
.ia-step {{ display: flex; gap: 10px; align-items: flex-start; background: var(--ia-card); border: 1px solid var(--ia-border);
    border-radius: 10px; padding: 9px 10px; }}
.ia-step .num {{ width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700; flex-shrink: 0; background: var(--ia-primary-soft); color: var(--ia-primary-text); }}
.ia-step .t {{ color: var(--ia-text); font-weight: 600; font-size: 0.86rem; line-height: 1.25; }}
.ia-step .d {{ color: var(--ia-muted); font-size: 0.76rem; line-height: 1.3; margin-top: 2px; }}
.ia-step.active {{ border-color: var(--ia-primary); background: var(--ia-primary-soft); }}
.ia-step.active .num {{ background: var(--ia-primary); color: #FFFFFF; }}
.ia-step.active .t {{ color: var(--ia-primary-text); }}
.ia-step.done .num {{ background: var(--ia-green); color: #FFFFFF; }}
.ia-banner {{ border-radius: 12px; padding: 11px 14px; display: flex; gap: 10px; align-items: flex-start; margin: 4px 0 10px;
    font-size: 0.9rem; line-height: 1.45; }}
.ia-banner .msr {{ font-size: 20px; margin-top: 1px; }}
.ia-b-info {{ background: var(--ia-primary-soft); color: var(--ia-primary-text); border: 1px solid var(--ia-primary); }}
.ia-b-warn {{ background: var(--ia-amber-soft); color: var(--ia-amber-text); border: 1px solid var(--ia-amber); }}
.ia-b-ok {{ background: var(--ia-green-soft); color: var(--ia-green-text); border: 1px solid var(--ia-green); }}
.ia-b-err {{ background: var(--ia-red-soft); color: var(--ia-red-text); border: 1px solid var(--ia-red); }}
.ia-note {{ background: var(--ia-card); color: var(--ia-muted); border: 1px dashed var(--ia-border); border-radius: 10px;
    padding: 8px 12px; font-size: 0.82rem; display: flex; gap: 8px; align-items: center; margin-top: 8px; }}
.ia-summary {{ background: var(--ia-primary-soft); color: var(--ia-text); border-left: 4px solid var(--ia-primary);
    padding: 12px 16px; border-radius: 0; font-size: 0.98rem; line-height: 1.55; }}
.ia-summary .verdict {{ color: var(--ia-primary-text); font-size: 0.82rem; font-weight: 600; margin-top: 6px; }}
.ia-table {{ width: 100%; border-collapse: separate; border-spacing: 0; font-size: 0.86rem; background: var(--ia-card);
    border: 1px solid var(--ia-border); border-radius: 12px; overflow: hidden; }}
.ia-table th {{ background: var(--ia-navy); color: #FFFFFF; text-align: left; padding: 9px 10px; font-weight: 600; font-size: 0.8rem; }}
.ia-table td {{ color: var(--ia-text); padding: 9px 10px; vertical-align: top; border-top: 1px solid var(--ia-border); line-height: 1.45; }}
.ia-table tr:nth-child(even) td {{ background: var(--ia-row-alt); }}
.ia-table .sub {{ color: var(--ia-muted); font-size: 0.76rem; }}
.ia-chip {{ display: inline-block; border-radius: 8px; padding: 3px 9px; font-size: 0.78rem; font-weight: 700; white-space: nowrap; }}
.ia-chip-High {{ background: var(--ia-red-soft); color: var(--ia-red-text); }}
.ia-chip-Medium {{ background: var(--ia-amber-soft); color: var(--ia-amber-text); }}
.ia-chip-Low {{ background: var(--ia-sky-soft); color: var(--ia-sky-text); }}
.ia-pill {{ display: inline-block; border-radius: 999px; padding: 3px 10px; font-size: 0.78rem; font-weight: 600;
    background: var(--ia-primary-soft); color: var(--ia-primary-text); margin: 2px 4px 2px 0; }}
.ia-prio {{ color: var(--ia-primary-text); font-size: 0.74rem; font-weight: 700; }}
.ia-list {{ background: var(--ia-card); border: 1px solid var(--ia-border); border-radius: 12px; padding: 10px 14px; height: 100%; }}
.ia-list h4 {{ color: var(--ia-text); font-size: 0.88rem; margin: 0 0 6px; display: flex; gap: 6px; align-items: center; }}
.ia-list ul {{ margin: 0; padding-left: 1.1rem; color: var(--ia-text); font-size: 0.86rem; line-height: 1.5; }}
.ia-list .empty {{ color: var(--ia-muted); font-size: 0.84rem; }}
.ia-progress {{ background: var(--ia-card); border: 1px solid var(--ia-border); border-radius: 14px; padding: 14px 16px; box-shadow: var(--ia-shadow); }}
.ia-progress .head {{ color: var(--ia-text); font-weight: 700; font-size: 0.98rem; margin-bottom: 8px; display: flex; justify-content: space-between; }}
.ia-progress .head span {{ color: var(--ia-muted); font-weight: 500; font-size: 0.85rem; }}
.ia-prow {{ display: flex; gap: 10px; align-items: center; padding: 7px 4px; border-top: 1px solid var(--ia-border); }}
.ia-prow:first-of-type {{ border-top: none; }}
.ia-prow .ic {{ width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
.ia-prow .ic .msr {{ font-size: 17px; }}
.ia-prow .name {{ color: var(--ia-text); font-weight: 600; font-size: 0.88rem; }}
.ia-prow .det {{ color: var(--ia-muted); font-size: 0.8rem; }}
.ia-pending .ic {{ background: var(--ia-row-alt); color: var(--ia-muted); border: 1px solid var(--ia-border); }}
.ia-running .ic {{ background: var(--ia-primary-soft); color: var(--ia-primary); }}
.ia-running .ic .msr {{ animation: ia-spin 1.1s linear infinite; }}
.ia-done .ic {{ background: var(--ia-green); color: #FFFFFF; }}
@keyframes ia-spin {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
.ia-section {{ color: var(--ia-text); font-weight: 700; font-size: 1.05rem; margin: 18px 0 8px; display: flex; gap: 8px; align-items: center; }}
.ia-section .msr {{ color: var(--ia-primary); }}
.ia-kicker {{ color: var(--ia-muted); font-size: 0.86rem; margin: -4px 0 10px; }}
.ia-hist {{ background: var(--ia-card); border: 1px solid var(--ia-border); border-radius: 12px; padding: 12px 14px; }}
.ia-hist .top {{ display: flex; justify-content: space-between; gap: 10px; color: var(--ia-muted); font-size: 0.8rem; }}
.ia-hist .ttl {{ color: var(--ia-text); font-weight: 700; margin: 4px 0; }}
.ia-hist .sum {{ color: var(--ia-text); font-size: 0.86rem; }}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)


def icon(name: str) -> str:
    return f'<span class="msr" aria-hidden="true">{name}</span>'


def e(text) -> str:
    return escape(str(text or ""))


def hero():
    st.markdown(
        f'<div class="ia-hero"><div class="logo">{icon("precision_manufacturing")}</div>'
        '<div><h1>Industria-AI</h1><p>Industrial problem analyzer · a team of AI specialists, '
        'with you in control</p></div></div>', unsafe_allow_html=True)


def banner(kind: str, text: str, ic: str = None):
    ic = ic or {"info": "info", "warn": "warning", "ok": "check_circle", "err": "error"}[kind]
    st.markdown(f'<div class="ia-banner ia-b-{kind}">{icon(ic)}<div>{text}</div></div>', unsafe_allow_html=True)


def note(text: str, ic: str = "lock"):
    st.markdown(f'<div class="ia-note">{icon(ic)}<span>{text}</span></div>', unsafe_allow_html=True)


def section(title: str, ic: str, kicker: str = ""):
    st.markdown(f'<div class="ia-section">{icon(ic)}{e(title)}</div>', unsafe_allow_html=True)
    if kicker:
        st.markdown(f'<div class="ia-kicker">{kicker}</div>', unsafe_allow_html=True)


def step_guide(steps, current: int):
    rows = []
    for i, (title, desc) in enumerate(steps, 1):
        cls = "active" if i == current else ("done" if i < current else "")
        num = "✓" if i < current else str(i)
        rows.append(f'<div class="ia-step {cls}"><div class="num">{num}</div>'
                    f'<div><div class="t">{e(title)}</div><div class="d">{e(desc)}</div></div></div>')
    st.markdown('<div class="ia-steps">' + "".join(rows) + "</div>", unsafe_allow_html=True)


def summary_box(text: str, verdict: str = ""):
    v = f'<div class="verdict">Reviewer verdict: {e(verdict)}</div>' if verdict else ""
    st.markdown(f'<div class="ia-summary">{e(text)}{v}</div>', unsafe_allow_html=True)


def ranked_table(causes):
    rows = []
    for i, c in enumerate(causes, 1):
        rows.append(
            f"<tr><td><b>{i}</b></td><td><b>{e(c['cause'])}</b><div class='sub'>{e(c['category'])}</div></td>"
            f"<td><span class='ia-chip ia-chip-{c['likelihood']}'>{e(c['likelihood'])} · {c['likelihood_pct']}%</span></td>"
            f"<td>{e(c.get('evidence'))}</td>"
            f"<td>{e(c.get('action'))}<div class='ia-prio'>{e(c.get('priority'))}</div></td>"
            f"<td>{e(c.get('verification'))}</td></tr>")
    if not rows:
        rows.append("<tr><td colspan='6'>No ranked causes were produced.</td></tr>")
    st.markdown(
        "<div style='overflow-x:auto'><table class='ia-table'><thead><tr><th>#</th><th>Root cause</th><th>Likelihood</th>"
        "<th>Evidence</th><th>Recommended action</th><th>How to verify</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table></div>", unsafe_allow_html=True)


def list_card(title: str, items, ic: str):
    items = [i for i in (items or []) if str(i).strip()]
    body = "<ul>" + "".join(f"<li>{e(i)}</li>" for i in items) + "</ul>" if items else "<div class='empty'>None stated.</div>"
    st.markdown(f'<div class="ia-list"><h4>{icon(ic)}{e(title)}</h4>{body}</div>', unsafe_allow_html=True)


def pills(items):
    st.markdown("".join(f'<span class="ia-pill">{e(i)}</span>' for i in items), unsafe_allow_html=True)


def progress_html(rows, title: str, elapsed: float) -> str:
    icons = {"pending": "radio_button_unchecked", "running": "progress_activity", "done": "check"}
    out = [f'<div class="ia-progress"><div class="head">{e(title)}<span>{int(elapsed)} s</span></div>']
    for r in rows:
        out.append(f'<div class="ia-prow ia-{r["status"]}"><div class="ic">{icon(icons[r["status"]])}</div>'
                   f'<div><div class="name">{e(r["name"])}</div><div class="det">{e(r.get("detail", ""))}</div></div></div>')
    out.append("</div>")
    return "".join(out)
