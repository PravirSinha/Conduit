"""
CONDUIT — LangGraph Orchestrator
==================================
Wires all five agents into a single StateGraph pipeline.

Pipeline flow:
    intake → [intake_hitl?] → inventory → quoting → transaction → replenishment → END

Conditional routing:
    After intake     → confidence < 0.70 or parts = [] → intake_hitl (supervisor review)
                     → else → inventory (normal flow)
    After inventory  → quoting (always — quoting handles empty parts gracefully)
    After quoting    → if error → END
                     → else    → transaction
    After transaction → approved  → replenishment
                      → rejected  → END

Intake HITL triggers for:
    - Agent confidence < 0.70 (ambiguous complaint)
    - No parts identified (unknown fault / body work / paint)
    - Supervisor can provide: parts from catalog, custom materials, labor-only

Key LangGraph concepts used:
    StateGraph      — directed graph of agent nodes
    TypedDict       — shared typed state passed between agents
    add_conditional_edges — routing logic based on state
    PostgresSaver   — checkpoint state to DB for HITL resumability
    compile()       — produces executable graph

Usage:
    # Run full pipeline
    from orchestrator import run_pipeline

    result = run_pipeline(
        ro_id="RO-2024-00001",
        vin="1HGBH41JXMN109186",
        complaint_text="grinding noise from front when braking",
    )

    # Resume after HITL pause
    from orchestrator import resume_pipeline

    result = resume_pipeline(
        ro_id="RO-2024-00001",
        approved=True,
        advisor_id="SA-001",
    )
"""

import os
import sys

# ── PATH SETUP ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from typing import TypedDict, Optional, List, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agents.intake_agent       import run_intake_agent
from agents.inventory_agent    import run_inventory_agent
from agents.quoting_agent      import run_quoting_agent
from agents.transaction_agent  import run_transaction_agent
from agents.replenishment_agent import run_replenishment_agent

from config import HITL_ENABLED, INTAKE_HITL_ENABLED, DATABASE_URL


# ── SHARED STATE DEFINITION ───────────────────────────────────────────────────
# Every field that any agent reads or writes must be declared here.
# TypedDict gives type safety and makes the data contract explicit.
# Agents receive the full state and return updated state.

class CONDUITState(TypedDict, total=False):

    # ── INPUT ─────────────────────────────────────────────────────────────
    ro_id:              str
    vin:                str
    complaint_text:     str
    customer_id:        Optional[str]

    # ── AGENT 1 — INTAKE ──────────────────────────────────────────────────
    vehicle_details:            Optional[Dict]
    customer_details:           Optional[Dict]
    recall_flags:               List[Dict]
    retrieved_parts_context:    List[Dict]
    fault_classification:       Optional[str]
    fault_description:          Optional[str]
    required_parts:             List[str]
    recommended_labor_codes:    List[str]
    urgency:                    Optional[str]
    urgency_reason:             Optional[str]
    intake_confidence:          float
    recall_action_required:     bool
    technician_skill_required:  Optional[str]
    ev_safety_protocol:         bool
    intake_notes:               Optional[str]
    is_ev_job:                  bool

    # ── AGENT 2 — INVENTORY ───────────────────────────────────────────────
    inventory_check:    Dict
    parts_available:    bool
    reserved_parts:     List[Dict]
    unavailable_parts:  List[str]
    reorder_needed:     List[str]

    # ── AGENT 3 — QUOTING ─────────────────────────────────────────────────
    quote:              Optional[Dict]
    quote_id:           Optional[str]
    oem_quote:          Optional[Dict]
    aftermarket_quote:  Optional[Dict]
    requires_approval:  bool
    approval_reason:    Optional[str]
    discount_rate:      float
    discount_reason:    Optional[str]

    # ── AGENT 4 — TRANSACTION ─────────────────────────────────────────────
    transaction_status: Optional[str]
    approved_by:        Optional[str]
    human_approved:     bool
    hitl_triggered:     bool
    approval_method:    Optional[str]
    approval_notes:     Optional[str]
    rejection_reason:   Optional[str]

    # ── AGENT 5 — REPLENISHMENT ───────────────────────────────────────────
    pos_raised:         List[Dict]
    reorder_summary:    Optional[str]
    total_po_value:     float

    # ── INTAKE HITL — SUPERVISOR OVERRIDE ────────────────────────────────
    # Populated when intake agent can't identify parts
    # Supervisor fills in via dashboard form
    intake_hitl_triggered:          bool
    supervisor_override:            bool
    supervisor_parts:               List[str]        # part numbers from catalog
    supervisor_custom_materials:    List[Dict]       # [{"description": "Silver paint", "cost": 3500}]
    supervisor_labor_description:   Optional[str]    # e.g. "Dent repair and respray"
    supervisor_labor_hours:         Optional[float]  # e.g. 4.0
    supervisor_labor_rate:          Optional[float]  # per hour, defaults to standard rate
    inspection_only:                bool             # True = diagnostic quote only
    supervisor_id:                  Optional[str]    # who made the override decision
    supervisor_notes:               Optional[str]    # any additional notes
    supervisor_complaint_override:  Optional[str]    # refined complaint / diagnosis for re-triage

    # ── META ──────────────────────────────────────────────────────────────
    current_agent:      Optional[str]
    error:              Optional[str]


# ── INTAKE HITL NODE ─────────────────────────────────────────────────────────

def run_intake_hitl(state: CONDUITState) -> CONDUITState:
    """
    Pauses pipeline when Intake Agent cannot identify parts.

    Triggers when:
        - confidence < 0.70 (ambiguous complaint)
        - required_parts = [] (unknown fault / body work / paint)

    Supervisor sees in dashboard:
        - Vehicle details
        - Complaint text
        - What the agent understood (fault classification if any)
        - Form to enter: parts from catalog, custom materials, labor details

    On resume, supervisor input is injected into state and pipeline
    continues from inventory onwards as normal.

    Option C implementation:
        supervisor_parts           → catalog parts (tracked in inventory)
        supervisor_custom_materials → paint, compound, sundries (not tracked)
        supervisor_labor_*          → manual labor entry
        inspection_only=True        → diagnostic quote only, no parts
    """
    try:
        from langgraph.types import interrupt

        vehicle   = state.get("vehicle_details", {}) or {}
        complaint = state.get("complaint_text", "")
        fault     = state.get("fault_classification", "UNKNOWN")
        confidence = state.get("intake_confidence", 0.0)
        ro_id     = state.get("ro_id")

        # Pause pipeline — waits for supervisor input via dashboard
        decision = interrupt({
            "ro_id":       ro_id,
            "trigger":     "intake_hitl",
            "message":     (
                f"Agent could not identify parts with sufficient confidence "
                f"({confidence:.0%}). Supervisor review required."
            ),
            "vehicle":     f"{vehicle.get('year')} {vehicle.get('make')} {vehicle.get('model')}",
            "complaint":   complaint,
            "agent_fault": fault,
            "form_fields": [
                "supervisor_parts",
                "supervisor_custom_materials",
                "supervisor_labor_description",
                "supervisor_labor_hours",
                "inspection_only",
                "supervisor_notes",
                "supervisor_complaint_override",
            ],
        })

        # Merge supervisor input into state
        return {
            **state,
            "supervisor_override":           True,
            "intake_hitl_triggered":         True,
            "supervisor_id":                 decision.get("supervisor_id"),
            "supervisor_parts":              decision.get("supervisor_parts", []),
            "supervisor_custom_materials":   decision.get("supervisor_custom_materials", []),
            "supervisor_labor_description":  decision.get("supervisor_labor_description"),
            "supervisor_labor_hours":        decision.get("supervisor_labor_hours"),
            "supervisor_labor_rate":         decision.get("supervisor_labor_rate"),
            "inspection_only":               decision.get("inspection_only", False),
            "supervisor_notes":              decision.get("supervisor_notes"),

                        # Optional: supervisor can refine complaint/dx and re-run Intake.
                        "supervisor_complaint_override":  decision.get("supervisor_complaint_override"),
                        "complaint_text":                 (
                                                                                                decision.get("supervisor_complaint_override")
                                                                                                or state.get("complaint_text")
                                                                                            ),

            # Override required_parts with supervisor selection
            # Downstream agents use required_parts normally
            "required_parts": decision.get("supervisor_parts", []),

            "current_agent": "intake_hitl",
        }

    except ImportError:
        # Standalone test — no LangGraph interrupt available
        # Auto-fill with empty supervisor input and continue
        return {
            **state,
            "supervisor_override":   True,
            "intake_hitl_triggered": True,
            "supervisor_parts":      [],
            "supervisor_custom_materials": [],
            "inspection_only":       False,
            "required_parts":        [],
            "current_agent":         "intake_hitl",
        }


# ── ROUTING FUNCTIONS ─────────────────────────────────────────────────────────

def route_after_intake(state: CONDUITState) -> str:
    """
    After Intake Agent:
    - Error             → end
    - Low confidence    → intake_hitl (supervisor review)
    - No parts found    → intake_hitl (supervisor review)
    - HITL disabled     → inventory (skip hitl regardless)
    - Normal            → inventory
    """
    if state.get("error"):
        return "end"

    if not INTAKE_HITL_ENABLED:
        return "inventory"

    confidence    = state.get("intake_confidence", 1.0)
    required_parts = state.get("required_parts", [])
    fault         = state.get("fault_classification", "UNKNOWN")

    # Trigger HITL for ambiguous or unidentified cases
    if confidence < 0.70:
        return "intake_hitl"

    if not required_parts:
        return "intake_hitl"

    if fault == "UNKNOWN":
        return "intake_hitl"

    return "inventory"


def route_after_inventory(state: CONDUITState) -> str:
    """
    After Inventory Agent:
    - Error → END
    - Always → quoting (quoting handles empty parts gracefully)
    """
    if state.get("error"):
        return "end"

    return "quoting"


def route_after_quoting(state: CONDUITState) -> str:
    """
    After Quoting Agent:
    - Error → END
    - Success → transaction
    """
    if state.get("error"):
        return "end"

    return "transaction"


def route_after_transaction(state: CONDUITState) -> str:
    """
    After Transaction Agent:
    - Error → END
    - Rejected → END (reservations already released)
    - Approved → replenishment (check reorder flags)
    """
    if state.get("error"):
        return "end"

    if state.get("transaction_status") == "REJECTED":
        return "end"

    return "replenishment"


def route_after_replenishment(state: CONDUITState) -> str:
    """Always end after replenishment."""
    return "end"


# ── BUILD GRAPH ───────────────────────────────────────────────────────────────

def build_graph(use_memory_checkpointer: bool = True):
    """
    Builds and compiles the LangGraph StateGraph.

    use_memory_checkpointer=True  → in-memory (testing, no DB needed)
    use_memory_checkpointer=False → PostgreSQL (production, HITL support)
    """

    # Initialise graph with state schema
    graph = StateGraph(CONDUITState)

    # ── ADD NODES ─────────────────────────────────────────────────────────
    graph.add_node("intake",        run_intake_agent)
    graph.add_node("intake_hitl",   run_intake_hitl)
    graph.add_node("inventory",     run_inventory_agent)
    graph.add_node("quoting",       run_quoting_agent)
    graph.add_node("transaction",   run_transaction_agent)
    graph.add_node("replenishment", run_replenishment_agent)

    # ── SET ENTRY POINT ───────────────────────────────────────────────────
    graph.set_entry_point("intake")

    # ── ADD EDGES ─────────────────────────────────────────────────────────
    # intake → intake_hitl or inventory (conditional)
    graph.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "intake_hitl": "intake_hitl",
            "inventory":   "inventory",
            "end":         END,
        }
    )

    # intake_hitl → intake (if supervisor provided refined complaint) OR inventory
    def route_after_intake_hitl(state: CONDUITState) -> str:
        override = (state.get("supervisor_complaint_override") or "").strip()
        if override:
            return "intake"
        return "inventory"

    graph.add_conditional_edges(
        "intake_hitl",
        route_after_intake_hitl,
        {
            "intake":     "intake",
            "inventory":  "inventory",
        }
    )

    # inventory → quoting or end (conditional)
    graph.add_conditional_edges(
        "inventory",
        route_after_inventory,
        {
            "quoting": "quoting",
            "end":     END,
        }
    )

    # quoting → transaction or end (conditional)
    graph.add_conditional_edges(
        "quoting",
        route_after_quoting,
        {
            "transaction": "transaction",
            "end":         END,
        }
    )

    # transaction → replenishment or end (conditional)
    graph.add_conditional_edges(
        "transaction",
        route_after_transaction,
        {
            "replenishment": "replenishment",
            "end":           END,
        }
    )

    # replenishment → END (always)
    graph.add_edge("replenishment", END)

    # ── COMPILE WITH CHECKPOINTER ─────────────────────────────────────────
    if use_memory_checkpointer:
        checkpointer = MemorySaver()
    else:
        # PostgreSQL checkpointer for production HITL support
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            checkpointer = PostgresSaver.from_conn_string(DATABASE_URL)
        except Exception:
            # Fall back to memory if postgres checkpointer unavailable
            checkpointer = MemorySaver()

    compiled = graph.compile(checkpointer=checkpointer)
    return compiled


# ── THREAD CONFIG ─────────────────────────────────────────────────────────────

def get_thread_config(ro_id: str) -> dict:
    """
    Returns LangGraph thread config for a given RO.
    Thread ID = RO ID — each RO is its own isolated pipeline run.
    Used for checkpointing and HITL resume.
    """
    return {"configurable": {"thread_id": ro_id}}


# ── PUBLIC API ────────────────────────────────────────────────────────────────

# Single compiled graph instance — reused across all requests
_graph = None

def get_graph():
    """Returns singleton compiled graph."""
    global _graph
    if _graph is None:
        use_memory = not HITL_ENABLED
        _graph = build_graph(use_memory_checkpointer=use_memory)
    return _graph


def run_pipeline(
    ro_id:          str,
    vin:            str,
    complaint_text: str,
    customer_id:    Optional[str] = None,
) -> Dict[str, Any]:
    """
    Runs the full CONDUIT pipeline for a new repair order.

    Args:
        ro_id:          Repair order ID (must exist in repair_orders table)
        vin:            Vehicle VIN
        complaint_text: Raw complaint from service advisor
        customer_id:    Optional customer ID for loyalty lookup

    Returns:
        Final pipeline state dict with all agent outputs
    """
    graph  = get_graph()
    config = get_thread_config(ro_id)

    initial_state: CONDUITState = {
        "ro_id":          ro_id,
        "vin":            vin,
        "complaint_text": complaint_text,
        "customer_id":    customer_id,

        # Initialise list/dict fields to avoid None errors
        "recall_flags":             [],
        "retrieved_parts_context":  [],
        "required_parts":           [],
        "recommended_labor_codes":  [],
        "reserved_parts":           [],
        "unavailable_parts":        [],
        "reorder_needed":           [],
        "pos_raised":               [],
        "inventory_check":          {},
        "recall_action_required":   False,
        "ev_safety_protocol":       False,
        "is_ev_job":                False,
        "parts_available":          True,
        "intake_confidence":        0.0,
        "discount_rate":            0.0,
        "human_approved":           False,
        "hitl_triggered":           False,
        "intake_hitl_triggered":    False,
        "supervisor_override":      False,
        "supervisor_parts":         [],
        "supervisor_custom_materials": [],
        "inspection_only":          False,
        "total_po_value":           0.0,
        "error":                    None,
        "current_agent":            None,
    }

    result = graph.invoke(initial_state, config=config)
    return result


def run_pipeline_streaming(
    ro_id:          str,
    vin:            str,
    complaint_text: str,
    customer_id:    Optional[str] = None,
):
    """
    Streaming version of run_pipeline.
    Yields state snapshots after each agent completes.
    Used by FastAPI StreamingResponse for real-time SSE.

    Each yield is a dict:
        {
            "agent":   "intake_agent",
            "status":  "complete",
            "data":    { ...agent output fields... },
            "elapsed": 8.2,
        }

    Usage in FastAPI:
        async def stream():
            for event in run_pipeline_streaming(...):
                yield f"data: {json.dumps(event)}\\n\\n"
        return StreamingResponse(stream(), media_type="text/event-stream")
    """
    import time

    # Build initial state — same as run_pipeline
    initial_state: CONDUITState = {
        "ro_id":          ro_id,
        "vin":            vin,
        "complaint_text": complaint_text,
        "customer_id":    customer_id,
        "recall_flags":             [],
        "retrieved_parts_context":  [],
        "required_parts":           [],
        "recommended_labor_codes":  [],
        "reserved_parts":           [],
        "unavailable_parts":        [],
        "reorder_needed":           [],
        "pos_raised":               [],
        "inventory_check":          {},
        "recall_action_required":   False,
        "ev_safety_protocol":       False,
        "is_ev_job":                False,
        "parts_available":          True,
        "intake_confidence":        0.0,
        "discount_rate":            0.0,
        "human_approved":           False,
        "hitl_triggered":           False,
        "intake_hitl_triggered":    False,
        "supervisor_override":      False,
        "supervisor_parts":         [],
        "supervisor_custom_materials": [],
        "inspection_only":          False,
        "total_po_value":           0.0,
        "error":                    None,
        "current_agent":            None,
    }

    # Run agents manually in sequence
    # This gives us control to yield between each step
    pipeline_start = time.time()
    state          = initial_state

    agent_sequence = [
        ("intake_agent",        run_intake_agent,        "Classifying fault + identifying parts"),
        ("inventory_agent",     run_inventory_agent,     "Checking stock + reserving parts"),
        ("quoting_agent",       run_quoting_agent,       "Building OEM + aftermarket quotes"),
        ("transaction_agent",   run_transaction_agent,   "Processing approval + confirming"),
        ("replenishment_agent", run_replenishment_agent, "Checking reorder + raising POs"),
    ]

    for agent_name, agent_fn, description in agent_sequence:
        agent_start = time.time()

        pending_hitl_required: dict | None = None

        # Yield "running" event so dashboard shows spinner for this agent
        yield {
            "event":       "agent_running",
            "agent":       agent_name,
            "description": description,
            "elapsed":     round(time.time() - pipeline_start, 1),
        }

        # Run the agent — hard 60 s wall-clock timeout so a slow
        # OpenAI / Pinecone call can never hang the pipeline forever.
        #
        # IMPORTANT: do NOT use `with ThreadPoolExecutor` here.
        # Its __exit__ calls shutdown(wait=True), which blocks until the
        # submitted thread finishes — completely defeating the timeout.
        # We call shutdown(wait=False) explicitly to abandon stuck threads.
        import concurrent.futures as _cf
        _ex = _cf.ThreadPoolExecutor(max_workers=1)
        try:
            fut   = _ex.submit(agent_fn, state)
            state = fut.result(timeout=60)

            if agent_name == "intake_agent":
                # Check if we need to pause for intake HITL
                confidence     = state.get("intake_confidence", 1.0)
                required_parts = state.get("required_parts", [])
                fault          = state.get("fault_classification", "UNKNOWN")

                if (
                    confidence < 0.70 or
                    not required_parts or
                    fault == "UNKNOWN"
                ):
                    msg = (
                        f"Low confidence ({confidence:.0%}) — human inspection recommended"
                        if not INTAKE_HITL_ENABLED
                        else f"Low confidence ({confidence:.0%}) — supervisor review required"
                    )
                    pending_hitl_required = {
                        "event":   "hitl_required",
                        "agent":   "intake_hitl",
                        "message": msg,
                        "elapsed": round(time.time() - pipeline_start, 1),
                    }

        except _cf.TimeoutError:
            _ex.shutdown(wait=False)  # abandon the stuck thread — do NOT wait=True
            yield {
                "event":   "agent_error",
                "agent":   agent_name,
                "error":   f"{agent_name} timed out after 60 s — OpenAI or Pinecone may be slow. Please retry.",
                "elapsed": round(time.time() - pipeline_start, 1),
            }
            return
        except Exception as e:
            _ex.shutdown(wait=False)
            yield {
                "event":   "agent_error",
                "agent":   agent_name,
                "error":   str(e),
                "elapsed": round(time.time() - pipeline_start, 1),
            }
            return
        else:
            _ex.shutdown(wait=False)

        agent_elapsed = round(time.time() - agent_start, 1)

        # Build per-agent summary for the event
        summary = _build_agent_summary(agent_name, state)

        # Yield "complete" event with agent output
        yield {
            "event":       "agent_complete",
            "agent":       agent_name,
            "description": description,
            "elapsed_agent":    agent_elapsed,
            "elapsed_total":    round(time.time() - pipeline_start, 1),
            "summary":     summary,
            "error":       state.get("error"),
        }

        # If intake was ambiguous, emit HITL/inspection notification AFTER
        # marking intake complete — avoids UI looking like it stopped abruptly.
        if pending_hitl_required:
            yield pending_hitl_required
            return  # Stop streaming — ambiguous case should not be auto-quoted

        # Stop pipeline if error occurred
        if state.get("error"):
            return

        # Stop after transaction if rejected
        if agent_name == "transaction_agent":
            if state.get("transaction_status") == "REJECTED":
                break

    # Final event — complete pipeline with full state
    # Include a minimal PO breakdown for demo UX (explains large PO totals).
    pos_min = []
    for po in state.get("pos_raised", []) or []:
        parts = []
        for p in (po.get("parts") or []):
            parts.append({
                "part_number":    p.get("part_number"),
                "description":    p.get("description"),
                "order_quantity": p.get("order_quantity"),
                "unit_cost":      p.get("unit_cost"),
                "order_value":    p.get("order_value"),
            })

        pos_min.append({
            "po_id":         po.get("po_id"),
            "supplier_id":   po.get("supplier_id"),
            "supplier_name": po.get("supplier_name"),
            "parts_count":   po.get("parts_count"),
            "total_value":   po.get("total_value"),
            "status":        po.get("status"),
            "parts":         parts,
        })

    yield {
        "event":         "pipeline_complete",
        "total_elapsed": round(time.time() - pipeline_start, 1),
        "ro_id":         ro_id,
        "fault":         state.get("fault_classification"),
        "urgency":       state.get("urgency"),
        "confidence":    state.get("intake_confidence"),
        "required_parts":    state.get("required_parts", []),
        "parts_available":   state.get("parts_available"),
        "quote_id":          state.get("quote_id"),
        "transaction_status": state.get("transaction_status"),
        "approved_by":       state.get("approved_by"),
        "reorder_summary":   state.get("reorder_summary"),
        "pos_count":         len(state.get("pos_raised", [])),
        "pos_raised":        pos_min,
        "quote":             state.get("quote"),
        "oem_quote":         state.get("oem_quote"),
        "aftermarket_quote": state.get("aftermarket_quote"),
        "is_ev_job":         state.get("is_ev_job"),
        "recall_action_required": state.get("recall_action_required"),
        "error":             state.get("error"),
    }


def _build_agent_summary(agent_name: str, state: dict) -> dict:
    """Extracts relevant fields per agent for SSE event summary."""
    if agent_name == "intake_agent":
        return {
            "fault":      state.get("fault_classification"),
            "urgency":    state.get("urgency"),
            "confidence": state.get("intake_confidence"),
            "parts":      state.get("required_parts", []),
            "is_ev":      state.get("is_ev_job"),
            "recall":     state.get("recall_action_required"),
        }
    elif agent_name == "inventory_agent":
        return {
            "reserved":   len(state.get("reserved_parts", [])),
            "unavailable": state.get("unavailable_parts", []),
            "available":  state.get("parts_available"),
            "reorder":    state.get("reorder_needed", []),
        }
    elif agent_name == "quoting_agent":
        quote = state.get("quote", {}) or {}
        return {
            "quote_id":    state.get("quote_id"),
            "total":       quote.get("total_amount"),
            "discount":    quote.get("discount_amount"),
            "has_am":      state.get("aftermarket_quote") is not None,
        }
    elif agent_name == "transaction_agent":
        return {
            "status":      state.get("transaction_status"),
            "approved_by": state.get("approved_by"),
            "hitl":        state.get("hitl_triggered"),
        }
    elif agent_name == "replenishment_agent":
        return {
            "pos_raised":    len(state.get("pos_raised", [])),
            "total_po_value": state.get("total_po_value", 0),
            "summary":       state.get("reorder_summary"),
        }
    return {}


def resume_pipeline(
    ro_id:      str,
    approved:   bool,
    advisor_id: str,
    notes:      str = "",
) -> Dict[str, Any]:
    """
    Resumes a HITL-paused pipeline after human decision.
    Only relevant when HITL_ENABLED=true.

    Args:
        ro_id:      RO ID of the paused pipeline
        approved:   True = approve quote, False = reject
        advisor_id: ID of the service advisor making decision
        notes:      Optional approval/rejection notes

    Returns:
        Final pipeline state after completion
    """
    graph  = get_graph()
    config = get_thread_config(ro_id)

    result = graph.invoke(
        input={
            "approved":   approved,
            "advisor_id": advisor_id,
            "notes":      notes,
        },
        config=config,
    )

    return result


def resume_intake_hitl(
    ro_id:                      str,
    supervisor_id:              str,
    supervisor_parts:           list   = None,
    supervisor_custom_materials: list  = None,
    supervisor_labor_description: str  = None,
    supervisor_labor_hours:     float  = None,
    supervisor_labor_rate:      float  = None,
    inspection_only:            bool   = False,
    supervisor_notes:           str    = "",
    supervisor_complaint_override: str  = None,
) -> Dict[str, Any]:
    """
    Resumes an intake-HITL paused pipeline with supervisor input.

    Since stream_pipeline runs agents manually (not via graph.invoke),
    no LangGraph checkpoint exists for the paused state. Instead, we
    look up the original RO from the database to get the VIN and
    complaint, then re-run the full pipeline using the supervisor's
    override as the updated complaint text.

    Args:
        ro_id:                       RO ID of the paused pipeline
        supervisor_id:               ID of the supervisor making decision
        supervisor_complaint_override: Supervisor's diagnosis/finding
        supervisor_notes:            Any additional notes

    Returns:
        Final pipeline state after completion
    """
    from database.connection import get_session
    from database.models import RepairOrder

    # Look up original RO to get VIN and customer_id
    with get_session() as db:
        ro = db.query(RepairOrder).filter(RepairOrder.ro_id == ro_id).first()
        if not ro:
            raise ValueError(f"Repair order {ro_id} not found in database")
        vin         = ro.vin
        customer_id = ro.customer_id

    # Use supervisor's override as the updated complaint
    updated_complaint = supervisor_complaint_override or ro.complaint_text

    # Build the full initial state with supervisor overrides
    initial_state: CONDUITState = {
        "ro_id":          ro_id,
        "vin":            vin,
        "complaint_text": updated_complaint,
        "customer_id":    str(customer_id) if customer_id else None,

        # Supervisor override fields
        "supervisor_override":        True,
        "supervisor_id":              supervisor_id,
        "supervisor_parts":           supervisor_parts or [],
        "supervisor_custom_materials": supervisor_custom_materials or [],
        "supervisor_labor_description": supervisor_labor_description,
        "supervisor_labor_hours":     supervisor_labor_hours,
        "supervisor_labor_rate":      supervisor_labor_rate,
        "inspection_only":            inspection_only,
        "supervisor_notes":           supervisor_notes,
        "supervisor_complaint_override": supervisor_complaint_override,

        # Initialise all required fields
        "recall_flags":             [],
        "retrieved_parts_context":  [],
        "required_parts":           [],
        "recommended_labor_codes":  [],
        "reserved_parts":           [],
        "unavailable_parts":        [],
        "reorder_needed":           [],
        "pos_raised":               [],
        "inventory_check":          {},
        "recall_action_required":   False,
        "ev_safety_protocol":       False,
        "is_ev_job":                False,
        "parts_available":          True,
        "intake_confidence":        0.0,
        "discount_rate":            0.0,
        "human_approved":           False,
        "hitl_triggered":           True,
        "intake_hitl_triggered":    True,
        "error":                    None,
        "current_agent":            None,
    }

    # Run the full pipeline from intake using the supervisor's complaint
    graph  = get_graph()
    config = get_thread_config(f"{ro_id}-resume")

    result = graph.invoke(
        input=initial_state,
        config=config,
    )

    return result




if __name__ == "__main__":

    print("\n" + "="*55)
    print("   CONDUIT — Full Pipeline Test")
    print("="*55)
    print(f"HITL Enabled: {HITL_ENABLED}")

    # Pull a real VIN from DB
    from database.connection import get_session
    from database.models import Vehicle, RepairOrder
    import uuid

    with get_session() as db:
        vehicle = db.query(Vehicle).filter(
            Vehicle.is_ev == False
        ).first()

    if not vehicle:
        print("No vehicles found — run generate_all.py first")
        sys.exit(1)

    # Create a test RO in DB first
    test_ro_id = f"RO-TEST-FULL-{str(uuid.uuid4())[:6].upper()}"

    with get_session() as db:
        ro = RepairOrder(
            ro_id          = test_ro_id,
            vin            = vehicle.vin,
            complaint_text = "grinding noise from front when braking, car pulls left",
            status         = "OPEN",
            vehicle_make   = vehicle.make,
            vehicle_model  = vehicle.model,
            vehicle_year   = vehicle.year,
        )
        db.add(ro)
        db.commit()

    print(f"\nVehicle:   {vehicle.year} {vehicle.make} {vehicle.model}")
    print(f"VIN:       {vehicle.vin}")
    print(f"RO ID:     {test_ro_id}")
    print(f"Complaint: grinding noise from front when braking\n")
    print("Running pipeline...\n")

    result = run_pipeline(
        ro_id          = test_ro_id,
        vin            = vehicle.vin,
        complaint_text = "grinding noise from front when braking, car pulls left",
    )

    # ── PRINT RESULTS ─────────────────────────────────────────────────────
    print("\n" + "="*55)
    print("   PIPELINE RESULTS")
    print("="*55)

    if result.get("error"):
        print(f"\n❌ Pipeline Error: {result['error']}")
    else:
        print(f"\n{'Field':<28} {'Value'}")
        print("-"*55)

        fields = [
            ("Fault Classification",  "fault_classification"),
            ("Urgency",               "urgency"),
            ("Confidence",            "intake_confidence"),
            ("Required Parts",        "required_parts"),
            ("Parts Available",       "parts_available"),
            ("Reserved Parts",        "reserved_parts"),
            ("Quote ID",              "quote_id"),
            ("Transaction Status",    "transaction_status"),
            ("Approved By",           "approved_by"),
            ("HITL Triggered",        "hitl_triggered"),
            ("Intake HITL Triggered", "intake_hitl_triggered"),
            ("Supervisor Override",   "supervisor_override"),
            ("POs Raised",            "pos_raised"),
            ("Reorder Summary",       "reorder_summary"),
        ]

        for label, key in fields:
            value = result.get(key)

            if key == "required_parts":
                value = value or []
                print(f"  {label:<26} {value}")

            elif key == "reserved_parts":
                value = value or []
                print(f"  {label:<26} {len(value)} parts reserved")

            elif key == "pos_raised":
                value = value or []
                print(f"  {label:<26} {len(value)} PO(s)")

            elif key == "intake_confidence":
                print(f"  {label:<26} {value:.0%}" if value else
                      f"  {label:<26} N/A")

            else:
                print(f"  {label:<26} {value}")

        # Quote summary
        quote = result.get("quote", {})
        if quote:
            print(f"\n{'─'*55}")
            print(f"  {'QUOTE SUMMARY':^53}")
            print(f"{'─'*55}")
            print(f"  {'Subtotal':<28} ₹{quote.get('subtotal', 0):>10,.0f}")
            print(f"  {'Discount':<28} -₹{quote.get('discount_amount', 0):>9,.0f}")
            print(f"  {'GST (18%)':<28} ₹{quote.get('gst_amount', 0):>10,.0f}")
            print(f"{'─'*55}")
            print(f"  {'TOTAL':<28} ₹{quote.get('total_amount', 0):>10,.0f}")
            print(f"{'─'*55}")

        if result.get("aftermarket_quote"):
            am = result["aftermarket_quote"]
            saving = quote.get("total_amount", 0) - am.get("total_amount", 0)
            print(f"\n  Aftermarket Option:          "
                  f"₹{am.get('total_amount', 0):>10,.0f}")
            print(f"  Customer Saving:             "
                  f"₹{saving:>10,.0f}")

    print(f"\n{'='*55}\n")