"""
usage_tracker.py — Per-Message Usage Tracking with MongoDB Persistence.

Responsibilities:
  1. Compute LLM cost from token counts.
  2. Compute embedding cost separately (different provider/rate).
  3. Persist one record per turn to MongoDB (usage_turns).
  4. Upsert a session summary (usage_sessions).
  5. Update Streamlit session_state running totals.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from db import LeadDB

LLM_PRICING = {
    "openai/gpt-oss-120b": {
        "input":  0.15 / 1_000_000,
        "output": 0.60 / 1_000_000,
    },
}

# the record is complete if you swap to a hosted embedding API later.
EMBEDDING_PRICING = {
    "paraphrase-multilingual-MiniLM-L12-v2": {
        "per_token": 0.0,
        "provider":  "local",
    },
}

DEFAULT_LLM_MODEL       = "openai/gpt-oss-120b"
DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


# DATA MODEL
@dataclass
class UsageRecord:
    # ── LLM tokens ────────────────────────────────────────────────────────
    input_tokens:   int
    output_tokens:  int
    total_tokens:   int
    llm_cost_usd:   float
    llm_model:      str     = DEFAULT_LLM_MODEL

    # ── Embedding tokens (provider / rate) ────────────────────────
    embedding_tokens:    int   = 0
    embedding_cost_usd:  float = 0.0
    embedding_model:     str   = DEFAULT_EMBEDDING_MODEL

    # ── Total (LLM + embeddings) ───────────────────────────────────────────
    total_cost_usd:  float  = 0.0

    # ── Context ───────────────────────────────────────────────────────────
    timestamp:            datetime      = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id:           Optional[str] = None
    user_id:              Optional[str] = None
    turn_number:          Optional[int] = None
    retrieval_ran:        Optional[bool] = None
    user_message_preview: Optional[str] = None
    is_arabic:            Optional[bool] = None

    # backward-compat alias so agent.py print still works
    @property
    def cost_usd(self) -> float:
        return self.total_cost_usd


# TOKEN EXTRACTION

def _extract_tokens(usage_obj) -> tuple[int, int]:
    input_tokens = (
        getattr(usage_obj, "request_tokens",  None)
        or getattr(usage_obj, "input_tokens",  None)
        or 0
    )
    output_tokens = (
        getattr(usage_obj, "response_tokens", None)
        or getattr(usage_obj, "output_tokens", None)
        or 0
    )
    return int(input_tokens), int(output_tokens)


# TRACK USAGE

def track_usage(
    result,
    model:              str            = DEFAULT_LLM_MODEL,
    user_message:       Optional[str]  = None,
    retrieval_ran:      Optional[bool] = None,
    embedding_tokens:   int            = 0,
    embedding_model:    str            = DEFAULT_EMBEDDING_MODEL,
) -> UsageRecord:
    """
    Call right after agent.run_sync(). Returns a UsageRecord. Never raises.

    Args:
        result:           Pydantic AI RunResult
        model:            LLM model string (must match LLM_PRICING key)
        user_message:     Raw user prompt — first 120 chars stored as preview
        retrieval_ran:    Pass `not skip_retrieval` from agent.py
        embedding_tokens: Token count from the embedding call this turn
        embedding_model:  Embedding model name
    """
    input_tokens, output_tokens = 0, 0
    try:
        input_tokens, output_tokens = _extract_tokens(result.usage)
    except Exception as e:
        print(f"[usage_tracker] Could not read usage: {e}")

    llm_rates = LLM_PRICING.get(model, LLM_PRICING[DEFAULT_LLM_MODEL])
    llm_cost  = (input_tokens * llm_rates["input"]) + (output_tokens * llm_rates["output"])

    emb_rate  = EMBEDDING_PRICING.get(embedding_model, {"per_token": 0.0})
    emb_cost  = embedding_tokens * emb_rate["per_token"]

    is_arabic = None
    preview   = None
    if user_message:
        is_arabic = any("\u0600" <= c <= "\u06FF" for c in user_message)
        preview   = user_message.strip()[:120]

    return UsageRecord(
        input_tokens          = input_tokens,
        output_tokens         = output_tokens,
        total_tokens          = input_tokens + output_tokens,
        llm_cost_usd          = round(llm_cost, 6),
        llm_model             = model,
        embedding_tokens      = embedding_tokens,
        embedding_cost_usd    = round(emb_cost, 6),
        embedding_model       = embedding_model,
        total_cost_usd        = round(llm_cost + emb_cost, 6),
        retrieval_ran         = retrieval_ran,
        user_message_preview  = preview,
        is_arabic             = is_arabic,
    )

# ACCUMULATE + PERSIST

def accumulate_session_usage(
    session_state,
    record: UsageRecord,
    user_id: Optional[str] = None,
) -> None:
    """
    1. Update Streamlit session_state running totals.
    2. Assign a session_id UUID on first call.
    3. Stamp user_id onto the record.
    4. Persist turn to MongoDB (usage_turns).
    5. Upsert session summary (usage_sessions).

    Pass user_id=st.session_state.get("username") from agent.py.
    """
    if "usage_total_tokens" not in session_state:
        session_state["usage_total_tokens"] = 0
        session_state["usage_total_cost"]   = 0.0
        session_state["usage_turn_count"]   = 0

    session_state["usage_total_tokens"] += record.total_tokens
    session_state["usage_total_cost"]   += record.total_cost_usd
    session_state["usage_turn_count"]   += 1

    if "session_id" not in session_state:
        session_state["session_id"] = str(uuid.uuid4())

    record.session_id  = session_state["session_id"]
    record.turn_number = session_state["usage_turn_count"]
    record.user_id     = user_id or session_state.get("username")

    _persist_turn(record)
    _upsert_session(record)


# MONGODB WRITERS

def _persist_turn(record: UsageRecord) -> None:
    """
    Append one immutable document to usage_turns.

    Document shape:
    {
        session_id, user_id, turn_number, timestamp,
        llm_model, input_tokens, output_tokens, total_tokens, llm_cost_usd,
        embedding_model, embedding_tokens, embedding_cost_usd,
        total_cost_usd, retrieval_ran, user_message_preview, is_arabic
    }
    """
    try:
        LeadDB.db["usage_turns"].insert_one({
            "session_id":           record.session_id,
            "user_id":              record.user_id,
            "turn_number":          record.turn_number,
            "timestamp":            record.timestamp,
            "llm_model":            record.llm_model,
            "input_tokens":         record.input_tokens,
            "output_tokens":        record.output_tokens,
            "total_tokens":         record.total_tokens,
            "llm_cost_usd":         record.llm_cost_usd,
            "embedding_model":      record.embedding_model,
            "embedding_tokens":     record.embedding_tokens,
            "embedding_cost_usd":   record.embedding_cost_usd,
            "total_cost_usd":       record.total_cost_usd,
            "retrieval_ran":        record.retrieval_ran,
            "user_message_preview": record.user_message_preview,
            "is_arabic":            record.is_arabic,
        })
    except Exception as e:
        print(f"[usage_tracker] Turn persist failed: {e}")


def _upsert_session(record: UsageRecord) -> None:
    """
    Rolling session summary → usage_sessions collection.

    Document shape:
    {
        _id (session_id), user_id, first_seen, last_seen,
        turn_count, total_tokens, total_cost_usd,
        llm_cost_usd, embedding_cost_usd,
        retrieval_turns, skipped_turns,
        arabic_turns, english_turns, llm_model
    }
    """
    try:
        inc = {
            "turn_count":         1,
            "total_tokens":       record.total_tokens,
            "total_cost_usd":     record.total_cost_usd,
            "llm_cost_usd":       record.llm_cost_usd,
            "embedding_cost_usd": record.embedding_cost_usd,
        }
        if record.retrieval_ran is True:
            inc["retrieval_turns"] = 1
        elif record.retrieval_ran is False:
            inc["skipped_turns"] = 1
        if record.is_arabic is True:
            inc["arabic_turns"] = 1
        elif record.is_arabic is False:
            inc["english_turns"] = 1

        LeadDB.db["usage_sessions"].update_one(
            {"_id": record.session_id},
            {
                "$setOnInsert": {
                    "first_seen": record.timestamp,
                    "llm_model":  record.llm_model,
                    "user_id":    record.user_id,
                },
                "$set": {"last_seen": record.timestamp},
                "$inc": inc,
            },
            upsert=True,
        )
    except Exception as e:
        print(f"[usage_tracker] Session upsert failed: {e}")