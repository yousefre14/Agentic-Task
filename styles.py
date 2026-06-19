"""
styles.py — Kayfa AI Sales Agent · Global Design System
=========================================================
Dark glassmorphism theme · Midnight blue + Kayfa gold
Logo top-right on every page · Full RTL Arabic support
"""

import streamlit as st
from PIL import Image
import base64, os

# ── brand tokens ─────────────────────────────────────────────────────────────
BRAND = {
    "bg_deep":      "#080B18",
    "bg_surface":   "#0E1225",
    "bg_card":      "rgba(255,255,255,0.035)",
    "border":       "rgba(255,255,255,0.07)",
    "gold":         "#F5A623",
    "gold_hover":   "#FFD166",
    "text":         "#F1F5F9",
    "muted":        "#64748B",
}

# ── logo loaders ──────────────────────────────────────────────────────────────
@st.cache_data
def _load(path: str):
    for p in [path, os.path.basename(path)]:
        try:
            return Image.open(p)
        except Exception:
            pass
    return None

@st.cache_data
def _b64(path: str) -> str:
    """Return base64 data-URI for an image so we can use it in HTML."""
    for p in [path, os.path.basename(path)]:
        try:
            with open(p, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            ext = p.rsplit(".", 1)[-1].lower()
            mime = "image/png" if ext == "png" else "image/jpeg"
            return f"data:{mime};base64,{data}"
        except Exception:
            pass
    return ""

logo1_img  = _load("logos/logo1.png")
logo2_img  = _load("logos/company_logo2.png")
logo1_b64  = _b64("logos/logo1.png")
logo2_b64  = _b64("logos/company_logo2.png")

# ── global CSS ────────────────────────────────────────────────────────────────
GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700;800&family=Inter:wght@300;400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/embed2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

/* ── base ──────────────────────────────────────────────────────────────── */
html, body, .stApp {
    background: #080B18 !important;
    color: #F1F5F9 !important;
    font-family: 'Inter', 'Cairo', system-ui, sans-serif !important;
}
#MainMenu, footer, header { visibility: hidden !important; }
.block-container { padding-top: 2rem !important; max-width: 1200px !important; }
[data-testid="stSidebarNav"] { display: none !important; }

/* ── webkit-icon fix & typography adjustments ──────────────────────────── */
.material-symbols-outlined {
    font-family: 'Material Symbols Outlined' !important;
    font-weight: normal;
    font-style: normal;
    font-size: 24px;
    line-height: 1;
    letter-spacing: normal;
    text-transform: none;
    display: inline-block;
    white-space: nowrap;
    word-wrap: normal;
    direction: ltr;
    -webkit-font-smoothing: antialiased;
}

::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #080B18; }
::-webkit-scrollbar-thumb { background: rgba(245,166,35,.25); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #F5A623; }

h1,h2,h3,h4,h5,h6,label {
    font-family: 'Inter','Cairo',system-ui,sans-serif !important;
}
h1 { font-size: 1.8rem !important; font-weight: 700 !important; color: #F1F5F9 !important; }
h2 { font-size: 1.4rem !important; font-weight: 600 !important; color: #F1F5F9 !important; }
h3 { font-size: 1.15rem  !important; font-weight: 600 !important; color: #F1F5F9 !important; }

/* ── sidebar ───────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: #05070F !important;
    border-right: 1px solid rgba(255,255,255,.06) !important;
}

/* ── glass card ────────────────────────────────────────────────────────── */
.k-card {
    background: rgba(255,255,255,.03);
    border: 1px solid rgba(255,255,255,.06);
    border-radius: 14px;
    padding: 1.5rem;
    backdrop-filter: blur(12px);
    margin-bottom: 1rem;
}

/* ── logo top-right bar ─────────────────────────────────────────────────── */
.k-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 2rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid rgba(255,255,255,.08);
}
.k-topbar-title { font-size: 1.5rem; font-weight: 700; color: #F1F5F9; letter-spacing: -0.02em; }
.k-topbar-logo img { height: 40px; display: block; }

/* ── gold divider ───────────────────────────────────────────────────────── */
.k-divider {
    height: 1px;
    background: linear-gradient(90deg, #F5A623, transparent);
    border: none;
    margin: 1.25rem 0;
}

/* ── premium custom buttons ──────────────────────────────────────────────── */
.stButton > button {
    font-family: 'Inter','Cairo',sans-serif !important;
    border-radius: 8px !important;
    transition: all .2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    padding: 0.5rem 1.2rem !important;
}
.stButton > button[kind="primary"] {
    background: #F5A623 !important;
    color: #080B18 !important;
    font-weight: 700 !important;
    border: none !important;
    box-shadow: 0 4px 12px rgba(245,166,35,.2) !important;
}
.stButton > button[kind="primary"]:hover {
    background: #FFD166 !important;
    box-shadow: 0 6px 20px rgba(245,166,35,.35) !important;
    transform: translateY(-1px);
}
.stButton > button:not([kind="primary"]) {
    border: 1px solid rgba(255,255,255,.1) !important;
    background: rgba(255,255,255,.02) !important;
    color: #F1F5F9 !important;
}
.stButton > button:not([kind="primary"]):hover {
    border-color: #F5A623 !important;
    background: rgba(245,166,35,.05) !important;
    color: #F5A623 !important;
}

/* ── inputs ─────────────────────────────────────────────────────────────── */
.stTextInput input, .stTextArea textarea, [data-baseweb="input"] input {
    background: rgba(0,0,0,.25) !important;
    border: 1px solid rgba(255,255,255,.08) !important;
    border-radius: 8px !important;
    color: #F1F5F9 !important;
}

/* ── chat styling overrides ──────────────────────────────────────────────── */
[data-testid="stChatMessage"] {
    background: rgba(255,255,255,.02) !important;
    border: 1px solid rgba(255,255,255,.05) !important;
    border-radius: 12px !important;
}

/* ── RTL arabic ─────────────────────────────────────────────────────────── */
[dir="rtl"], div[lang="ar"] {
    direction: rtl !important;
    text-align: right !important;
    font-family: 'Cairo','Segoe UI',sans-serif !important;
}

/* ── custom metric adjustments ──────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: rgba(255,255,255,.02) !important;
    border: 1px solid rgba(255,255,255,.05) !important;
    border-radius: 12px !important;
}

/* ── custom option menu layout wrapper ─────────────────────────────────────── */
.option-box {
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 2rem;
    text-align: center;
    background: rgba(255,255,255,0.02);
    cursor: pointer;
    transition: transform 0.2s ease, border-color 0.2s ease;
}
.option-box:hover {
    border-color: #F5A623;
    transform: translateY(-2px);
}
</style>
"""

# ════════════════════════════════════════════════════════════════════════════
# PUBLIC API — call these from every page
# ════════════════════════════════════════════════════════════════════════════

def inject_theme():
    """Inject global CSS. Call at the very top of every page."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def render_topbar(title: str, subtitle: str = ""):
    """
    Renders a top bar with title on the left and Kayfa logo on the right.
    Call after inject_theme() on every page.
    """
    logo_html = ""
    if logo1_b64:
        logo_html = f'<img src="{logo1_b64}" style="height:38px;object-fit:contain;" alt="Kayfa logo">'
    elif logo2_b64:
        logo_html = f'<img src="{logo2_b64}" style="height:38px;object-fit:contain;" alt="Kayfa logo">'
    else:
        logo_html = '<span style="color:#F5A623;font-weight:700;font-size:1.2rem">كيف · Kayfa</span>'

    st.markdown(f"""
    <div class="k-topbar">
        <div>
            <div class="k-topbar-title">{title}</div>
            {"<div style='font-size:.85rem;color:#64748B;margin-top:4px'>" + subtitle + "</div>" if subtitle else ""}
        </div>
        <div class="k-topbar-logo">{logo_html}</div>
    </div>
    """, unsafe_allow_html=True)


def gold_divider():
    st.markdown('<div class="k-divider"></div>', unsafe_allow_html=True)


def render_sidebar_logo():
    """Put logo at the top of the sidebar cleanly."""
    with st.sidebar:
        if logo2_img:
            st.image(logo2_img, width=230)
        elif logo1_img:
            st.image(logo1_img, width=230)
        else:
            st.markdown("<h3 style='color:#F5A623;'>كيف · Kayfa</h3>", unsafe_allow_html=True)