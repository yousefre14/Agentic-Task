"""
tools.py — Tool Library for Pydantic AI Agent.

FIXES:
  1. search_available_courses had no query_text param — agent couldn't pass
     the user's actual question through. Added query_text as first param.
  2. Tool functions used positional ctx arg — Pydantic AI requires RunContext
     as first param with correct type annotation.
  3. capture_and_save_crm_lead used 'ticket: CRMLeadTicket' as a single object
     param — Pydantic AI flattens tool params, so each field must be a separate
     named param. Restructured accordingly.
"""

from pydantic_ai import RunContext
from db import KnowledgeBaseDB, LeadDB
from prompts import LEAD_FIELDS


# ════════════════════════════════════════════════════════════════════════════
# TOOL 1 — Course search
# ════════════════════════════════════════════════════════════════════════════

def search_available_courses(ctx: RunContext, query_text: str,
                              track: str = "", level: str = "") -> str:
    """
    Search Kayfa's course catalog by topic, track, or difficulty level.
    Use for questions about specific courses, what's available, or comparing options.

    Args:
        query_text: The user's question or topic of interest (e.g. 'python course for beginners')
        track: Optional domain filter — 'AI', 'cybersecurity', 'web', 'data science'
        level: Optional level filter — 'beginner', 'intermediate', 'advanced'
    """
    result = KnowledgeBaseDB.search_courses(
        query_text=query_text,
        track=track or None,
        level=level or None,
    )
    if not result:
        return "No courses matched this search."
        
    # Append a structural instruction reminder right to the data payload
    return f"{result}\n\n[SYSTEM REMINDER: You must translate/respond to these details completely in the language/dialect the user used.]"

# ════════════════════════════════════════════════════════════════════════════
# TOOL 2 — Diploma / roadmap details
# ════════════════════════════════════════════════════════════════════════════

def get_roadmap_or_diploma_details(ctx: RunContext, structural_name: str) -> str:
    """
    Fetch full curriculum, duration, structure, and outcomes for a diploma or track.
    Use for questions about what a program covers, how long it takes, or its structure.

    Args:
        structural_name: Name of the diploma or track (e.g. 'SOC diploma', 'AI track', 'Full-Stack')
    """
    result = KnowledgeBaseDB.search_roadmaps(structural_name=structural_name)
    return result if result else f"No details found for: '{structural_name}'"


# ════════════════════════════════════════════════════════════════════════════
# TOOL 3 — Policies, prices, sales pitches
# ════════════════════════════════════════════════════════════════════════════

def lookup_policies_and_sales_pitches(ctx: RunContext, user_query: str) -> str:
    """
    Search for pricing, payment options, refund policies, enrollment details,
    certificates, or sales pitch content. Use for ANY question about cost,
    how to register, installments, or company policies.

    Args:
        user_query: The user's full question exactly as asked
                    (e.g. 'how much is the SOC diploma and when does it start')
    """
    result = KnowledgeBaseDB.query_unstructured_kb(user_query, top_n=5)
    return result if result else "Pricing details not available — please connect user with sales team."


# ════════════════════════════════════════════════════════════════════════════
# TOOL 4 — CRM lead capture
# ════════════════════════════════════════════════════════════════════════════

def capture_and_save_crm_lead(
    ctx: RunContext,
    name: str,
    contact: str,
    products_interested: str,
    goal: str,
    lead_temperature: str,
    buying_signals: str,
    conversation_summary: str,
    recommended_action: str,
    city_country: str = "غير محدد",
    language_dialect: str = "العربية",
    current_level: str = "مبتدئ",
    objections: str = "",
) -> str:
    """
    Silently save a qualified lead as a CRM ticket in MongoDB.
    Call this ONLY when both the user's name AND contact info (WhatsApp/email)
    are confirmed in the conversation. Do not announce this call to the user.

    Args:
        name: Full name as stated by the user
        contact: WhatsApp number with country code or email address
        products_interested: Comma-separated diplomas or courses they showed interest in
        goal: Their career goal or learning motivation
        lead_temperature: 'hot', 'warm', or 'cold'
        buying_signals: Comma-separated signals observed (e.g. 'asked about price, installments')
        conversation_summary: 2-3 sentence Arabic summary of the full conversation
        recommended_action: Next action the sales rep should take
        city_country: User's city and country (default: غير محدد)
        language_dialect: Detected dialect (default: العربية)
        current_level: Technical level — beginner/intermediate/advanced
        objections: Any concerns or objections raised (optional)
    """
    try:
        ticket = {
            "name":                 name,
            "contact":              contact,
            "city_country":         city_country,
            "language_dialect":     language_dialect,
            "products_interested":  [p.strip() for p in products_interested.split(",")],
            "goal":                 goal,
            "current_level":        current_level,
            "lead_temperature":     lead_temperature,
            "buying_signals":       [s.strip() for s in buying_signals.split(",")],
            "objections":           [o.strip() for o in objections.split(",")] if objections else [],
            "conversation_summary": conversation_summary,
            "recommended_action":   recommended_action,
        }
        inserted_id = LeadDB.create_ticket(ticket)
        print(f"[CRM] ✅ Lead saved: {name} | {contact} | ID: {inserted_id}")
        return f"SUCCESS: Lead recorded — ID {inserted_id}"
    except Exception as e:
        print(f"[CRM] ❌ Failed to save lead: {e}")
        return f"FAILURE: {str(e)}"