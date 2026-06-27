"""
app.py — Kayfa Portal Gateway & Welcome Lounge
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from agent import build_agent
from Auth import render_login_page, get_user_role
from styles import inject_theme, render_topbar, gold_divider, logo1_b64, logo2_b64
from db import LeadDB

st.set_page_config(
    page_title="Kayfa Portal — كيف",
    page_icon=logo2_b64,
    layout="wide",
    initial_sidebar_state="expanded",
)

if "agent" not in st.session_state:
    st.session_state.agent = build_agent()

if "history" not in st.session_state:
    st.session_state.history = []

if "messages" not in st.session_state:
    st.session_state.messages = []


# ── theme ─────────────────────────────────────────────────────────────────────
inject_theme()

# ── auth ──────────────────────────────────────────────────────────────────────
auth_status, name, username = render_login_page()
if not auth_status:
    st.stop()


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
col1, col2, col3 = st.columns(3, gap="large")

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
                 type="primary", width="stretch"):
        st.switch_page("pages/chat_agent.py")

with col2:
    st.markdown(CARD.format(
        icon="📋",
        title="Operational CRM Hub",
        desc="Review incoming qualified leads, analyze enrollment funnel conversion stats, and update acquisition pipeline.",
    ), unsafe_allow_html=True)
    st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
    if role in ("sales_rep", "admin"):
        if st.button("Open Lead Dashboard →", key="go_crm",
                     type="primary", width="stretch"):
            st.switch_page("pages/crm_dashbored.py")
    else:
        st.button("🔒 CRM Access Restricted", key="go_crm_disabled",
                  disabled=True, width="stretch")

with col3:
    st.markdown(CARD.format(
        icon="🔍",
        title="Behaviour & Trace Monitor",
        desc="Replay every agent turn step-by-step: retrieval, tool calls, sources, response, tokens, latency, and cost.",
    ), unsafe_allow_html=True)
    st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
    if role == "admin":
        if st.button("Open Trace Monitor →", key="go_trace",
                     type="primary", width="stretch"):
            st.switch_page("pages/behavior_trace.py")
    else:
        st.button("🔒 Admin Access Only", key="go_trace_disabled",
                  disabled=True, width="stretch")


# COST & USAGE MONITOR

st.markdown("<br>", unsafe_allow_html=True)
gold_divider()
st.header("📊 Cost & Usage Monitor")


# ── This session (all roles) ──────────────────────────────────────────────────
st.markdown("#### This Session")

total_tokens = st.session_state.get("usage_total_tokens", 0)
total_cost   = st.session_state.get("usage_total_cost",   0.0)
turns_count  = st.session_state.get("usage_turn_count",   0)
avg_per_turn = (total_cost / turns_count) if turns_count else 0.0

s1, s2, s3, s4 = st.columns(4)
s1.metric("Session Cost",    f"${total_cost:.5f}")
s2.metric("Turns",           turns_count)
s3.metric("Tokens Used",     f"{total_tokens:,}")
s4.metric("Avg Cost / Turn", f"${avg_per_turn:.5f}")


# ── Platform-wide stats (admin only) ─────────────────────────────────────────
if role == "admin":
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Platform Overview")

    window_col, _ = st.columns([1, 5])
    with window_col:
        window = st.selectbox(
            "Lookback window",
            options=[7, 14, 30, 90],
            format_func=lambda d: f"Last {d} days",
            index=1,
            label_visibility="collapsed",
        )

    since = datetime.now(timezone.utc) - timedelta(days=window)

    with st.spinner("Loading platform stats…"):
        try:
            db = LeadDB.db

            # ── aggregate over usage_turns ─────────────────────────────────
            agg = list(db["usage_turns"].aggregate([
                {"$match": {"timestamp": {"$gte": since}}},
                {"$group": {
                    "_id":                  None,
                    "total_cost":           {"$sum": "$total_cost_usd"},
                    "total_llm_cost":       {"$sum": "$llm_cost_usd"},
                    "total_emb_cost":       {"$sum": "$embedding_cost_usd"},
                    "total_turns":          {"$sum": 1},
                    "total_input_tokens":   {"$sum": "$input_tokens"},
                    "total_output_tokens":  {"$sum": "$output_tokens"},
                    "retrieval_turns":      {"$sum": {"$cond": ["$retrieval_ran", 1, 0]}},
                    "arabic_turns":         {"$sum": {"$cond": ["$is_arabic",    1, 0]}},
                }},
            ]))
            a = agg[0] if agg else {}

            total_cost_all  = round(a.get("total_cost",         0.0), 6)
            total_llm       = round(a.get("total_llm_cost",     0.0), 6)
            total_emb       = round(a.get("total_emb_cost",     0.0), 6)
            total_turns_all = a.get("total_turns",              0)
            ret_turns       = a.get("retrieval_turns",          0)
            arabic_turns    = a.get("arabic_turns",             0)
            avg_in          = round(a.get("total_input_tokens",  0) / max(total_turns_all, 1), 0)
            avg_out         = round(a.get("total_output_tokens", 0) / max(total_turns_all, 1), 0)

            total_sessions = db["usage_sessions"].count_documents(
                {"last_seen": {"$gte": since}}
            )

            # ── KPI row ───────────────────────────────────────────────────
            k1, k2, k3, k4, k5, k6 = st.columns(6)
            k1.metric("Total Spend",         f"${total_cost_all:.4f}")
            k2.metric("Unique Sessions",     total_sessions)
            k3.metric("Total Turns",         total_turns_all)
            k4.metric("Cost / Session",      f"${total_cost_all / max(total_sessions, 1):.5f}")
            k5.metric("Avg Turns / Session", f"{total_turns_all / max(total_sessions, 1):.1f}")
            k6.metric("Cost / Turn",         f"${total_cost_all / max(total_turns_all, 1):.5f}")

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Cost breakdown row (LLM vs embeddings) ────────────────────
            st.markdown("**Cost breakdown**")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("LLM Cost",          f"${total_llm:.5f}",
                      help="Chat model tokens only.")
            c2.metric("Embedding Cost",    f"${total_emb:.5f}",
                      help="Local model — $0 now, tracked for when you switch providers.")
            c3.metric("KB Retrieval Rate", f"{ret_turns / max(total_turns_all, 1) * 100:.1f}%",
                      help="% of turns that queried the knowledge base.")
            c4.metric("Arabic Traffic",    f"{arabic_turns / max(total_turns_all, 1) * 100:.1f}%",
                      help="% of turns in Arabic.")

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Token health row ──────────────────────────────────────────
            st.markdown("**Token health**")
            t1, t2 = st.columns(2)
            t1.metric("Avg Input Tokens / Turn",  f"{avg_in:,.0f}",
                      help="Rising over time = history bloat returning.")
            t2.metric("Avg Output Tokens / Turn", f"{avg_out:,.0f}",
                      help="Very high = model over-explaining.")

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Daily spend chart ─────────────────────────────────────────
            daily = list(db["usage_turns"].aggregate([
                {"$match": {"timestamp": {"$gte": since}}},
                {"$group": {
                    "_id":   {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                    "cost":  {"$sum": "$total_cost_usd"},
                    "turns": {"$sum": 1},
                }},
                {"$sort": {"_id": 1}},
            ]))

            if daily:
                st.markdown("**Daily spend (USD)**")
                daily_df = pd.DataFrame([
                    {"date": d["_id"], "cost_usd": round(d["cost"], 6)}
                    for d in daily
                ])
                daily_df["date"] = pd.to_datetime(daily_df["date"])
                daily_df = daily_df.set_index("date")
                st.area_chart(daily_df["cost_usd"], width="stretch", height=200)
            else:
                st.info("No turn data yet for the selected window.")

            # ── Per-user cost table ───────────────────────────────────────
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**Cost by user**")
            per_user = list(db["usage_turns"].aggregate([
                {"$match": {"timestamp": {"$gte": since}, "user_id": {"$ne": None}}},
                {"$group": {
                    "_id":         "$user_id",
                    "total_cost":  {"$sum": "$total_cost_usd"},
                    "turns":       {"$sum": 1},
                    "last_active": {"$max": "$timestamp"},
                }},
                {"$sort": {"total_cost": -1}},
                {"$limit": 20},
            ]))

            if per_user:
                user_df = pd.DataFrame([{
                    "User":        u["_id"],
                    "Cost (USD)":  f"${u['total_cost']:.5f}",
                    "Turns":       u["turns"],
                    "Last Active": u["last_active"].strftime("%Y-%m-%d %H:%M") if u.get("last_active") else "—",
                } for u in per_user])
                st.dataframe(user_df, width="stretch", hide_index=True)
            else:
                st.info("No per-user data yet — user_id stamps appear after the next chat turn.")

            # ── Top cost sessions ─────────────────────────────────────────
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**Top 5 most expensive sessions**")
            top_sessions = list(
                db["usage_sessions"]
                .find({"last_seen": {"$gte": since}},
                      {"_id": 1, "user_id": 1, "total_cost_usd": 1,
                       "turn_count": 1, "first_seen": 1, "last_seen": 1})
                .sort("total_cost_usd", -1)
                .limit(5)
            )
            if top_sessions:
                sess_df = pd.DataFrame([{
                    "Session":    str(s["_id"])[:8] + "…",
                    "User":       s.get("user_id", "—"),
                    "Cost (USD)": f"${s.get('total_cost_usd', 0):.5f}",
                    "Turns":      s.get("turn_count", 0),
                    "First Seen": s["first_seen"].strftime("%Y-%m-%d %H:%M") if s.get("first_seen") else "—",
                    "Last Seen":  s["last_seen"].strftime("%Y-%m-%d %H:%M")  if s.get("last_seen")  else "—",
                } for s in top_sessions])
                st.dataframe(sess_df, width="stretch", hide_index=True)
                st.caption("Outlier sessions may indicate unusually long conversations or testing.")
            else:
                st.info("No session data yet for this window.")

        except Exception as e:
            st.warning(f"Could not load platform stats: {e}")


# ── footer ────────────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
gold_divider()

_, btn_col = st.columns([8, 2])
with btn_col:
    if st.button("🚪 Terminate Session", width="stretch"):
        st.session_state.clear()
        st.rerun()