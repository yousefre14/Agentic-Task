"""
app.py — Kayfa Portal Gateway & Welcome Lounge
"""
import streamlit as st

st.set_page_config(
    page_title="Kayfa Portal — كيف",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

from Auth import render_login_page, get_user_role, get_authenticator
from styles import inject_theme, render_topbar, gold_divider, logo1_b64, logo2_b64

# ── theme ─────────────────────────────────────────────────────────────────────
inject_theme()

# ── auth ──────────────────────────────────────────────────────────────────────
auth_status, name, username = render_login_page()
if not auth_status:
    st.stop()

# ── SIDEBAR: COST MONITORING DASHBOARD ────────────────────────────────────────
with st.sidebar:
    st.header("📊 Cost & Usage Monitor")
    st.markdown("Real-time metrics accumulated via `usage_tracker.py`")
    st.write("---")
    
    # Safely fetch accumulated metrics from st.session_state with default values
    total_tokens = st.session_state.get("usage_total_tokens", 0)
    total_cost = st.session_state.get("usage_total_cost", 0.0)
    turns_count = st.session_state.get("usage_turn_count", 0)
    
    # Display neat metric card rows
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Total Cost (USD)", value=f"${total_cost:.5f}")
    with col2:
        st.metric(label="Total Turns", value=turns_count)
        
    st.metric(label="Total Tokens Consumed", value=f"{total_tokens:,}")
    
    st.write("---")
    if st.button("Reset Session & Metrics"):
        st.session_state.history = []
        st.session_state.messages = []
        if "usage_total_tokens" in st.session_state:
            del st.session_state["usage_total_tokens"]
            del st.session_state["usage_total_cost"]
            del st.session_state["usage_turn_count"]
        st.rerun()

# ── header ────────────────────────────────────────────────────────────────────
role = get_user_role()
render_topbar(
    "Sales Agent Workspace",
    "Automated Client Intelligence & Unstructured RAG Pipeline"
)
gold_divider()

st.markdown("<br>", unsafe_allow_html=True)

# ── welcome line ──────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="margin-bottom:1.75rem">
    <span style="font-size:1rem;color:#64748B">Welcome back, </span>
    <span style="font-size:1rem;font-weight:600;color:#F5A623">{name}</span>
    <span style="font-size:.85rem;color:#475569;margin-left:.5rem">({role.replace('_',' ').title()})</span>
</div>
""", unsafe_allow_html=True)

# ── navigation cards ──────────────────────────────────────────────────────────
col1, col2 = st.columns(2, gap="large")

CARD = """
<div style="
    background: rgba(255,255,255,.025);
    border: 1px solid rgba(255,255,255,.07);
    border-radius: 16px;
    padding: 2.25rem;
    text-align: center;
    min-height: 210px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
">
    <div style="font-size:3rem;margin-bottom:.85rem">{icon}</div>
    <h3 style="margin:0 0 .6rem;font-weight:700;color:#F1F5F9;font-size:1.1rem">{title}</h3>
    <p style="color:#64748B;font-size:.875rem;line-height:1.6;max-width:320px;margin:0">{desc}</p>
</div>
"""

with col1:
    st.markdown(CARD.format(
        icon="💬",
        title="AI Sales Assistant",
        desc="Engage prospective learners, get grounded RAG recommendations, and automatically capture CRM pipeline tickets.",
    ), unsafe_allow_html=True)
    st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
    if st.button("Launch Chat Workspace →", key="go_chat",
                 type="primary", use_container_width=True):
        st.switch_page("pages/chat_agent.py")

with col2:
    st.markdown(CARD.format(
        icon="📊",
        title="Operational CRM Hub",
        desc="Review incoming qualified leads, analyze enrollment funnel conversion stats, and update acquisition pipeline.",
    ), unsafe_allow_html=True)
    st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
    if role in ("sales_rep", "admin"):
        if st.button("Open Lead Dashboard →", key="go_crm",
                     type="primary", use_container_width=True):
            st.switch_page("pages/crm_dashbored.py")
    else:
        st.button("🔒 CRM Access Restricted", key="go_crm_disabled",
                  disabled=True, use_container_width=True)

# ── footer ────────────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
gold_divider()

_, btn_col = st.columns([8, 2])
with btn_col:
    if st.button("🚪 Terminate Session", use_container_width=True):
        st.session_state.clear()
        st.rerun()