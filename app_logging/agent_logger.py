"""
CONDUIT — Agent Logger
=======================
Structured logging functions for all five agents.
Every agent imports and calls these four functions:

    log_agent_start()      → when agent begins processing
    log_agent_end()        → when agent completes successfully
    log_agent_error()      → when agent throws exception
    log_guardrail_failure() → when validation check fails

Also writes to agent_audit_log table in PostgreSQL
so the Streamlit dashboard can display pipeline traces.
"""

import os
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
)))

from app_logging.logger import agent_logger


# ── DB AUDIT LOG ──────────────────────────────────────────────────────────────

def _write_audit_log(
    agent_name:     str,
    ro_id:          Optional[str],
    action:         str,
    input_payload:  Optional[Dict] = None,
    output_payload: Optional[Dict] = None,
    latency_ms:     Optional[int]  = None,
) -> None:
    """
    Writes agent event to agent_audit_log table in PostgreSQL.
    Silent fail — logging should never crash the pipeline.
    """
    try:
        from database.connection import get_session
        from database.models import AgentAuditLog

        with get_session() as db:
            log = AgentAuditLog(
                ro_id          = ro_id,
                agent_name     = agent_name,
                action         = action,
                input_payload  = input_payload,
                output_payload = output_payload,
                latency_ms     = latency_ms,
            )
            db.add(log)
            db.commit()

    except Exception:
        # Never let audit logging crash the pipeline
        pass


# ── AGENT LOGGING FUNCTIONS ───────────────────────────────────────────────────

def log_agent_start(
    agent_name:    str,
    ro_id:         Optional[str],
    input_summary: Optional[Dict] = None,
) -> None:
    """
    Called at the start of every agent's run() function.

    Logs to:
      - Console (INFO level)
      - conduit.log file
      - agent_audit_log table

    Usage:
        log_agent_start(
            agent_name    = "intake_agent",
            ro_id         = state.get("ro_id"),
            input_summary = {"vin": state.get("vin"), "complaint": "..."},
        )
    """
    payload = {
        "event":         "agent_start",
        "agent":         agent_name,
        "ro_id":         ro_id,
        "vin":           None,
        "input_summary": input_summary or {},
        "ts":            datetime.now(timezone.utc).isoformat(),
    }

    agent_logger.info(payload)

    _write_audit_log(
        agent_name    = agent_name,
        ro_id         = ro_id,
        action        = "START",
        input_payload = input_summary,
    )


def log_agent_end(
    agent_name:     str,
    ro_id:          Optional[str],
    output_summary: Optional[Dict] = None,
    latency_ms:     Optional[int]  = None,
) -> None:
    """
    Called at the end of every agent's run() function on success.

    Usage:
        log_agent_end(
            agent_name     = "intake_agent",
            ro_id          = ro_id,
            output_summary = {
                "fault":      classification.get("fault_classification"),
                "confidence": classification.get("confidence"),
                "latency_ms": latency_ms,
            },
            latency_ms = latency_ms,
        )
    """
    payload = {
        "event":          "agent_end",
        "agent":          agent_name,
        "ro_id":          ro_id,
        "status":         "success",
        "duration_ms":    None,
        "output_summary": output_summary or {},
        "latency_ms":     latency_ms,
        "ts":             datetime.now(timezone.utc).isoformat(),
    }

    agent_logger.info(payload)

    _write_audit_log(
        agent_name     = agent_name,
        ro_id          = ro_id,
        action         = "END",
        output_payload = output_summary,
        latency_ms     = latency_ms,
    )


def log_agent_error(
    agent_name:  str,
    ro_id:       Optional[str],
    error:       str,
    input_state: Optional[Dict] = None,
) -> None:
    """
    Called in the except block of every agent's run() function.

    Usage:
        except Exception as e:
            log_agent_error(
                agent_name  = "intake_agent",
                ro_id       = ro_id,
                error       = str(e),
                input_state = {"vin": state.get("vin")},
            )
    """
    payload = {
        "event":       "agent_error",
        "agent":       agent_name,
        "ro_id":       ro_id,
        "error":       error,
        "input_state": input_state or {},
        "ts":          datetime.now(timezone.utc).isoformat(),
    }

    agent_logger.error(payload)

    _write_audit_log(
        agent_name    = agent_name,
        ro_id         = ro_id,
        action        = "ERROR",
        input_payload = input_state,
        output_payload = {"error": error},
    )


def log_guardrail_failure(
    agent_name: str,
    ro_id:      Optional[str],
    reason:     str,
    details:    Optional[Dict] = None,
) -> None:
    """
    Called when a guardrail validation check fails.
    Logged as WARNING — pipeline may continue with override.

    Usage:
        is_valid, reason = validate_intake_output(classification, ro_id)
        if not is_valid:
            log_guardrail_failure("intake_agent", ro_id, reason)
    """
    payload = {
        "event":   "guardrail_failure",
        "agent":   agent_name,
        "ro_id":   ro_id,
        "reason":  reason,
        "details": details or {},
        "ts":      datetime.now(timezone.utc).isoformat(),
    }

    agent_logger.warning(payload)

    _write_audit_log(
        agent_name     = agent_name,
        ro_id          = ro_id,
        action         = "GUARDRAIL_FAILURE",
        input_payload  = details,
        output_payload = {"reason": reason},
    )


def log_hitl_trigger(
    agent_name: str,
    ro_id:      Optional[str],
    trigger:    str,
    details:    Optional[Dict] = None,
) -> None:
    """
    Called when HITL is triggered — either intake or transaction.

    Usage:
        log_hitl_trigger(
            agent_name = "orchestrator",
            ro_id      = ro_id,
            trigger    = "intake_hitl",
            details    = {"confidence": 0.45, "fault": "UNKNOWN"},
        )
    """
    payload = {
        "event":   "hitl_trigger",
        "agent":   agent_name,
        "ro_id":   ro_id,
        "trigger": trigger,
        "details": details or {},
        "ts":      datetime.now(timezone.utc).isoformat(),
    }

    agent_logger.warning(payload)

    _write_audit_log(
        agent_name     = agent_name,
        ro_id          = ro_id,
        action         = f"HITL_{trigger.upper()}",
        input_payload  = details,
    )


def log_pipeline_complete(
    ro_id:         str,
    total_ms:      int,
    final_status:  str,
    quote_total:   Optional[float] = None,
    pos_raised:    int = 0,
) -> None:
    """
    Called by orchestrator when full pipeline completes.
    Gives end-to-end timing for the entire RO.
    """
    from app_logging.logger import pipeline_logger

    payload = {
        "event":        "pipeline_complete",
        "ro_id":        ro_id,
        "final_status": final_status,
        "total_ms":     total_ms,
        "quote_total":  quote_total,
        "pos_raised":   pos_raised,
        "ts":           datetime.now(timezone.utc).isoformat(),
    }

    pipeline_logger.info(payload)

    _write_audit_log(
        agent_name     = "orchestrator",
        ro_id          = ro_id,
        action         = "PIPELINE_COMPLETE",
        output_payload = payload,
        latency_ms     = total_ms,
    )