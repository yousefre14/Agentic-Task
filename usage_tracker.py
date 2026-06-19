from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
 
# ── Groq pricing, USD per token (verified June 2026) ─────────────────────────
# Add your model pricing rules to your usage tracker file:
PRICING = {
    "llama-3.3-70b-versatile": {
        "input": 0.59 / 1_000_000,
        "output": 0.79 / 1_000_000,
    },
    "openai/gpt-oss-120b": {
        "input": 0.59 / 1_000_000,   # Set your specific model rate matrix here
        "output": 0.79 / 1_000_000,  # Set your specific model rate matrix here
    },
}

DEFAULT_MODEL = "openai/gpt-oss-120b"
 
@dataclass
class UsageRecord:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    model: str = DEFAULT_MODEL
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
 
 
def _extract_tokens(usage_obj) -> tuple[int, int]:
    """
    Pydantic AI's Usage object has used different attribute names across
    versions (request_tokens/response_tokens vs input_tokens/output_tokens).
    Try both rather than assuming one — avoids silently reporting 0 cost
    if the installed version uses the other naming.
    """
    input_tokens = (
        getattr(usage_obj, "request_tokens", None)
        or getattr(usage_obj, "input_tokens", None)
        or 0
    )
    output_tokens = (
        getattr(usage_obj, "response_tokens", None)
        or getattr(usage_obj, "output_tokens", None)
        or 0
    )
    return int(input_tokens), int(output_tokens)
 
 
def track_usage(result, model: str = DEFAULT_MODEL) -> UsageRecord:
    """
    Call this right after agent.run_sync(). `result` is the Pydantic AI
    RunResult — this reads result.usage() and computes estimated cost.
 
    Never raises: returns a zeroed record if usage data is unavailable,
    so a tracking failure can never break a chat turn.
    """
    input_tokens, output_tokens = 0, 0
    try:
        usage_obj = result.usage()
        input_tokens, output_tokens = _extract_tokens(usage_obj)
    except Exception as e:
        print(f"[usage_tracker] ⚠️  Could not read usage: {e}")
 
    rates = PRICING.get(model, PRICING[DEFAULT_MODEL])
    cost = (input_tokens * rates["input"]) + (output_tokens * rates["output"])
 
    return UsageRecord(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        cost_usd=round(cost, 6),
        model=model,
    )
 
 
def accumulate_session_usage(session_state, record: UsageRecord) -> None:
    """
    Add one turn's usage into Streamlit's session_state running totals.
    Pass st.session_state in directly — this module takes it as a plain
    dict-like argument rather than importing streamlit itself, so it can
    be unit-tested (e.g. from test.py) without a running Streamlit app.
 
    Initializes the three counters on first call — no separate init step.
    """
    if "usage_total_tokens" not in session_state:
        session_state["usage_total_tokens"] = 0
        session_state["usage_total_cost"] = 0.0
        session_state["usage_turn_count"] = 0
 
    session_state["usage_total_tokens"] += record.total_tokens
    session_state["usage_total_cost"] += record.cost_usd
    session_state["usage_turn_count"] += 1