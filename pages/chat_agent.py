"""
pages/chat_agent.py — Kayfa AI Chat Interface
"""

import re
import streamlit as st
import uuid
from db import ConversationDB
from Auth import get_authenticator
from agent import build_agent, run_agent
from styles import inject_theme, render_topbar, gold_divider, render_sidebar_logo

# ── auth guard ────────────────────────────────────────────────────
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

    if st.button("➕ New conversation", width="stretch", type="primary"):
        st.session_state.session_id    = str(uuid.uuid4())
        st.session_state.messages      = []
        st.session_state.agent_history = []
        st.rerun()
    
    if st.button("Admin Trace", width="stretch"):
        st.switch_page("pages/behavior_trace.py")

    if st.button("📋 CRM Lead Hub Dashboard", width="stretch"):
        st.switch_page("pages/crm_dashbored.py")

    st.header("📊 Cost & Usage Monitor")
    st.markdown("Real-time metrics accumulated via `usage_tracker.py`")
    st.write("---")

    total_tokens = st.session_state.get("usage_total_tokens", 0)
    total_cost   = st.session_state.get("usage_total_cost",   0.0)
    turns_count  = st.session_state.get("usage_turn_count",   0)

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
        for key in ("usage_total_tokens", "usage_total_cost", "usage_turn_count"):
            st.session_state.pop(key, None)
        st.rerun()

    st.divider()
    st.caption(f"ID: `{st.session_state.get('session_id','')[:14]}...`")
    st.caption(f"Total History Turns: **{len(st.session_state.get('messages', []))}**")
    st.divider()
    get_authenticator().logout("🚪 Terminate Session", "sidebar", key="chat_logout")


# ── session init ──────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id    = str(uuid.uuid4())
    st.session_state.messages      = ConversationDB.load_session(st.session_state.session_id)
    st.session_state.agent_history = []


# CONTACT VALIDATION

_PHONE_TRIGGERS = re.compile(
    r"(?:رقم|واتساب|whatsapp|phone|number|my number|رقمي|تواصل)",
    re.IGNORECASE,
)
_EMAIL_TRIGGERS = re.compile(
    r"(?:email|إيميل|ايميل|بريد|mail)",
    re.IGNORECASE,
)

# Anything that has digits and could be a phone number attempt
_PHONE_CANDIDATE = re.compile(r"\+?[\d][\d\s\-\(\)]{6,19}")

# Anything that contains @ (email attempt)
_EMAIL_CANDIDATE = re.compile(r"[^\s@]+@[^\s@]+")

# Valid patterns
_VALID_EMAIL = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

# Supported country patterns: Egypt, Saudi, UAE, Jordan, Syria, Lebanon, Kuwait
_VALID_PHONE_PATTERNS = [
    (re.compile(r"^(\+20|0020|20|0)?1[0125]\d{8}$"),    "مصر — 010/011/012/015 + 8 أرقام"),
    (re.compile(r"^(\+966|00966|966|0)?5\d{8}$"),        "السعودية — 05X + 8 أرقام"),
    (re.compile(r"^(\+971|00971|971|0)?5[024568]\d{7}$"),"الإمارات — 05X + 7 أرقام"),
    (re.compile(r"^(\+962|00962|962|0)?7[789]\d{7}$"),   "الأردن — 077/078/079 + 7 أرقام"),
    (re.compile(r"^(\+963|00963|963|0)?9[0-9]\d{7}$"),   "سوريا — 09X + 7 أرقام"),
    (re.compile(r"^(\+961|00961|961|0)?[37]\d{7}$"),     "لبنان — 03/07 + 7 أرقام"),
    (re.compile(r"^(\+965|00965|965)?[569]\d{7}$"),      "الكويت — 5/6/9 + 7 أرقام"),
]

def _digits_only(s: str) -> str:
    """Strip everything except digits."""
    return re.sub(r"[^\d]", "", s)


def _validate_contact_info(text: str) -> list[str]:
    """
    Scan message for contact-info attempts and return a list of error strings.
    Empty list → message is clean, send to agent.
    Non-empty → block the message and show errors to the user.
    """
    errors = []

    # ── Email validation ───────────────────────────────────────────────────
    email_candidates = _EMAIL_CANDIDATE.findall(text)
    for raw in email_candidates:
        raw = raw.strip(".,;:")
        if not _VALID_EMAIL.match(raw):
            errors.append(
                f"📧 **{raw}** لا يبدو عنوان بريد إلكتروني صحيحاً.\n"
                f"الصيغة الصحيحة: `yourname@example.com`"
                if any("\u0600" <= c <= "\u06FF" for c in text)
                else f"📧 **{raw}** doesn't look like a valid email address.\n"
                     f"Expected format: `yourname@example.com`"
            )

    # ── Phone validation ───────────────────────────────────────────────────
    # Only check for phones if there's a trigger word OR a clear phone-like string
    has_phone_trigger = bool(_PHONE_TRIGGERS.search(text))
    phone_candidates  = _PHONE_CANDIDATE.findall(text)

    for raw in phone_candidates:
        digits = _digits_only(raw)

        # Skip short digit runs (prices, years, course IDs)
        if len(digits) < 8:
            continue

        # Skip if no trigger word and the number is short (could be a price/year)
        if not has_phone_trigger and len(digits) < 10:
            continue

        # Check against all known valid patterns
        matched = any(pattern.match(digits) for pattern, _ in _VALID_PHONE_PATTERNS)
        if not matched:
            is_arabic = any("\u0600" <= c <= "\u06FF" for c in text)
            country_hints = "\n".join(f"  • {hint}" for _, hint in _VALID_PHONE_PATTERNS)
            if is_arabic:
                errors.append(
                    f"📱 **{raw.strip()}** لا يبدو رقم هاتف صحيحاً.\n\n"
                    f"أمثلة على الأرقام المقبولة:\n{country_hints}"
                )
            else:
                errors.append(
                    f"📱 **{raw.strip()}** doesn't look like a valid phone number.\n\n"
                    f"Accepted formats:\n{country_hints}"
                )

    return errors


# ── page header ───────────────────────────────────────────────────────────────
render_topbar(
    "🤖 Kayfa AI Sales Assistant",
    "Ask about diplomas, tracks, pricing, or enrollment · English or العربية"
)
gold_divider()

# ── welcome state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.markdown("""
    <div style="text-align:center; padding:3.5rem 1rem; background: rgba(255,255,255,0.01);
                border: 1px solid rgba(255,255,255,0.03); border-radius:16px; margin-bottom: 1.5rem;">
        <div style="font-size:3rem; margin-bottom:1rem;">🎓</div>
        <div style="font-size:1.2rem; font-weight:700; color:#F1F5F9; margin-bottom:0.5rem;">
            Welcome to Kayfa AI Portal Workspace
        </div>
        <div style="font-size:0.9rem; color:#64748B; max-width:440px; margin:0 auto; line-height:1.65;">
            Inquire about our official AI, Data Science, Cybersecurity, or Web Development tracks instantly.
            <br><br>
            <span style="color:#A0AEC0; font-family:'Cairo', sans-serif;">
                أهلاً بك! اسألني عن الدبلومات والكورسات والأسعار والمسارات المتاحة.
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── replay history ────────────────────────────────────────────────────────────
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


# ── chat input ────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask about diplomas, pricing, or enrollment..."):

    prompt = prompt.strip()

    # ── Basic length guards (unchanged) ───────────────────────────────────
    if len(prompt) < 2:
        st.warning("Message too short.")
        st.stop()
    if len(prompt) > 2000:
        st.warning("Message too long (max 2000 chars).")
        st.stop()

    # ── Contact info validation ────────────────────────────────────────────
    contact_errors = _validate_contact_info(prompt)
    if contact_errors:
        is_ar = any("\u0600" <= c <= "\u06FF" for c in prompt)
        if is_ar:
            st.error("⚠️ يرجى تصحيح معلومات التواصل قبل الإرسال:")
        else:
            st.error("⚠️ Please fix the contact info before sending:")
        for err in contact_errors:
            st.markdown(err)
        st.stop()

    # ── Everything valid — proceed as before ──────────────────────────────
    is_user_ar = any("\u0600" <= c <= "\u06FF" for c in prompt)
    lang_tag   = 'dir="rtl" lang="ar" class="ticket-arabic"' if is_user_ar else 'style="padding:0.25rem 0;"'

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(f'<div {lang_tag}>{prompt}</div>', unsafe_allow_html=True)

    ConversationDB.save_turn(
        session_id = st.session_state.session_id,
        role       = "user",
        content    = prompt,
        user_id    = st.session_state.get("username"),
    )

    with st.spinner("⏳ Searching knowledge base..."):
        agent_instance = build_agent()
        response_text, updated_history = run_agent(
            agent            = agent_instance,
            prompt           = prompt,
            history          = st.session_state.agent_history,
            display_messages = st.session_state.messages,
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
        session_id = st.session_state.session_id,
        role       = "assistant",
        content    = response_text,
        user_id    = st.session_state.get("username"),
    )
    st.rerun()