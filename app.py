"""
app.py — Premium Portal Gateway & Welcome Lounge Hub
"""
import streamlit as st

st.set_page_config(
    page_title="Kayfa Portal — كيف",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed" # Collapsed by default to maximize layout canvas
)

from Auth import render_login_page, get_user_role, get_authenticator
from styles import inject_theme_infrastructure, render_branded_header

# 1. Apply core cyber-corporate glassmorphism skin
inject_theme_infrastructure()

# 2. Hard-force suppression of native sidebar indexes globally
st.markdown("""
<style>
[data-testid="stSidebarNav"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ── AUTHENTICATION BLOCK ───────────────────────────────────────────────────
auth_status, name, username = render_login_page()

if not auth_status:
    st.stop()

# ── PREMIUM WELCOME LOUNGE CONTAINER ───────────────────────────────────────
role = get_user_role()

# Render fixed top branding header zone
render_branded_header(
    title_text="Sales Agent Workspace", 
    subtitle_text="Automated Client Intelligence & Unstructured RAG Pipeline",
    show_back_button=False # Turn off back button on the lounge home page!
)

st.markdown("<br><br>", unsafe_allow_html=True)

# Executive Navigation Grid Layout
col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown("""
    <div style="
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 2.5rem;
        text-align: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    ">
        <div style="font-size: 3.5rem; margin-bottom: 1rem;">💬</div>
        <h3 style="margin: 0 0 10px 0; font-weight: 700; color: #fff;">AI Sales Assistant</h3>
        <p style="color: #94A3B8; font-size: 0.9rem; min-height: 60px;">
            Engage with prospective platform learners, provide grounded RAG recommendations, and automatically capture CRM pipeline tickets.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("Launch Chat Workspace", key="go_chat", type="secondary", use_container_width=True):
        st.switch_page("pages/chat_agent.py")

with col2:
    st.markdown("""
    <div style="
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 2.5rem;
        text-align: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    ">
        <div style="font-size: 3.5rem; margin-bottom: 1rem;">📊</div>
        <h3 style="margin: 0 0 10px 0; font-weight: 700; color: #fff;">Operational CRM Hub</h3>
        <p style="color: #94A3B8; font-size: 0.9rem; min-height: 60px;">
            Review incoming qualified leads, analyze enrollment funnel conversion statistics, and update active student acquisition parameters.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Conditional Access Gating for CRM Dashboard button
    if role in ("sales_rep", "admin"):
        if st.button("Open Lead Dashboard", key="go_crm", type="primary", use_container_width=True):
            st.switch_page("pages/crm_dashbored.py")
    else:
        st.button("🔒 CRM Access Restricted", key="go_crm_disabled", disabled=True, use_container_width=True)

st.markdown("<br><hr style='border-color: rgba(255,255,255,0.05);'><br>", unsafe_allow_html=True)

# Secure Centralized Logout Button Row
lbl_col, btn_col = st.columns([8, 2])
with btn_col:
    authenticator = get_authenticator()
    # Call dummy log out engine safely inside page matrix boundaries
    if st.button("🚪 Terminate Session", use_container_width=True):
        st.session_state.clear()
        st.rerun()