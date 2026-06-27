"""
agent.py — Pydantic AI Agent Orchestration Hub.

  PATCH-1  Lean history  — _build_lean_history() strips ToolReturn parts,
           pre-fetched context blobs, and ToolCall JSON from message_history
           before each LLM call. Prevents KB content from compounding across
           turns. Estimated saving: 60-80% of history tokens after turn 2.

  PATCH-2  History window — lean history is capped at MAX_HISTORY_TURNS (5)
           user+assistant pairs. Older turns are dropped entirely.
           Prevents unbounded growth in long sessions.

  PATCH-3  Conditional language reminder — only injected when the query is
           non-trivial (router didn't skip AND message length > 20 chars).
           Saves ~80 tokens on every "hi", "thanks", CRM-only turn.

  PATCH-4  QueryRouter pattern fix — "hi " → "hi" (strip trailing spaces
           from all patterns so bare words match correctly).
           Prevents retrieval from firing on greetings that lack a trailing space.
"""

import asyncio
import os
import re
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
import streamlit as st
from usage_tracker import track_usage, accumulate_session_usage
from prompts import SYSTEM_PROMPT
import tools
from tools import QueryRouter, EmbeddingCache
from db import KnowledgeBaseDB, LeadDB

load_dotenv()
ACTIVE_MODEL = "openai/gpt-oss-120b"

MAX_HISTORY_TURNS = 5

# ── regex to strip tool-call leak formats ────────────────────────────────────
_LEAK_RE = re.compile(
    r"<function[_a-z]*\s*=\s*\w+[^<]*"
    r"|<function(?:_call)?=[^>]*>.*?</function(?:_call)?>"
    r"|ToolCall\([^)]*\)"
    r"|\[TOOL_CALL\][^\n]*",
    flags=re.DOTALL,
)
_JSON_BLOCK_RE = re.compile(
    r"\{s*\"name\"\s*:.*?\}"
    r"|\{\s*\"query_text\"\s*:.*?\}",
    flags=re.DOTALL
)

def _clean(text: str) -> str:
    if not text:
        return ""
    text = _LEAK_RE.sub("", text)
    text = _JSON_BLOCK_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

# BEHAVIOUR TRACE LOGGER

def _log_trace(
    session_id:    str,
    user_id:       str,
    turn_number:   int,
    user_message:  str,
    retrieval_ran: bool,
    pre_context:   str,
    all_msgs:      list,
    output_text:   str,
    record,
    latency_ms:    int,
) -> None:
    """
    Write one behaviour trace document to MongoDB (behaviour_traces collection).
    """
    try:
        # ── Extract tool calls + results from message history ──────────────
        tool_steps = []
        for msg in all_msgs:
            for part in getattr(msg, "parts", []):
                ptype = type(part).__name__
                if "ToolCall" in ptype and "Return" not in ptype:
                    tool_steps.append({
                        "type": "call",
                        "tool": getattr(part, "tool_name", "unknown"),
                        "args": str(getattr(part, "args", ""))[:400],
                    })
                elif "ToolReturn" in ptype or "tool_return" in ptype.lower():
                    content = str(
                        getattr(part, "content", "")
                        or getattr(part, "tool_return", "")
                    )
                    tool_steps.append({
                        "type":           "result",
                        "tool":           getattr(part, "tool_name", "unknown"),
                        "result_preview": content[:400],
                        "result_length":  len(content),
                    })

        # ── Extract source file names from pre-fetched context ─────────────
        sources = re.findall(r"### Source:\s*([^\n—\-]+)", pre_context or "")
        sources = [s.strip() for s in sources]

        LeadDB.db["behaviour_traces"].insert_one({
            "session_id":   session_id,
            "user_id":      user_id,
            "turn_number":  turn_number,
            "timestamp":    datetime.now(timezone.utc),
            "user_message": user_message,
            "step_retrieval": {
                "ran":           retrieval_ran,
                "sources":       sources,
                "context_chars": len(pre_context or ""),
            },
            "step_tool_calls": tool_steps,
            "step_response": {
                "text_preview": output_text[:400],
                "full_length":  len(output_text),
            },
            "input_tokens":   record.input_tokens,
            "output_tokens":  record.output_tokens,
            "total_cost_usd": record.total_cost_usd,
            "latency_ms":     latency_ms,
        })
        print(f"[trace] ✓ Turn {turn_number} logged to MongoDB")
    except Exception as e:
        print(f"[trace]  Trace log failed: {e}")


# PATCH-1 + PATCH-2  LEAN HISTORY BUILDER

def _build_lean_history(all_messages: list) -> list:
    lean: list[ModelMessage] = []

    for msg in all_messages:
        parts = getattr(msg, "parts", [])
        if not parts:
            continue

        msg_type = type(msg).__name__

        if "Request" in msg_type:
            clean_parts = []
            for part in parts:
                ptype = type(part).__name__
                if "UserPrompt" in ptype or ptype.lower() == "userpromptpart":
                    raw_content = getattr(part, "content", "") or ""
                    if "[PRE-FETCHED KNOWLEDGE BASE CONTEXT]" in raw_content:
                        sentinel = "[END CONTEXT]\n\n"
                        idx = raw_content.find(sentinel)
                        if idx != -1:
                            raw_content = raw_content[idx + len(sentinel):]
                    for reminder_marker in ["[CRITICAL DIRECTIVE]"]:
                        ri = raw_content.find(f"\n\n{reminder_marker}")
                        if ri != -1:
                            raw_content = raw_content[:ri]
                    if raw_content.strip():
                        clean_parts.append(UserPromptPart(content=raw_content.strip()))
            if clean_parts:
                lean.append(ModelRequest(parts=clean_parts))

        elif "Response" in msg_type:
            clean_parts = []
            for part in parts:
                ptype = type(part).__name__
                if "Text" in ptype and not ("ToolCall" in ptype or "ToolReturn" in ptype):
                    text_content = getattr(part, "content", "") or getattr(part, "text", "")
                    cleaned = _clean(str(text_content))
                    if cleaned:
                        clean_parts.append(TextPart(content=cleaned))
            if clean_parts:
                lean.append(ModelResponse(parts=clean_parts))

    max_messages = MAX_HISTORY_TURNS * 2
    if len(lean) > max_messages:
        lean = lean[-max_messages:]

    return lean


# PARALLEL RETRIEVAL

async def _run_retrieval_parallel(query_text: str) -> str:
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, EmbeddingCache.encode, query_text)

    def _courses():
        r = KnowledgeBaseDB.search_courses(query_text=query_text)
        return r or ""

    def _roadmap():
        r = KnowledgeBaseDB.search_roadmaps(structural_name=query_text)
        return r or ""

    def _policies():
        r = KnowledgeBaseDB.query_unstructured_kb(query_text, top_n=5)
        return r or ""

    def _pricing():
        # Always fetch the pricing document regardless of the user query.
        # "enrol in X" has low similarity to a price table — dedicated
        # query guarantees the price is always in context.
        r = KnowledgeBaseDB.query_unstructured_kb(
            "Kayfa paid educational tracks price table", top_n=2
        )
        return r or ""

    courses, roadmap, policies, pricing = await asyncio.gather(
        loop.run_in_executor(None, _courses),
        loop.run_in_executor(None, _roadmap),
        loop.run_in_executor(None, _policies),
        loop.run_in_executor(None, _pricing),
    )

    # Merge pricing into policies so dedup handles overlap
    combined_policies = "\n\n---\n\n".join(
        c for c in [policies, pricing] if c.strip()
    )

    chunks = [c for c in [courses, roadmap, combined_policies] if c.strip()]
    deduped = tools.deduplicate_chunks(chunks, threshold=0.92)
    all_chunks = deduped
    if pricing.strip():
        all_chunks = [pricing] + deduped  # pricing first = highest priority

    if not deduped:
        return ""

    return (
        "[PRE-FETCHED KNOWLEDGE BASE CONTEXT]\n"
        + "\n\n---\n\n".join(deduped)
        + "\n[END CONTEXT]\n\n"
        + "[SYSTEM REMINDER: Respond entirely in the language/dialect the user used.]"
    )

# AGENT BUILDERS

@st.cache_resource
def build_agent():
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        print("[agent] GROQ_API_KEY not found.")
        return None
    try:
        sales_agent = Agent(
            "groq:openai/gpt-oss-120b",
            system_prompt=SYSTEM_PROMPT,
        )
        for tool_fn in [
            tools.search_available_courses,
            tools.get_roadmap_or_diploma_details,
            tools.lookup_policies_and_sales_pitches,
            tools.capture_and_save_crm_lead,
        ]:
            try:
                sales_agent.tool(tool_fn)
                print(f"[agent] Tool registered: {tool_fn.__name__}")
            except Exception as e:
                print(f"[agent] Tool {tool_fn.__name__} failed: {e}")
        print("[agent] Agent ready.")
        return sales_agent
    except Exception as e:
        print(f"[agent] Build failed: {e}")
        return None


@st.cache_resource
def build_synthesis_agent():
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return None
    try:
        return Agent("groq:openai/gpt-oss-120b", system_prompt=SYSTEM_PROMPT)
    except Exception:
        return None


def _extract_tool_results(messages: list) -> str:
    parts_out = []
    for msg in messages:
        for part in getattr(msg, "parts", []):
            ptype = type(part).__name__
            if "ToolReturn" in ptype or "tool_return" in ptype.lower():
                content = getattr(part, "content", "") or getattr(part, "tool_return", "")
                if content and str(content).strip():
                    parts_out.append(str(content))
    return "\n\n---\n\n".join(parts_out)

# MAIN RUN FUNCTION

def run_agent(agent, prompt: str, history: list,
              display_messages: list) -> tuple[str, list]:
    if agent is None:
        return _fallback(prompt), history

    try:
        is_arabic      = any("\u0600" <= c <= "\u06FF" for c in prompt)
        skip_retrieval = QueryRouter.should_skip_retrieval(prompt)

        is_trivial = skip_retrieval or len(prompt.strip()) < 20
        language_reminder = ""
        if not is_trivial:
            language_reminder = (
                "\n\n[CRITICAL DIRECTIVE]\nتذكير صارم: يجب أن تكون الإجابة بالكامل باللغة العربية وباللهجة التي يفضلها المستخدم ولا تغير اللغة مطلقاً بسبب نتائج الأدوات الإنجليزية."
                if is_arabic else
                "\n\n[CRITICAL DIRECTIVE]\nStrict Reminder: Respond entirely in English as preferred by the user, completely disregarding English context strings shifting your target formatting."
            )

        # ── Retrieval ──────────────────────────────────────────────────────
        pre_context = ""
        if not skip_retrieval:
            try:
                pre_context = asyncio.run(_run_retrieval_parallel(prompt))
                print(f"[agent] Parallel retrieval done — context length: {len(pre_context)} chars")
            except RuntimeError:
                loop = asyncio.new_event_loop()
                try:
                    pre_context = loop.run_until_complete(_run_retrieval_parallel(prompt))
                finally:
                    loop.close()
        else:
            print("[agent] QueryRouter: retrieval skipped for this turn")

        
        enriched_prompt = f"{pre_context}{prompt}{language_reminder}"
        lean_history    = _build_lean_history(history)

        # ── LLM call ──────────────────────────────────────────────────────
        start_time  = time.time()
        result      = agent.run_sync(enriched_prompt, message_history=lean_history)
        latency_ms  = int((time.time() - start_time) * 1000)

        all_msgs    = result.all_messages()
        output_text = _clean(result.output)

        # ── Usage tracking + trace logging ────────────────────────────────
        try:
            turn_record = track_usage(
                result,
                model         = ACTIVE_MODEL,
                user_message  = prompt,
                retrieval_ran = not skip_retrieval,
            )
            accumulate_session_usage(
                st.session_state,
                turn_record,
                user_id = st.session_state.get("username"),
            )
            print(f"[TRACKER] Turn Cost: ${turn_record.cost_usd} | Session: ${st.session_state.get('usage_total_cost', 0.0)}")

            _log_trace(
                session_id    = st.session_state.get("session_id", ""),
                user_id       = st.session_state.get("username", ""),
                turn_number   = st.session_state.get("usage_turn_count", 0),
                user_message  = prompt,
                retrieval_ran = not skip_retrieval,
                pre_context   = pre_context,
                all_msgs      = all_msgs,
                output_text   = output_text,
                record        = turn_record,
                latency_ms    = latency_ms,
            )
        except Exception as tracker_err:
            print(f"[agent] Tracker warning: {tracker_err}")

        # ── Return if we have output ───────────────────────────────────────
        if output_text:
            return output_text, all_msgs

        # ── Layer 2: last TextPart ─────────────────────────────────────────
        for msg in reversed(all_msgs):
            for part in reversed(getattr(msg, "parts", [])):
                ptype = type(part).__name__
                if "Text" in ptype or ptype.lower().endswith("text"):
                    raw     = getattr(part, "content", "") or getattr(part, "text", "")
                    cleaned = _clean(str(raw))
                    if cleaned:
                        print("[agent] ℹ️  Layer 2 fallback used")
                        return cleaned, all_msgs

        # ── Layer 3: synthesis agent ───────────────────────────────────────
        tool_ctx = _extract_tool_results(all_msgs)
        if not tool_ctx and pre_context:
            tool_ctx = pre_context

        if tool_ctx:
            print("[agent] ℹ️  Layer 3 synthesis fallback used")
            synth = build_synthesis_agent()
            if synth:
                syn_prompt = (
                    f"The user asked: {prompt}\n\n"
                    f"Retrieved knowledge base context:\n\n{tool_ctx}\n\n"
                    f"Answer the user's question directly using ONLY the context above. "
                    f"Match their language exactly."
                )
                syn_result = synth.run_sync(syn_prompt)
                syn_text   = _clean(syn_result.output)
                if syn_text:
                    return syn_text, all_msgs

        print("[agent] All layers empty — using fallback message")
        return _fallback(prompt), history

    except Exception as e:
        print(f"[agent] Inference error: {e}")
        return _fallback(prompt), history


def _fallback(prompt: str) -> str:
    is_arabic = any("\u0600" <= c <= "\u06FF" for c in prompt)
    if is_arabic:
        return (
            "أهلاً بك! أواجه تأخيراً مؤقتاً. "
            "يرجى مشاركة اسمك ورقم واتساب وسيتواصل معك فريق المبيعات فوراً."
        )
    return (
        "Welcome to Kayfa! I'm experiencing a brief delay. "
        "Please share your name and WhatsApp and our team will reach out directly."
    )