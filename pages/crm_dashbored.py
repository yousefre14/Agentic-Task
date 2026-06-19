"""
pages/crm_dashboard.py — Kayfa CRM Lead Management Dashboard
Layout: metrics row → filter bar → leads table + detail panel (side by side)
Auth:   sales_rep and admin only
"""

import streamlit as st
import pandas as pd
from db import LeadDB
from Auth import get_user_role
from styles import inject_theme, render_topbar, gold_divider, render_sidebar_logo

# ── auth guard ────────────────────────────────────────────────────────────────
if not st.session_state.get("authentication_status"):
    st.warning("⚠️ Please log in first.")
    st.stop()

if get_user_role() not in ("sales_rep", "admin"):
    st.error("❌ Access denied — sales team authorization required.")
    st.stop()

# ── Theme & Premium Custom Adjustments ────────────────────────────────────────
inject_theme()

st.markdown("""
<style>
[data-testid="stSidebarNav"] { display: none !important; }

/* Refined Premium Badges */
.badge {
    display: inline-block;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 12px;
    letter-spacing: .02em;
    margin: 2px;
}
.hot  { background: rgba(245, 166, 35, 0.15); color: #FFD166; border: 1px solid rgba(245, 166, 35, 0.3); }
.warm { background: rgba(100, 116, 139, 0.15); color: #E2E8F0; border: 1px solid rgba(100, 116, 139, 0.3); }
.cold { background: rgba(255, 255, 255, 0.03); color: #64748B; border: 1px solid rgba(255, 255, 255, 0.05); }

/* Status Indicators */
.s-new       { background: rgba(59, 130, 246, 0.15); color: #60A5FA; }
.s-contacted { background: rgba(245, 166, 35, 0.15); color: #F5A623; }
.s-converted { background: rgba(16, 185, 129, 0.15); color: #34D399; }
.s-lost      { background: rgba(239, 68, 68, 0.15); color: #F87171; }

/* Custom Action Detail Panels matching styles.py specifications */
.rtl-block {
    direction: rtl;
    text-align: right;
    background: rgba(255, 255, 255, 0.02);
    border-radius: 10px;
    padding: 14px;
    font-size: 0.92rem;
    line-height: 1.75;
    border-right: 3px solid #64748B;
    font-family: 'Cairo', sans-serif;
}
.action-block {
    direction: rtl;
    text-align: right;
    background: rgba(245, 166, 35, 0.04);
    border-radius: 10px;
    padding: 14px;
    font-size: 0.92rem;
    color: #FFD166;
    line-height: 1.75;
    border-right: 3px solid #F5A623;
    font-family: 'Cairo', sans-serif;
}

/* Rounded Profile Monograms */
.avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 40px; height: 40px;
    border-radius: 50%;
    font-size: 14px;
    font-weight: 700;
    flex-shrink: 0;
}
</style>
""", unsafe_allow_html=True)

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar_logo()
    st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)
    st.divider()
    st.markdown(f"👤 Operational View: **{st.session_state.get('name','')}**")
    st.caption("Access Clear: `SALES CONTROL`")
    st.divider()
    if st.button("💬 Launch Chat Agent", use_container_width=True, type="primary"):
        st.switch_page("pages/chat_agent.py")
    if st.button("🔄 Sync Live Pipeline", use_container_width=True):
        st.rerun()

# ── load data ─────────────────────────────────────────────────────────────────
try:
    all_tickets = LeadDB.get_all_tickets(limit=200)
except Exception as e:
    st.error(f"Database sync failed: {e}")
    all_tickets = []

# ── header + metrics ──────────────────────────────────────────────────────────
render_topbar(
    "🎯 Kayfa Enrollment Analytics",
    "Qualified Pipeline Leads & Unstructured Conversational Insights Hub"
)
gold_divider()

total     = len(all_tickets)
hot_count = sum(1 for t in all_tickets if t.get("lead_temperature","").lower() == "hot")
warm_count= sum(1 for t in all_tickets if t.get("lead_temperature","").lower() == "warm")
conv_count= sum(1 for t in all_tickets if t.get("status","").lower() == "converted")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Captured Leads",  total)
c2.metric("Hot Signals 🔥",       hot_count)
c3.metric("Warm Prospects",         warm_count)
c4.metric("Conversions ✅", conv_count)

st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)

if not all_tickets:
    st.info("No lead files generated yet. Active chat interactions stream pipeline profiles here.")
    st.stop()

# ── tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["🔥 Active Leads Pipeline", "📈 Funnel Distribution Profile"])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — LEADS PIPELINE WORKSPACE
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    # ── filters ───────────────────────────────────────────────────────────
    f1, f2, f3 = st.columns([2, 2, 2])
    with f1:
        temp_filter = st.multiselect("Filter Temperature", ["hot","warm","cold"], default=["hot","warm"])
    with f2:
        status_filter = st.multiselect("Pipeline Status", ["new","contacted","converted","lost"], default=["new","contacted"])
    with f3:
        sort_by = st.selectbox("Pipeline Hierarchy", ["Most recent","Hottest first"])

    # ── apply filters ─────────────────────────────────────────────────────
    filtered = [
        t for t in all_tickets
        if t.get("lead_temperature","warm").lower() in temp_filter
        and t.get("status","new").lower() in status_filter
    ]

    priority = {"hot": 3, "warm": 2, "cold": 1}
    if sort_by == "Hottest first":
        filtered.sort(key=lambda x: priority.get(x.get("lead_temperature","warm").lower(), 0), reverse=True)
    else:
        filtered.sort(key=lambda x: str(x.get("created_at", x.get("_id",""))), reverse=True)

    if not filtered:
        st.info("No active profiles match the selected filtering combinations.")
        st.stop()

    st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)

    # ── premium two-column workspace framework ────────────────────────────
    left, right = st.columns([2.2, 2], gap="large")

    with left:
        st.markdown(f"### Live Records ({len(filtered)})")
        
        # Build Selection Action List
        options = {
            f"👤 {t.get('name','?')} ({t.get('lead_temperature','').upper()})": t
            for t in filtered
        }
        selected_key = st.radio(
            "Select Record Target Profile",
            options=list(options.keys()),
            label_visibility="visible",
        )
        selected = options[selected_key]

        st.markdown('<div style="margin-top: 1.5rem;"></div>', unsafe_allow_html=True)
        
        # Grid View Presentation Matrix
        df_rows = []
        for t in filtered:
            temp  = t.get("lead_temperature","warm").lower()
            stat  = t.get("status","new").lower()
            prods = t.get("products_interested",[])
            if isinstance(prods, list):
                prods = ", ".join(prods)
            df_rows.append({
                "Prospect Name": t.get("name","N/A"),
                "Priority":      temp.upper(),
                "Pipeline Phase": stat.upper(),
                "Program Interest": prods or "N/A",
            })

        st.dataframe(pd.DataFrame(df_rows), use_container_width=True, hide_index=True)

    with right:
        st.markdown("### Profile Inspector")
        lead = selected
        name    = lead.get("name","?")
        initials= "".join(w[0].upper() for w in name.split()[:2]) if name else "??"
        temp    = lead.get("lead_temperature","warm").lower()
        status  = lead.get("status","new").lower()

        # Dynamic Avatar System matching UI styling theme
        av_bg, av_fg = ("#F5A623", "#080B18") if temp == "hot" else ("rgba(255,255,255,0.05)", "#F1F5F9")

        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:16px; margin-bottom:1.5rem; background:rgba(255,255,255,0.02); padding:1rem; border-radius:12px; border:1px solid rgba(255,255,255,0.05);">
            <div class="avatar" style="background:{av_bg}; color:{av_fg};">{initials}</div>
            <div>
                <div style="font-size:1.1rem; font-weight:700; color:#F1F5F9;">{name}</div>
                <div style="font-size:0.85rem; color:#64748B; margin-top:2px;">{lead.get('contact', lead.get('phone','N/A'))}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Profile Parameter Grid Details
        prods = lead.get("products_interested",[])
        if isinstance(prods, list): prods = ", ".join(prods)

        info = {
            "📍 Core Location": lead.get("city_country", lead.get("city","N/A")),
            "🗣 Language Dialect": lead.get("language_dialect", lead.get("dialect","Arabic")),
            "📊 Current Domain Experience": lead.get("current_level","N/A"),
            "🎓 Track Objectives": prods or "N/A",
            "🌡 Target Temperature": temp.upper(),
        }
        
        for k, v in info.items():
            ck, cv = st.columns([1.2, 2])
            ck.caption(k)
            cv.markdown(f"<span style='font-size:0.9rem; color:#E2E8F0;'>{v}</span>", unsafe_allow_html=True)

        # Buying Flags Layout Configuration
        st.markdown('<div style="margin-top: 1.5rem;"></div>', unsafe_allow_html=True)
        signals = lead.get("buying_signals",[])
        if isinstance(signals, str): signals = [signals]
        if signals:
            st.markdown("🗣 **Buying Signals Tracked**")
            st.markdown(" ".join(f'<span class="badge s-new">{s}</span>' for s in signals), unsafe_allow_html=True)

        # Conversational Intelligence Breakdown
        st.markdown('<div style="margin-top: 1.5rem;"></div>', unsafe_allow_html=True)
        st.markdown("📝 **Automated Session Summary**")
        summary = lead.get("conversation_summary", lead.get("conversation_link","N/A"))
        st.markdown(f'<div class="rtl-block">{summary}</div>', unsafe_allow_html=True)

        # Recommended Action
        st.markdown('<div style="margin-top: 1.25rem;"></div>', unsafe_allow_html=True)
        st.markdown("⚡ **AI Recommended Next Step**")
        action = lead.get("recommended_action", lead.get("next_action", "يتواصل أحد مندوبي المبيعات لمتابعة التسجيل"))
        st.markdown(f'<div class="action-block">{action}</div>', unsafe_allow_html=True)

        # Pipeline Write-Back Management Frame
        st.divider()
        st.markdown("### Update Core Record Pipeline")
        status_opts = ["new","contacted","converted","lost"]
        new_status  = st.selectbox(
            "Modify Stage Clearances",
            status_opts,
            index=status_opts.index(status) if status in status_opts else 0,
            key=f"status_{lead['_id']}"
        )
        note = st.text_area(
            "Operational Field Interactions Log",
            placeholder="e.g., Connected over call. Student requested premium installment structure setup...",
            height=90,
            key=f"note_{lead['_id']}"
        )
        if st.button("Commit Phase Update Changes ✅", use_container_width=True, key=f"commit_{lead['_id']}", type="primary"):
            try:
                LeadDB.update_ticket_status(
                    ticket_id=str(lead["_id"]),
                    status=new_status,
                    notes=note,
                )
                st.success("Pipeline matrix records synced successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Pipeline write sync anomaly: {e}")

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — METRIC AND CONVERSION FUNNEL ANALYTICS
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### Structural Metrics & Stream Funnels")

    a1, a2 = st.columns(2, gap="large")

    with a1:
        st.markdown("📊 **Lead Volume by Temperature Matrix**")
        temp_counts = {"hot": 0, "warm": 0, "cold": 0}
        for t in all_tickets:
            k = t.get("lead_temperature","warm").lower()
            if k in temp_counts:
                temp_counts[k] += 1
        st.bar_chart(pd.DataFrame.from_dict(temp_counts, orient="index", columns=["leads"]))

    with a2:
        st.markdown("📈 **Conversion Phases State Metrics**")
        status_counts = {"new": 0, "contacted": 0, "converted": 0, "lost": 0}
        for t in all_tickets:
            k = t.get("status","new").lower()
            if k in status_counts:
                status_counts[k] += 1
        st.bar_chart(pd.DataFrame.from_dict(status_counts, orient="index", columns=["leads"]))

    st.divider()
    st.markdown("### Top Educational tracks of Interest")
    prog_counts: dict = {}
    for t in all_tickets:
        prods = t.get("products_interested",[])
        if isinstance(prods, str):
            prods = [prods]
        for p in prods:
            p = p.strip()
            if p:
                prog_counts[p] = prog_counts.get(p, 0) + 1

    if prog_counts:
        df_prog = (
            pd.DataFrame.from_dict(prog_counts, orient="index", columns=["leads"])
            .sort_values("leads", ascending=False)
            .head(8)
        )
        st.bar_chart(df_prog)
    else:
        st.caption("No product distribution metrics extracted yet.")