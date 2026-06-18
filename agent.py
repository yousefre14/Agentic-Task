"""
agent.py — The Sales Agent (Pydantic AI + Groq)

ARCHITECTURE:
- Groq as LLM backend (fast inference)
- RAG engine provides grounding (Kayfa KB)
- Tool-based retrieval (products + policies)
- Stateful conversation via message_history
"""

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.groq import GroqModel
from rag_engine import kb
import os


# =========================
# SYSTEM PROMPT (UNCHANGED)
# =========================
SALES_SYSTEM_PROMPT = """
أنت مساعد مبيعات ودود وخبير لشركة كيفاء (Kayfa) — منصة تعليم متقدمة في علم البيانات والذكاء الاصطناعي والأمن السيبراني.

**Your Mission:**
1. Understand what the visitor actually wants (skill-building, career change, specific tools)
2. Recommend the RIGHT product from Kayfa's catalog grounded in real data
3. Answer their questions honestly — refunds, access, certificates, prerequisites
4. Handle objections persuasively but truthfully
5. Guide warm leads toward enrollment
6. Detect when they're serious → capture as a CRM lead

**Core Constraints:**
- NEVER invent prices, courses, or policies — use only what you retrieve
- Answer in the visitor's language (Arabic or English) + match their dialect
- Be warm, professional, never pushy
- If you don't know something, offer to connect them with the team

**Sales Strategy:**
Start where they are comfortable, then guide upward.
"""


# =========================
# CONTEXT
# =========================
class SalesContext:
    def __init__(self, user_language: str = 'ar', user_dialect: str = 'egyptian'):
        self.user_language = user_language
        self.user_dialect = user_dialect
        self.conversation_turns = 0


# =========================
# GROQ MODEL BINDING (FIX)
# =========================

model = GroqModel("llama-3.1-8b-instant")

# =========================
# AGENT INITIALIZATION
# =========================
sales_agent = Agent(
    model=model,
    system_prompt=SALES_SYSTEM_PROMPT,
    deps_type=SalesContext,
)


# =========================
# TOOLS
# =========================
@sales_agent.tool
async def search_products(ctx: RunContext[SalesContext], query: str) -> str:
    courses = kb.search_courses(query, limit=3)
    roadmaps = kb.search_roadmaps(query, limit=2)

    context = kb.format_context_for_agent(courses, roadmaps)

    if not courses and not roadmaps:
        return "No products found. Offer escalation to human support."

    return context


@sales_agent.tool
async def search_policies(ctx: RunContext[SalesContext], query: str) -> str:
    result = kb.search_faq(query)

    return result or "Policy not found. Escalate to support team."


# =========================
# RUN LOOP
# =========================
async def run_agent(
    user_message: str,
    message_history: list,
    language: str = 'ar',
    dialect: str = 'egyptian'
) -> str:

    try:
        ctx = SalesContext(
            user_language=language,
            user_dialect=dialect
        )

        result = await sales_agent.run(
            user_message,
            message_history=message_history,
            deps=ctx,
        )

        return result.output

    except Exception as e:
        return f"System error. Please retry or escalate to support."