from datetime import datetime
import streamlit as st

def add_audit(log, event, detail):
    log.append({"time": datetime.now().strftime("%H:%M:%S"), "event": event, "detail": detail})

def render_audit(log):
    if not log:
        st.caption("No events yet.")
        return
    for item in log:
        st.write(f"**{item['time']} — {item['event']}**  ")
        st.caption(item['detail'])
