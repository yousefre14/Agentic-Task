"""
behaviour_trace.py 
Admin-only page. Shows a full step-by-step replay of how the agent
produced each answer: retrieval → tool calls (args + results) →
sources → final response → tokens + latency + cost per turn.

Also contains the optimisation write-up as a static section.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from Auth import render_login_page, get_user_role
from styles import inject_theme, render_topbar, gold_divider, render_sidebar_logo, logo1_b64, logo2_b64
from db import LeadDB
import re
import streamlit as st
import uuid
from db import ConversationDB
from Auth import get_authenticator
from agent import build_agent, run_agent
from styles import inject_theme, render_topbar, gold_divider


st.set_page_config(
    page_title="Behaviour Trace — Kayfa",
    page_icon=logo2_b64,
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme()

auth_status, name, username = render_login_page()
if not auth_status:
    st.stop()

role = get_user_role()
if role != "admin":
    st.error("🔒 Admin access required.")
    st.stop()

render_topbar(
    "Monitor B — Behaviour & Response Trace",
    "Step-by-step replay of every agent turn: retrieval · tools · sources · response · cost"
)
gold_divider()
st.markdown("<br>", unsafe_allow_html=True)

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar_logo()
    st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)
    st.divider()
    st.markdown(f"👤 Operational View: **{st.session_state.get('name','')}**")
    st.caption("Access Clear: `SALES CONTROL`")
    st.divider()
    if st.button("💬 Launch Chat Agent", width="stretch", type="primary"):
        st.switch_page("pages/chat_agent.py")
    if st.button("📋 CRM Lead Hub Dashboard", width="stretch"):
        st.switch_page("pages/crm_dashbored.py")
    if st.button("🔄 Sync Live Pipeline", width="stretch"):
        st.rerun()
    st.divider()
    st.caption(f"ID: `{st.session_state.get('session_id','')[:14]}...`")
    st.caption(f"Total History Turns: **{len(st.session_state.get('messages', []))}**")
    st.divider()
    get_authenticator().logout("🚪 Terminate Session", "sidebar", key="chat_logout")

# SECTION 0 — OPTIMISATION WRITE-UP 

with st.expander("📋 Optimisation Report — What We Found, Fixed & Saved", expanded=False):
    st.markdown("""
### What the data showed

After instrumenting the agent with per-message cost tracking, three wasteful
behaviours became visible from the terminal output:

| Behaviour | How it was spotted |
|---|---|
| **History bloat** | Turn 2 cost was 3–4× Turn 1 despite similar prompts — tool return payloads (800–2000 tokens of KB content) were being re-sent as message history every turn |
| **Retrieval firing on greetings** | `"hi"` triggered all 3 MongoDB KB queries because the skip pattern was `"hi "` (trailing space), never matching bare `"hi"` |
| **Language reminder on every turn** | ~80-token `[CRITICAL DIRECTIVE]` block was appended unconditionally, including to trivial one-word replies |

---

### What was changed

**Fix 1 — Lean history (`_build_lean_history` in `agent.py`)**
Strips `ToolReturnPart`, `ToolCallPart`, and pre-fetched context blobs from
`message_history` before each LLM call. Only bare user↔assistant text pairs
are kept, capped at 5 turns. KB content is re-fetched fresh each turn anyway —
keeping stale copies in history wasted tokens with zero benefit.

**Fix 2 — QueryRouter pattern fix (`tools.py`)**
Changed `"hi "` → `"hi"` (and all other patterns) by removing trailing spaces.
The fix was one character; the impact was eliminating 3 MongoDB round-trips
plus a ~1500-char context injection on every greeting turn.

**Fix 3 — Conditional language reminder (`agent.py`)**
The `[CRITICAL DIRECTIVE]` block (~80 tokens) now only fires when
`len(prompt) >= 20` AND retrieval wasn't skipped. Short CRM turns and
greetings no longer carry it.

**Fix 4 — Parallel retrieval (`agent.py` + `tools.py`)**
All 3 KB tools (`search_courses`, `search_roadmaps`, `query_unstructured_kb`)
now run concurrently via `asyncio.gather` instead of sequentially. Wall-time
cut from ~3× to ~1× the average MongoDB round-trip latency.

---

### Before vs after

| Metric | Before | After | Change |
|---|---|---|---|
| Cost — Turn 1 greeting (`"hi"`) | $0.001475 | $0.001419 | −4% |
| Retrieval on greeting | ✅ fired (3 DB calls) | ❌ skipped | −100% DB calls |
| History tokens by Turn 3 (estimated) | ~4,000+ | ~800 | −80% |
| Retrieval wall-time | sequential (~900 ms) | parallel (~300 ms) | −67% |

> **Note on Turn 1 greeting:** the 4% drop is small because Turn 1 has no
> history to strip — the system prompt dominates. The compounding savings
> appear from Turn 2 onward as lean history prevents KB blobs from
> accumulating. The retrieval skip saving is structural: 0 DB calls vs 3
> on every greeting, which also removes the ~1,500-char context injection
> from the prompt entirely.
    """)

gold_divider()
st.markdown("<br>", unsafe_allow_html=True)


# SECTION 1 — FILTERS
st.markdown("#### 🔍 Trace Explorer")

f1, f2, f3 = st.columns([1, 1, 2])
with f1:
    window = st.selectbox(
        "Window",
        [1, 7, 14, 30],
        format_func=lambda d: f"Last {d} day{'s' if d > 1 else ''}",
        index=1,
    )
with f2:
    filter_retrieval = st.selectbox(
        "Retrieval",
        ["All turns", "KB queried", "Skipped"],
    )
with f3:
    filter_user = st.text_input("Filter by user (leave blank for all)")

since = datetime.now(timezone.utc) - timedelta(days=window)

# Build MongoDB filter
mongo_filter: dict = {"timestamp": {"$gte": since}}
if filter_retrieval == "KB queried":
    mongo_filter["step_retrieval.ran"] = True
elif filter_retrieval == "Skipped":
    mongo_filter["step_retrieval.ran"] = False
if filter_user.strip():
    mongo_filter["user_id"] = filter_user.strip()

st.markdown("<br>", unsafe_allow_html=True)


# SECTION 2 — SUMMARY METRICS

try:
    db = LeadDB.db

    agg = list(db["behaviour_traces"].aggregate([
        {"$match": mongo_filter},
        {"$group": {
            "_id":             None,
            "total_turns":     {"$sum": 1},
            "total_cost":      {"$sum": "$total_cost_usd"},
            "avg_latency":     {"$avg": "$latency_ms"},
            "avg_input":       {"$avg": "$input_tokens"},
            "avg_output":      {"$avg": "$output_tokens"},
            "retrieval_count": {"$sum": {"$cond": ["$step_retrieval.ran", 1, 0]}},
            "tool_call_turns": {"$sum": {
                "$cond": [{"$gt": [{"$size": "$step_tool_calls"}, 0]}, 1, 0]
            }},
        }},
    ]))
    a = agg[0] if agg else {}

    total_turns = a.get("total_turns", 0)
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Turns in window",       total_turns)
    m2.metric("Total cost",            f"${a.get('total_cost', 0):.5f}")
    m3.metric("Avg latency",           f"{a.get('avg_latency', 0):.0f} ms")
    m4.metric("Avg input tokens",      f"{a.get('avg_input', 0):.0f}")
    m5.metric("Tool-call turns",       a.get("tool_call_turns", 0),
              help="Turns where the agent called a registered tool (vs using pre-fetched context only)")

    gold_divider()
    st.markdown("<br>", unsafe_allow_html=True)

    # SECTION 3 — TRACE LIST

    st.markdown("#### Turn-by-Turn Replay")
    st.caption("Expand any turn to see the full agent behaviour trace.")

    traces = list(
        db["behaviour_traces"]
        .find(mongo_filter)
        .sort("timestamp", -1)
        .limit(50)
    )

    if not traces:
        st.info("No traces found for the selected filters. Traces appear after the next chat turn.")
    else:
        for t in traces:
            ts          = t.get("timestamp")
            ts_str      = ts.strftime("%Y-%m-%d %H:%M:%S") if ts else "—"
            user_msg    = t.get("user_message", "")
            uid         = t.get("user_id", "—")
            cost        = t.get("total_cost_usd", 0)
            latency     = t.get("latency_ms", 0)
            ret         = t.get("step_retrieval", {})
            tool_steps  = t.get("step_tool_calls", [])
            response    = t.get("step_response", {})
            in_tok      = t.get("input_tokens", 0)
            out_tok     = t.get("output_tokens", 0)

            retrieval_badge = "🟢 KB queried" if ret.get("ran") else "⚪ skipped"
            tool_badge      = f"🔧 {len([s for s in tool_steps if s['type']=='call'])} tool call(s)" if tool_steps else "—"

            label = (
                f"**{ts_str}** · 👤 `{uid}` · "
                f"{retrieval_badge} · {tool_badge} · "
                f"${cost:.5f} · {latency} ms"
            )

            with st.expander(label, expanded=False):

                # ── User prompt ───────────────────────────────────────────
                st.markdown("**① User Prompt**")
                is_arabic = any("\u0600" <= c <= "\u06FF" for c in user_msg)
                if is_arabic:
                    st.markdown(
                        f'<div dir="rtl" style="background:rgba(255,255,255,.04);'
                        f'border-radius:8px;padding:.75rem 1rem;'
                        f'font-size:.95rem">{user_msg}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div style="background:rgba(255,255,255,.04);'
                        f'border-radius:8px;padding:.75rem 1rem;'
                        f'font-size:.95rem">{user_msg}</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown("<br>", unsafe_allow_html=True)

                # ── Retrieval step ────────────────────────────────────────
                st.markdown("**② Retrieval**")
                if ret.get("ran"):
                    sources = ret.get("sources", [])
                    ctx_chars = ret.get("context_chars", 0)
                    st.success(
                        f"Knowledge base queried — {ctx_chars:,} chars of context retrieved"
                    )
                    if sources:
                        st.markdown("Sources pulled:")
                        for src in sources:
                            st.markdown(f"- `{src}`")
                    else:
                        st.caption("Source file names not extracted (check pre_context format).")
                else:
                    st.info("QueryRouter skipped retrieval — greeting, farewell, or CRM-only turn.")

                st.markdown("<br>", unsafe_allow_html=True)

                # ── Tool calls ────────────────────────────────────────────
                st.markdown("**③ Tool Calls**")
                calls   = [s for s in tool_steps if s["type"] == "call"]
                results = [s for s in tool_steps if s["type"] == "result"]

                if not calls:
                    st.info("No registered tool calls this turn — agent used pre-fetched context directly.")
                else:
                    for i, call in enumerate(calls):
                        st.markdown(f"**Call {i+1}:** `{call['tool']}`")
                        st.code(call.get("args", ""), language="json")

                        # Match result
                        matching = [r for r in results if r["tool"] == call["tool"]]
                        if matching:
                            r = matching[0]
                            st.markdown(f"↳ **Result** ({r.get('result_length', 0):,} chars):")
                            st.code(r.get("result_preview", ""), language="text")

                st.markdown("<br>", unsafe_allow_html=True)

                # ── Final response ────────────────────────────────────────
                st.markdown("**④ Final Response**")
                resp_text   = response.get("text_preview", "")
                resp_length = response.get("full_length", 0)
                is_ar_resp  = any("\u0600" <= c <= "\u06FF" for c in resp_text)

                if resp_text:
                    direction = "rtl" if is_ar_resp else "ltr"
                    st.markdown(
                        f'<div dir="{direction}" style="background:rgba(245,166,35,.07);'
                        f'border-left:3px solid #F5A623;border-radius:0 8px 8px 0;'
                        f'padding:.75rem 1rem;font-size:.95rem">{resp_text}'
                        f'{"…" if resp_length > 400 else ""}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.warning("Response text not captured — fallback may have fired.")

                st.markdown("<br>", unsafe_allow_html=True)

                # ── Cost & performance ────────────────────────────────────
                st.markdown("**⑤ Cost & Performance**")
                p1, p2, p3, p4 = st.columns(4)
                p1.metric("Input tokens",  f"{in_tok:,}")
                p2.metric("Output tokens", f"{out_tok:,}")
                p3.metric("Turn cost",     f"${cost:.6f}")
                p4.metric("Latency",       f"{latency} ms")

                st.markdown("---")

except Exception as e:
    st.error(f"Could not load traces: {e}")

# ── footer ─────────────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
gold_divider()