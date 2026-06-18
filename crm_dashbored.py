"""
pages/crm_dashboard.py — Sales Team Dashboard

STRUCTURE:
1. Auth (sales_rep only)
2. Show all CRM tickets
3. Filter & sort
4. View full ticket details (in Arabic)
5. Update ticket status
6. Export reports
"""

import streamlit as st
import pandas as pd
from db import LeadDB
from Auth import check_authentication, get_user_role, load_authenticator

st.set_page_config(
    page_title="CRM Dashboard | Kayfa",
    page_icon="📊",
    layout="wide"
)

# ==================== AUTHENTICATION ====================
auth_status, name, username = check_authentication()

if not auth_status:
    st.warning("Please log in")
    st.stop()

user_role = get_user_role()
if user_role != 'sales_rep':
    st.error("❌ Access denied. This dashboard is for sales team only.")
    st.stop()

# ==================== SIDEBAR ====================
with st.sidebar:
    st.markdown("## 📊 CRM Dashboard")
    authenticator = load_authenticator()
    if st.button("🚪 Logout"):
        authenticator.logout('Logout', 'unrendered')
        st.session_state.clear()
        st.rerun()

# ==================== MAIN DASHBOARD ====================
st.title("🎯 Kayfa Sales — Lead Management")
st.markdown("---")

# Tabs
tab1, tab2, tab3 = st.tabs(["🔥 Leads", "📈 Analytics", "⚙️ Settings"])

with tab1:
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        temp_filter = st.multiselect(
            "Lead Temperature",
            options=['hot', 'warm', 'cold'],
            default=['hot', 'warm']
        )
    
    with col2:
        status_filter = st.multiselect(
            "Status",
            options=['new', 'contacted', 'converted', 'lost'],
            default=['new', 'contacted']
        )
    
    with col3:
        sort_by = st.selectbox(
            "Sort By",
            options=['Most Recent', 'Oldest', 'Hottest']
        )
    
    st.markdown("---")
    
    # Load tickets
    all_tickets = LeadDB.get_all_tickets(limit=100)
    
    # Filter
    filtered_tickets = [
        t for t in all_tickets
        if t.get('lead_temperature') in temp_filter and
        t.get('status', 'new') in status_filter
    ]
    
    # Display as table
    if filtered_tickets:
        # Convert to DataFrame for display
        df_data = []
        for ticket in filtered_tickets:
            df_data.append({
                'Name': ticket.get('name', 'N/A'),
                'Email': ticket.get('email', 'N/A'),
                'Phone': ticket.get('phone', 'N/A'),
                'Temperature': ticket.get('lead_temperature', 'cold'),
                'Status': ticket.get('status', 'new'),
                'Created': ticket.get('created_at', 'N/A'),
                'ID': str(ticket['_id'])
            })
        
        df = pd.DataFrame(df_data)
        
        st.dataframe(df, use_container_width=True)
        
        st.markdown("---")
        
        # Detailed view
        st.subheader("📋 Full Ticket Details")
        selected_id = st.selectbox(
            "Select a lead",
            options=[f"{t['Name']} ({t['Email']})" for t in df_data]
        )
        
        if selected_id:
            # Get full ticket
            ticket = next(
                (t for t in filtered_tickets if t.get('name') in selected_id),
                None
            )
            
            if ticket:
                st.markdown(f"""
                ### {ticket.get('name')}
                
                **Contact Info:**
                - Email: {ticket.get('email')}
                - Phone: {ticket.get('phone')}
                - City: {ticket.get('city')}, {ticket.get('country')}
                - Language: {ticket.get('language')} ({ticket.get('dialect')})
                
                **Interest:**
                - Lead Temp: 🔥 {ticket.get('lead_temperature')}
                - Status: {ticket.get('status')}
                - Signals: {', '.join(ticket.get('buying_signals', []))}
                
                **Conversation Summary:**
                {ticket.get('conversation_summary', 'N/A')}
                
                **Created:** {ticket.get('created_at')}
                """)
                
                # Update status
                new_status = st.selectbox(
                    "Update Status",
                    options=['new', 'contacted', 'converted', 'lost']
                )
                
                if st.button("Save Status"):
                    LeadDB.update_ticket_status(
                        ticket_id=str(ticket['_id']),
                        status=new_status
                    )
                    st.success("✅ Updated!")
                    st.rerun()
    
    else:
        st.info("No leads matching your filters.")

with tab2:
    st.subheader("📈 Analytics")
    
    all_tickets = LeadDB.get_all_tickets(limit=1000)
    
    if all_tickets:
        # Temperature distribution
        temps = {}
        for t in all_tickets:
            temp = t.get('lead_temperature', 'cold')
            temps[temp] = temps.get(temp, 0) + 1
        
        st.bar_chart(temps)
        
        # Status distribution
        statuses = {}
        for t in all_tickets:
            status = t.get('status', 'new')
            statuses[status] = statuses.get(status, 0) + 1
        
        st.pie_chart(statuses)

with tab3:
    st.subheader("⚙️ Settings")
    st.info("Admin settings coming soon...")