"""
app.py — Kayfa Portal Gateway & Welcome Lounge
"""
import streamlit as st

st.set_page_config(
    page_title="Kayfa Portal — كيف",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Lowercase auth import to match standard file systems
from Auth import render_login_page, get_user_role
from styles import inject_theme, render_topbar, gold_divider

# ── theme injection ───────────────────────────────────────────────────────────
inject_theme()

# Enforce clean full-bleed presentation frame by hiding sidebars completely
st.markdown("""
<style>
[data-testid="stSidebarNav"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ── auth checkpoint ───────────────────────────────────────────────────────────
auth_status, name, username = render_login_page()
if not auth_status:
    st.stop()

# ── top premium bar navigation ────────────────────────────────────────────────
role = get_user_role()
render_topbar(
    "Sales Agent Workspace",
    "Automated Client Intelligence & Unstructured RAG Pipeline"
)
gold_divider()

# ── welcoming profile card ────────────────────────────────────────────────────
st.markdown(f"""
<div style="background: rgba(255,255,255,0.01); border: 1px solid rgba(255,255,255,0.04); padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 2.5rem; display: flex; align-items: center; justify-content: space-between;">
    <div>
        <span style="font-size: 0.95rem; color: #64748B;">Welcome back, </span>
        <span style="font-size: 0.95rem; font-weight: 600; color: #F5A623;">{name}</span>
    </div>
    <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #64748B; background: rgba(255,255,255,0.05); padding: 0.25rem 0.75rem; border-radius: 20px;">
        Role: {role.replace('_',' ').title()}
    </div>
</div>
""", unsafe_allow_html=True)

# ── dynamic hub navigation workspace cards ─────────────────────────────────────
col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown("""
    <div class="option-box">
        <div style="font-size: 2.5rem; margin-bottom: 1rem;">💬</div>
        <h3 style="margin: 0 0 0.5rem 0; font-weight: 700; color: #F1F5F9; font-size: 1.25rem;">AI Sales Assistant</h3>
        <p style="color: #64748B; font-size: 0.9rem; line-height: 1.6; max-width: 340px; margin: 0 auto 1.5rem auto;">
            Engage prospective learners, fetch grounded RAG system details, and dynamically stream CRM lead items.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div style="margin-top: -1rem;"></div>', unsafe_allow_html=True)
    if st.button("Launch Chat Workspace →", key="go_chat", type="primary", use_container_width=True):
        st.switch_page("pages/chat_agent.py")

with col2:
    st.markdown("""
    <div class="option-box">
        <div style="font-size: 2.5rem; margin-bottom: 1rem;">📊</div>
        <h3 style="margin: 0 0 0.5rem 0; font-weight: 700; color: #F1F5F9; font-size: 1.25rem;">Operational CRM Hub</h3>
        <p style="color: #64748B; font-size: 0.9rem; line-height: 1.6; max-width: 340px; margin: 0 auto 1.5rem auto;">
            Review incoming qualified lead tickets, optimize funnel conversion states, and audit live acquisition pipelines.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div style="margin-top: -1rem;"></div>', unsafe_allow_html=True)
    if role in ("sales_rep", "admin"):
        if st.button("Open Lead Dashboard →", key="go_crm", type="primary", use_container_width=True):
            st.switch_page("pages/crm_dashbored.py")
    else:
        st.button("🔒 CRM Access Restricted", key="go_crm_disabled", disabled=True, use_container_width=True)

# ── system utility termination block ──────────────────────────────────────────
st.markdown("<div style='margin-top: 4rem;'></div>", unsafe_allow_html=True)
gold_divider()

_, btn_col = st.columns([7.5, 2.5])
with btn_col:
    if st.button("🚪 Terminate Session", use_container_width=True, key="logout_session"):
        st.session_state.clear()
        st.rerun()