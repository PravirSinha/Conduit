"""
CONDUIT — Centralised Configuration
All config values loaded from .env in one place.
Every file imports from here — never from os.getenv directly.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── OPENAI ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL      = os.getenv("OPENAI_MODEL_NAME", "gpt-4o")
OPENAI_EVAL_MODEL = os.getenv("OPENAI_EVAL_MODEL", "gpt-4o-mini")

# ── PINECONE ──────────────────────────────────────────────────────────────────
PINECONE_API_KEY    = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "conduit-parts-catalog")

# ── DATABASE ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")

# ── LANGSMITH ─────────────────────────────────────────────────────────────────
LANGCHAIN_TRACING  = os.getenv("LANGCHAIN_TRACING_V2", "false")
LANGCHAIN_API_KEY  = os.getenv("LANGCHAIN_API_KEY")
LANGCHAIN_PROJECT  = os.getenv("LANGCHAIN_PROJECT", "conduit-portfolio")

# ── HITL ──────────────────────────────────────────────────────────────────────
_legacy_hitl_enabled   = os.getenv("HITL_ENABLED", "false").lower() == "true"

# Split flags (preferred):
# - INTAKE_HITL_ENABLED controls the Intake ambiguity pause + supervisor override
# - TRANSACTION_HITL_ENABLED controls the quote approval pause (amount cutoffs, EV, recall, etc.)
INTAKE_HITL_ENABLED      = os.getenv("INTAKE_HITL_ENABLED", str(_legacy_hitl_enabled)).lower() == "true"
TRANSACTION_HITL_ENABLED = os.getenv("TRANSACTION_HITL_ENABLED", str(_legacy_hitl_enabled)).lower() == "true"

# Backward-compatible aggregate: true if any HITL gate is enabled.
HITL_ENABLED             = INTAKE_HITL_ENABLED or TRANSACTION_HITL_ENABLED
AUTO_APPROVE_THRESHOLD = float(os.getenv("AUTO_APPROVE_THRESHOLD", "50000"))
ADVISOR_PIN            = os.getenv("ADVISOR_PIN", "1234")

# ── APP ───────────────────────────────────────────────────────────────────────
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL   = os.getenv("LOG_LEVEL", "INFO")


def validate_required_config():
    """
    Validates all required env vars are present at startup.
    Call this once in api/main.py and orchestrator.py.
    Fails fast with clear error message.
    """
    required = {
        "OPENAI_API_KEY":    OPENAI_API_KEY,
        "PINECONE_API_KEY":  PINECONE_API_KEY,
        "DATABASE_URL":      DATABASE_URL,
    }

    missing = [k for k, v in required.items() if not v]

    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {missing}\n"
            f"Check your .env file."
        )