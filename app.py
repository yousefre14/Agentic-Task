"""
pages/app.py — Main Chat Interface for Visitors

STRUCTURE:
1. Check authentication
2. Render Kayfa branding
3. Display chat history (with RTL support for Arabic)
4. Chat input + agent response
5. Save to MongoDB
6. Detect & capture leads
"""

import streamlit as st
from streamlit_option_menu import option_menu
import uuid
from datetime import datetime
from db import ConversationDB, LeadDB
from agent import run_agent
from Auth import check_authentication, get_user_role, load_authenticator
import json

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="Kayfa Chat — كيف",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# RTL CSS for Arabic text support
def apply_rtl_styling():
    """Apply CSS for proper Arabic RTL rendering."""
    st.markdown("""
    <style>
    /* Detect Arabic text and apply RTL */
    [data-testid="stChatMessage"] {
        direction: auto;
    }
    
    /* Arabic-specific styling */
    [lang="ar"] {
        direction: rtl;
        text-align: right;
        font-family: 'Segoe UI', 'Noto Sans Arabic', Arial, sans-serif;
    }
    
    /* Message bubbles RTL support */
    .stChatMessage {
        direction: auto;
    }
    
    /* Ensure proper text rendering */
    body {
        overflow-wrap: break-word;
        word-break: normal;
    }
    </style>
    """, unsafe_allow_html=True)

apply_rtl_styling()

# ==================== AUTHENTICATION ====================
auth_status, name, username = check_authentication()

if not auth_status:
    st.warning("⚠️ يرجى تسجيل الدخول أولاً | Please log in first")
    st.stop()

# ==================== ROLE CHECK ====================
user_role = get_user_role()
if user_role != 'visitor':
    st.error("❌ هذه الصفحة للزوار فقط | This page is for visitors only")
    st.stop()

# ==================== SESSION STATE INIT ====================
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = ConversationDB.load_session(st.session_state.session_id)
    st.session_state.history = []
    st.session_state.user_language = 'ar'  # Default to Arabic
    st.session_state.user_dialect = 'egyptian'
    st.session_state.lead_data = {}  # Capture lead info

# ==================== SIDEBAR ====================
with st.sidebar:
    st.markdown("## 🎓 Kayfa Chat")
    st.markdown("---")
    
    # Language selector
    language = st.radio(
        "اللغة | Language",
        options=['Arabic', 'English'],
        index=0
    )
    st.session_state.user_language = 'ar' if language == 'Arabic' else 'en'
    
    # Dialect (if Arabic)
    if st.session_state.user_language == 'ar':
        dialect = st.selectbox(
            "اللهجة | Dialect",
            options=['Egyptian', 'Saudi', 'Syrian'],
            index=0
        )
        dialect_map = {'Egyptian': 'egyptian', 'Saudi': 'saudi', 'Syrian': 'syrian'}
        st.session_state.user_dialect = dialect_map[dialect]
    
    st.markdown("---")
    
    # Session info
    st.markdown(f"**Session ID:** `{st.session_state.session_id[:8]}...`")
    st.markdown(f"**Messages:** {len(st.session_state.messages)}")
    
    st.markdown("---")
    
    # Logout
    authenticator = load_authenticator()
    if st.button("🚪 تسجيل الخروج | Logout", key="logout_btn"):
        authenticator.logout('Logout', 'unrendered')
        st.session_state.clear()
        st.rerun()

# ==================== MAIN CONTENT ====================
st.markdown("""
<div style="text-align: center;">
    <h1>كيفاء 💬 Kayfa Chat</h1>
    <p>سؤالك عن التعليم | Your education guide</p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ==================== CHAT HISTORY REPLAY ====================
for msg in st.session_state.messages:
    # Detect language for proper direction
    is_arabic = any('\u0600' <= c <= '\u06FF' for c in msg['content'])
    lang_attr = 'lang="ar"' if is_arabic else ''
    
    with st.chat_message(msg['role']):
        st.markdown(f"<div {lang_attr}>{msg['content']}</div>", unsafe_allow_html=True)

# ==================== CHAT INPUT ====================
if prompt := st.chat_input("اسأل عن أي شيء | Ask anything..."):
    
    # ========== USER MESSAGE ==========
    st.session_state.messages.append({'role': 'user', 'content': prompt})
    
    is_arabic = any('\u0600' <= c <= '\u06FF' for c in prompt)
    lang_attr = 'lang="ar"' if is_arabic else ''
    
    with st.chat_message('user'):
        st.markdown(f"<div {lang_attr}>{prompt}</div>", unsafe_allow_html=True)
    
    # Save to MongoDB
    ConversationDB.save_turn(
        session_id=st.session_state.session_id,
        role='user',
        content=prompt,
        user_id=username
    )
    
    # ========== AGENT RESPONSE ==========
    with st.chat_message('assistant'):
        with st.spinner("🤔 Thinking..."):
            # Run agent
            response = run_agent(
                prompt,
                st.session_state.history,
                language=st.session_state.user_language,
                dialect=st.session_state.user_dialect
            )
        
        # Detect response language
        is_arabic_response = any('\u0600' <= c <= '\u06FF' for c in response)
        lang_attr = 'lang="ar"' if is_arabic_response else ''
        
        st.markdown(f"<div {lang_attr}>{response}</div>", unsafe_allow_html=True)
    
    # Save assistant response to MongoDB
    ConversationDB.save_turn(
        session_id=st.session_state.session_id,
        role='assistant',
        content=response,
        user_id=username
    )
    
    # Update message history for agent
    st.session_state.messages.append({'role': 'assistant', 'content': response})
    st.session_state.history = [
        {'role': m['role'], 'content': m['content']}
        for m in st.session_state.messages
    ]
    
    # ========== LEAD DETECTION ==========
    # Detect buying signals (keywords indicating serious interest)
    buying_signals = ['تسجيل', 'دفع', 'enrollment', 'price', 'start', 'when']
    lead_quality_score = 0
    
    for signal in buying_signals:
        if signal in prompt.lower():
            lead_quality_score += 1
    
    if lead_quality_score >= 1:
        st.info("✅ We detected strong interest! Let us capture your details for our team.")
        
        # Show lead capture form
        with st.expander("📝 Share Your Details"):
            col1, col2 = st.columns(2)
            
            with col1:
                name_input = st.text_input("الاسم | Name")
                email_input = st.text_input("البريد الإلكتروني | Email")
                phone_input = st.text_input("رقم الهاتف / واتساب | Phone/WhatsApp")
            
            with col2:
                city_input = st.text_input("المدينة | City")
                country_input = st.text_input("الدولة | Country", value="Egypt")
            
            if st.button("✉️ تسجيل | Submit Lead"):
                if name_input and email_input:
                    # Create CRM ticket
                    ticket = {
                        'name': name_input,
                        'email': email_input,
                        'phone': phone_input,
                        'city': city_input,
                        'country': country_input,
                        'language': 'ar' if st.session_state.user_language == 'ar' else 'en',
                        'dialect': st.session_state.user_dialect,
                        'session_id': st.session_state.session_id,
                        'conversation_summary': '\n'.join([
                            f"{m['role']}: {m['content']}" 
                            for m in st.session_state.messages[-6:]  # Last 6 messages
                        ]),
                        'lead_temperature': 'hot' if lead_quality_score > 1 else 'warm',
                        'buying_signals': buying_signals,
                        'conversation_link': f"https://yourdomain.com/crm?session={st.session_state.session_id}"
                    }
                    
                    LeadDB.create_ticket(ticket)
                    st.success("✅ شكراً! تم تسجيل بيانات الاهتمام | Thank you! Lead captured!")
                    st.balloons()
                else:
                    st.error("Please fill in at least name and email.")