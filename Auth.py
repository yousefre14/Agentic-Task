"""
Auth.py 
"""
import streamlit as st
from styles import inject_theme, logo1_b64, logo2_b64

CREDENTIALS = {
    "visitor_demo": {"password":"admin","name":"Demo Visitor","role":"visitor"},
    "sales_rep":    {"password":"admin","name":"Sales Team",  "role":"sales_rep"},
    "admin":        {"password":"admin","name":"Admin",       "role":"admin"},
}

def render_login_page():
    if st.session_state.get("authentication_status"):
        return True, st.session_state.get("name"), st.session_state.get("username")

    inject_theme()

    logo_src  = logo1_b64 or logo2_b64
    logo_html = (
        f'<img src="{logo_src}" style="height:80px; object-fit:contain; '
        f'background:transparent; display:block; margin:0 auto 1rem;" alt="Kayfa">'
        if logo_src else
        '<div style="font-size:2.2rem; font-weight:800; color:#F5A623; margin-bottom:1rem; text-align:center;">كيف</div>'
    )

    # Centered column layout for a premium web app feel
    _, col, _ = st.columns([1, 1.8, 1])
    with col:
        # Unified Header Block
        st.markdown(f"""
        <div style="text-align:center; margin:4rem 0 2rem 0;">
            {logo_html}
            <div style="font-size:1.6rem; font-weight:700; color:#F1F5F9; letter-spacing:-0.025em;">Kayfa AI Portal</div>
            <div style="font-size:0.875rem; color:#64748B; margin-top:0.35rem; font-weight:400;">
                Agentic AI Sales Assistant &middot; Week 3
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Login Card Container
        with st.container():
            with st.form("login_form"):
                username_input = st.text_input("Username", placeholder="e.g. visitor_demo").strip()
                password_input = st.text_input("Password", type="password", placeholder="••••••").strip()
                
                st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)
                submit = st.form_submit_button(
                    "Sign in →", width="stretch", type="primary"
                )

            if submit:
                if not username_input:
                    st.error("⚠️ Username is required.")
                elif not password_input:
                    st.error("⚠️ Password is required.")
                elif username_input in CREDENTIALS and CREDENTIALS[username_input]["password"] == password_input:
                    info = CREDENTIALS[username_input]
                    st.session_state["authentication_status"] = True
                    st.session_state["username"] = username_input
                    st.session_state["name"]     = info["name"]
                    st.session_state["role"]     = info["role"]
                    st.rerun()
                else:
                    st.error("❌ Incorrect username or password.")
                    st.session_state["authentication_status"] = False

        # Cleaned up demo credentials layout to avoid standard overlapping expanders
        st.markdown('<div style="margin-top: 1.5rem;"></div>', unsafe_allow_html=True)
    

    return (
        st.session_state.get("authentication_status"),
        st.session_state.get("name"),
        st.session_state.get("username"),
    )

def get_user_role():
    return st.session_state.get("role", "visitor")

def get_authenticator():
    class _Logout:
        def logout(self, label="Logout", location="main", key=None):
            # Default to main page button to avoid crowding sidebars
            btn = st.sidebar.button(label, key=key) if location == "sidebar" else st.button(label, key=key)
            if btn:
                st.session_state.clear()
                st.rerun()
    return _Logout()