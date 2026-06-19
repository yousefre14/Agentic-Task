"""
pages/chat_agent.py — Kayfa AI Chat Interface
Design updated — ZERO logic changes.
"""

import streamlit as st
import uuid
from db import ConversationDB
from Auth import get_authenticator
from agent import build_agent, run_agent
from styles import inject_theme, render_topbar, gold_divider, render_sidebar_logo

# ── auth guard — UNCHANGED ────────────────────────────────────────────────────
if not st.session_state.get("authentication_status"):
    st.warning("⚠️ Please log in first.")
    st.stop()

# ── theme ─────────────────────────────────────────────────────────────────────
inject_theme()

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar_logo()
    st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)
    st.divider()
    
    st.markdown(f"👤 Active Session: **{st.session_state.get('name','User')}**")
    st.caption(f"Role clearance: `{st.session_state.get('role','visitor').upper()}`")
    st.divider()

    if st.button("➕ New conversation", use_container_width=True, type="primary"):
        st.session_state.session_id    = str(uuid.uuid4())
        st.session_state.messages      = []
        st.session_state.agent_history = []
        st.rerun()

    if st.button("📋 CRM Lead Hub Dashboard", use_container_width=True):
        st.switch_page("pages/crm_dashbored.py")

    st.divider()
    st.caption(f"ID: `{st.session_state.get('session_id','')[:14]}...`")
    st.caption(f"Total History Turns: **{len(st.session_state.get('messages', []))}**")

    st.divider()

    get_authenticator().logout("🚪 Terminate Session", "sidebar", key="chat_logout")

# ── session init — UNCHANGED ──────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id    = str(uuid.uuid4())
    st.session_state.messages      = ConversationDB.load_session(st.session_state.session_id)
    st.session_state.agent_history = []

# ── page header with logo ──────────────────────────────────────────────────────
render_topbar(
    "🤖 Kayfa AI Sales Assistant",
    "Ask about diplomas, tracks, pricing, or enrollment · English or العربية"
)
gold_divider()

# ── welcome state (empty conversation) ────────────────────────────────────────
if not st.session_state.messages:
    st.markdown("""
    <div style="text-align:center; padding:3.5rem 1rem; background: rgba(255,255,255,0.01); border: 1px solid rgba(255,255,255,0.03); border-radius:16px; margin-bottom: 1.5rem;">
        <div style="font-size:3rem; margin-bottom:1rem;">🎓</div>
        <div style="font-size:1.2rem; font-weight:700; color:#F1F5F9; margin-bottom:0.5rem; letter-spacing:-0.01em;">
            Welcome to Kayfa AI Portal Workspace
        </div>
        <div style="font-size:0.9rem; color:#64748B; max-width:440px; margin:0 auto; line-height:1.65;">
            Inquire about our official AI, Data Science, Cybersecurity, or Web Development tracks instantly.
            <br><br>
            <span style="color:#A0AEC0; font-family:'Cairo', sans-serif;">أهلاً بك! اسألني عن الدبلومات والكورسات والأسعار والمسارات المتاحة.</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── replay history — LOGIC UNCHANGED ──────────────────────────────────────────
for msg in st.session_state.messages:
    is_ar    = any("\u0600" <= c <= "\u06FF" for c in msg["content"])
    lang_tag = 'dir="rtl" lang="ar" class="ticket-arabic"' if is_ar else 'style="padding:0.25rem 0;"'
    with st.chat_message(msg["role"]):
        st.markdown(f'<div {lang_tag}>{msg["content"]}</div>', unsafe_allow_html=True)

# ── guidance line ─────────────────────────────────────────────────────────────
st.markdown("""
<div style="font-size:0.8rem; color:#64748B; background:rgba(255,255,255,.01);
            border-left:3px solid #F5A623; border-radius:4px;
            padding:0.6rem 1rem; margin: 1.5rem 0 0.5rem 0;">
    💡 Language Auto-detection Active: System matches input query dialect (English / العربية) instantly.
</div>
""", unsafe_allow_html=True)

# ── chat input — LOGIC COMPLETELY UNCHANGED ───────────────────────────────────
if prompt := st.chat_input("Ask about diplomas, pricing, or enrollment..."):

    prompt = prompt.strip()
    if len(prompt) < 2:
        st.warning("Message too short.")
        st.stop()
    if len(prompt) > 2000:
        st.warning("Message too long (max 2000 chars).")
        st.stop()

    is_user_ar = any("\u0600" <= c <= "\u06FF" for c in prompt)
    lang_tag   = 'dir="rtl" lang="ar" class="ticket-arabic"' if is_user_ar else 'style="padding:0.25rem 0;"'

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(f'<div {lang_tag}>{prompt}</div>', unsafe_allow_html=True)

    ConversationDB.save_turn(
        session_id=st.session_state.session_id,
        role="user", content=prompt,
        user_id=st.session_state.get("username"),
    )

    with st.spinner("⏳ Searching knowledge base..."):
        agent_instance = build_agent()
        response_text, updated_history = run_agent(
            agent=agent_instance,
            prompt=prompt,
            history=st.session_state.agent_history,
            display_messages=st.session_state.messages,
        )

    if not response_text or not response_text.strip():
        response_text = (
            "عذراً، لم أتمكن من معالجة طلبك. يرجى إعادة المحاولة."
            if is_user_ar else
            "Sorry, I couldn't process that. Please try again."
        )

    is_agent_ar    = any("\u0600" <= c <= "\u06FF" for c in response_text)
    agent_lang_tag = 'dir="rtl" lang="ar" class="ticket-arabic"' if is_agent_ar else 'style="padding:0.25rem 0;"'

    with st.chat_message("assistant"):
        st.markdown(f'<div {agent_lang_tag}>{response_text}</div>', unsafe_allow_html=True)

    st.session_state.messages.append({"role": "assistant", "content": response_text})
    st.session_state.agent_history = updated_history

    ConversationDB.save_turn(
        session_id=st.session_state.session_id,
        role="assistant", content=response_text,
        user_id=st.session_state.get("username"),
    )
    st.rerun()