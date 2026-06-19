"""
agent.py — Pydantic AI Agent Orchestration Hub.

FIXES:
  1. Blank response: 3-layer fallback (output → text parts → synthesis agent)
  2. Tool call leaking into text: comprehensive _LEAK_RE strips all known
     Groq llama formats: <function=name {json}>, ToolCall(...), [TOOL_CALL]
  3. Greetings triggering tool calls: handled in prompts.py CONVERSATIONAL_INTENTS
"""

import os
import re
from dotenv import load_dotenv
from pydantic_ai import Agent
import streamlit as st

from prompts import SYSTEM_PROMPT
import tools

load_dotenv()

# ── regex to strip all tool-call leak formats from Groq llama ────────────────
# Format 1: <function=search_available_courses {"query_text": "x"}>
# Format 2: <function=name {"json"}   (no closing >)
# Format 3: <function_call=name>...</function_call>
# Format 4: ToolCall(name, {json})
# Format 5: [TOOL_CALL] name
_LEAK_RE = re.compile(
    r"<function[_a-z]*\s*=\s*\w+[^<]*"
    r"|<function(?:_call)?=[^>]*>.*?</function(?:_call)?>"
    r"|ToolCall\([^)]*\)"
    r"|\[TOOL_CALL\][^\n]*",
    flags=re.DOTALL,
)

# Aggressive cleaner to find any raw JSON-like blocks or parameter mappings remaining
_JSON_BLOCK_RE = re.compile(
    r"\{s*\"name\"\s*:.*?\}"  # Matches structural CRM lead properties
    r"|\{\s*\"query_text\"\s*:.*?\}", # Matches search tool query layouts
    flags=re.DOTALL
)

def _clean(text: str) -> str:
    """Strip all known Groq llama tool-call leak formats from response text."""
    if not text:
        return ""
    text = _LEAK_RE.sub("", text)
    # collapse triple+ newlines left after removal
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@st.cache_resource
def build_agent():
    """Build and cache the Pydantic AI agent with all tools registered."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        print("[agent] ❌ GROQ_API_KEY not found.")
        return None

    try:
        sales_agent = Agent(
            "groq:llama-3.3-70b-versatile",
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
                print(f"[agent] ✅ Tool registered: {tool_fn.__name__}")
            except Exception as e:
                print(f"[agent] ⚠️  Tool {tool_fn.__name__} failed: {e}")

        print("[agent] ✅ Agent ready.")
        return sales_agent

    except Exception as e:
        print(f"[agent] ❌ Build failed: {e}")
        return None


@st.cache_resource
def build_synthesis_agent():
    """
    No-tool synthesis agent.
    Used when main agent returns empty after tool calls — forced text response.
    """
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return None
    try:
        return Agent("groq:llama-3.3-70b-versatile", system_prompt=SYSTEM_PROMPT)
    except Exception:
        return None


def _extract_tool_results(messages: list) -> str:
    """Extract all tool return values from a Pydantic AI message list."""
    parts_out = []
    for msg in messages:
        for part in getattr(msg, "parts", []):
            ptype = type(part).__name__
            if "ToolReturn" in ptype or "tool_return" in ptype.lower():
                content = getattr(part, "content", "") or getattr(part, "tool_return", "")
                if content and str(content).strip():
                    parts_out.append(str(content))
    return "\n\n---\n\n".join(parts_out)


def run_agent(agent, prompt: str, history: list,
              display_messages: list) -> tuple[str, list]:
    """
    Run one agent turn. Returns (reply_text, updated_history).

    Blank response — 3-layer fallback:
      Layer 1: result.output  (normal path)
      Layer 2: last TextPart from all_messages()
      Layer 3: synthesis agent fed with tool results as context
    """
    if agent is None:
        return _fallback(prompt), history

    try:
        result      = agent.run_sync(prompt, message_history=history)
        all_msgs    = result.all_messages()
        output_text = _clean(result.output)

        if output_text:
            return output_text, all_msgs

        # Layer 2 — scan for last text part
        for msg in reversed(all_msgs):
            for part in reversed(getattr(msg, "parts", [])):
                ptype = type(part).__name__
                if "Text" in ptype or ptype.lower().endswith("text"):
                    raw = getattr(part, "content", "") or getattr(part, "text", "")
                    cleaned = _clean(str(raw))
                    if cleaned:
                        print("[agent] ℹ️  Layer 2 fallback used")
                        return cleaned, all_msgs

        # Layer 3 — synthesise from tool results
        tool_ctx = _extract_tool_results(all_msgs)
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

        print("[agent] ⚠️  All layers empty — using fallback message")
        return _fallback(prompt), history

    except Exception as e:
        print(f"[agent] ❌ Inference error: {e}")
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