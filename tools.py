"""
tools.py — Tool Library for Pydantic AI Agent.
  - EmbeddingCache: uses semantic_search.get_embedding_model() 
  - QueryRouter: skip retrieval for greetings/trivial turns
  - Contact validation on CRM capture
"""

import asyncio
import hashlib
import time
from typing import Optional
import re as _re

import numpy as np
from pydantic_ai import RunContext
from prompts import LEAD_FIELDS
from semantic_search import get_embedding_model



# ── EMBEDDING CACHE

class EmbeddingCache:
    """
    Two-layer embedding cache:
      L1 — in-process dict  (zero latency, lost on restart)
      L2 — MongoDB Atlas    (persists across restarts; optional)
    """

    _l1: dict = {}
    _MAX_L1 = 2048

    @classmethod
    def _get_model(cls):
        return get_embedding_model()

    @classmethod
    def encode(cls, text: str) -> np.ndarray:
        key = hashlib.sha256(text.strip().lower().encode()).hexdigest()

        # L1 hit
        if key in cls._l1:
            return cls._l1[key]

        # L2 hit (MongoDB)
        cached = cls._try_mongo_get(key)
        if cached is not None:
            cls._l1_set(key, cached)
            return cached

        # Miss — encode via shared model
        vec = cls._get_model().encode(text, normalize_embeddings=True)
        cls._l1_set(key, vec)
        cls._try_mongo_set(key, vec)
        return vec

    @classmethod
    def _l1_set(cls, key: str, vec: np.ndarray):
        if len(cls._l1) >= cls._MAX_L1:
            cls._l1.pop(next(iter(cls._l1)))
        cls._l1[key] = vec

    @classmethod
    def _try_mongo_get(cls, key: str) -> Optional[np.ndarray]:
        try:
            from db import LeadDB
            doc = LeadDB.db["embedding_cache"].find_one({"_id": key})
            if doc:
                return np.array(doc["vec"], dtype=np.float32)
        except Exception:
            pass
        return None

    @classmethod
    def _try_mongo_set(cls, key: str, vec: np.ndarray):
        try:
            from db import LeadDB
            LeadDB.db["embedding_cache"].update_one(
                {"_id": key},
                {"$set": {"vec": vec.tolist(), "ts": int(time.time())}},
                upsert=True,
            )
        except Exception:
            pass


# ── SEMANTIC DEDUPLICATION 
def deduplicate_chunks(chunks: list[str], threshold: float = 0.92) -> list[str]:
    """
    Remove near-duplicate strings from a list using cosine similarity.
    """
    if len(chunks) <= 1:
        return chunks

    vecs = np.array([EmbeddingCache.encode(c) for c in chunks])
    kept_indices = [0]

    for i in range(1, len(vecs)):
        kept_vecs = vecs[kept_indices]
        sims = kept_vecs @ vecs[i]
        if sims.max() < threshold:
            kept_indices.append(i)

    return [chunks[i] for i in kept_indices]


# ── QUERY ROUTER ──────────────────────────────────────────────────────────────

_SKIP_PATTERNS = [
    "مرحبا", "أهلاً", "السلام", "هاي", "هلا", "hello", "hi", "hey",
    "اسمي", "رقمي", "ايميلي", "my name is", "my number is", "my email is",
    "شكرا", "وداعاً", "bye", "thanks",
]

class QueryRouter:
    @staticmethod
    def should_skip_retrieval(user_message: str) -> bool:
        msg = user_message.strip().lower()
        if len(msg) < 12:
            return True
        if any(pat in msg for pat in _SKIP_PATTERNS):
            return True
        return False


# ── TOOL 1 — Course search ────────────────────────────────────────────────────

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
    from db import KnowledgeBaseDB
    result = KnowledgeBaseDB.search_courses(
        query_text=query_text,
        track=track or None,
        level=level or None,
    )
    if not result:
        return "No courses matched this search."
    return f"{result}\n\n[SYSTEM REMINDER: Respond entirely in the language/dialect the user used.]"


# ── TOOL 2 — Diploma / roadmap details ───────────────────────────────────────

def get_roadmap_or_diploma_details(ctx: RunContext, structural_name: str) -> str:
    """
    Fetch full curriculum, duration, structure, and outcomes for a diploma or track.
    Use for questions about what a program covers, how long it takes, or its structure.

    Args:
        structural_name: Name of the diploma or track (e.g. 'SOC diploma', 'AI track', 'Full-Stack')
    """
    from db import KnowledgeBaseDB
    result = KnowledgeBaseDB.search_roadmaps(structural_name=structural_name)
    return result if result else f"No details found for: '{structural_name}'"


# ── TOOL 3 — Policies, prices, sales pitches ─────────────────────────────────

def lookup_policies_and_sales_pitches(ctx: RunContext, user_query: str) -> str:
    """
    Search for pricing, payment options, refund policies, enrollment details,
    certificates, or sales pitch content. Use for ANY question about cost,
    how to register, installments, or company policies.

    Args:
        user_query: The user's full question exactly as asked
                    (e.g. 'how much is the SOC diploma and when does it start')
    """
    from db import KnowledgeBaseDB
    result = KnowledgeBaseDB.query_unstructured_kb(user_query, top_n=5)
    return result if result else "Pricing details not available — please connect user with sales team."


# ── TOOL 4 — CRM lead capture ────────────────────────────────────────────────

_VALID_EMAIL_RE = _re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)
_VALID_PHONE_PATTERNS = [
    _re.compile(r"^(\+20|0020|0)?1[0125]\d{8}$"),     # Egypt
    _re.compile(r"^(\+966|00966|0)?5\d{8}$"),          # Saudi
    _re.compile(r"^(\+971|00971|0)?5[024568]\d{7}$"),  # UAE
    _re.compile(r"^(\+962|00962|0)?7[789]\d{7}$"),     # Jordan
    _re.compile(r"^(\+963|00963|0)?9[0-9]\d{7}$"),     # Syria
    _re.compile(r"^(\+961|00961|0)?[37]\d{7}$"),       # Lebanon
    _re.compile(r"^(\+965|00965)?[569]\d{7}$"),        # Kuwait
]

def _validate_contact(contact: str) -> tuple[bool, str]:
    contact = contact.strip()
    if "@" in contact:
        if _VALID_EMAIL_RE.match(contact):
            return True, ""
        return False, f"Invalid email format: '{contact}'"
    digits = _re.sub(r"[\s\-\(\)\+]", "", contact)
    for pattern in _VALID_PHONE_PATTERNS:
        if pattern.match(digits):
            return True, ""
    return False, (
        f"Invalid phone number: '{contact}'. "
        f"Must be a valid mobile number from EG/SA/UAE/JO/SY/LB/KW. "
        f"Egypt example: 01012345678"
    )


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
        buying_signals: Comma-separated signals observed
        conversation_summary: 2-3 sentence Arabic summary of the full conversation
        recommended_action: Next action the sales rep should take
        city_country: User's city and country (default: غير محدد)
        language_dialect: Detected dialect (default: العربية)
        current_level: Technical level — beginner/intermediate/advanced
        objections: Any concerns or objections raised (optional)
    """
    from db import LeadDB

    is_valid, reason = _validate_contact(contact)
    if not is_valid:
        print(f"[CRM] Rejected lead '{name}' — {reason}")
        return (
            f"VALIDATION_ERROR: {reason}. "
            f"Do NOT save this lead. "
            f"Ask the user to provide their correct WhatsApp number (with country code) "
            f"or a valid email address before calling this tool again."
        )

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
        print(f"[CRM] ✓ Lead saved: {name} | {contact} | ID: {inserted_id}")
        return f"SUCCESS: Lead recorded — ID {inserted_id}"
    except Exception as e:
        print(f"[CRM] Failed to save lead: {e}")
        return f"FAILURE: {str(e)}"