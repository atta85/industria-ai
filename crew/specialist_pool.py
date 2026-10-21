"""
The fixed specialist pool. Keys must match crew/config/agents.yaml and the
list in the intake task. Icons are Material Symbols names used by Streamlit.
"""

SPECIALIST_POOL = {
    "mechanical_specialist": {"label": "Mechanical", "icon": ":material/settings:"},
    "manufacturing_specialist": {"label": "Manufacturing", "icon": ":material/factory:"},
    "electrical_specialist": {"label": "Electrical", "icon": ":material/bolt:"},
    "civil_specialist": {"label": "Civil and structural", "icon": ":material/foundation:"},
    "chemical_specialist": {"label": "Chemical process", "icon": ":material/science:"},
    "materials_specialist": {"label": "Materials", "icon": ":material/diamond:"},
    "biotech_specialist": {"label": "Biotechnology", "icon": ":material/biotech:"},
    "software_specialist": {"label": "Software and automation", "icon": ":material/terminal:"},
    "data_ai_specialist": {"label": "Data and statistics", "icon": ":material/monitoring:"},
    "quality_ops_specialist": {"label": "Quality and reliability", "icon": ":material/verified:"},
}

MAX_SPECIALISTS = 4
DEFAULT_SPECIALISTS = ["manufacturing_specialist", "quality_ops_specialist"]


def label(key: str) -> str:
    return SPECIALIST_POOL.get(key, {}).get("label", key)


def clean_selection(keys, has_data=False):
    """Valid, unique keys only; at least 2, at most 4; data specialist added
    when process data was uploaded."""
    out = []
    for k in keys or []:
        if k in SPECIALIST_POOL and k not in out:
            out.append(k)
    if has_data and "data_ai_specialist" not in out:
        out = out[: MAX_SPECIALISTS - 1] + ["data_ai_specialist"]
    for k in DEFAULT_SPECIALISTS:
        if len(out) >= 2:
            break
        if k not in out:
            out.append(k)
    return out[:MAX_SPECIALISTS]
