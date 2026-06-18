"""
Centralizing auth logic keeps it DRY and reusable across pages.
     We handle password hashing, session validation, and role-based access here.
"""

import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import os

def load_authenticator():
    """Load authenticator once per session."""
    with open('config.yaml') as f:
        config = yaml.load(f, Loader=SafeLoader)
    
    return stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
    )

def check_authentication():
    """
    Check if user is logged in.
    
    HOW: 
    1. Load authenticator from cache
    2. Check session_state for auth status
    3. Return True/False + user info
    
    WHY: Prevents code duplication. One function for all auth checks.
    """
    authenticator = load_authenticator()
    
    # If not yet authenticated, show login
    if st.session_state.get('authentication_status') is None:
         authenticator.login(location="main")
    
    return (
        st.session_state.get('authentication_status'),
        st.session_state.get('name'),
        st.session_state.get('username')
    )

def logout_user(authenticator):
    """Handle logout with cleanup."""
    authenticator.logout('Logout', 'sidebar', key='logout_unique')
    st.rerun()

def get_user_role():
    """Return the logged-in user's role (visitor or sales_rep)."""
    with open('config.yaml') as f:
        config = yaml.load(f, Loader=SafeLoader)
    
    username = st.session_state.get('username')
    if username and username in config['credentials']['usernames']:
        return config['credentials']['usernames'][username].get('role', 'visitor')
    return 'visitor'