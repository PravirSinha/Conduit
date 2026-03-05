"""
CONDUIT — Repair Orders Router
================================
Core endpoints for creating and managing repair orders.
"""

import json
import uuid
from fastapi.responses import StreamingResponse

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import RepairOrder, Vehicle
from api.schemas import (
    CreateRORequest,
    ApproveQuoteRequest,
    RejectQuoteRequest,
    IntakeReviewRequest,
    ROResponse,
    ROListItem,
)
from config import ADVISOR_PIN
from app_logging.logger import get_logger

logger = get_logger("conduit.api")
router = APIRouter(prefix="/repair-orders", tags=["Repair Orders"])


# ── HELPERS ───────────────────────────────────────────────────────────────────

def verify_pin(pin: str) -> bool:
    """Validates advisor PIN for HITL approval."""
    return pin == ADVISOR_PIN


def build_ro_response(state: dict, db: Session) -> ROResponse:
    """Builds ROResponse from pipeline state dict."""

    vehicle_details = state.get("vehicle_details")
    vehicle_resp    = None

    if vehicle_details:
        from api.schemas import VehicleResponse
        vehicle_resp = VehicleResponse(
            vin              = vehicle_details.get("vin", ""),
            make             = vehicle_details.get("make", ""),
            model            = vehicle_details.get("model", ""),
            year             = vehicle_details.get("year", 0),
            fuel_type        = vehicle_details.get("fuel_type"),
            is_ev            = vehicle_details.get("is_ev", False),
            odometer_km      = vehicle_details.get("odometer_km"),
            warranty_expired = vehicle_details.get("warranty_expired", False),
        )

    quote_details = state.get("quote")
    quote_resp    = None

    if quote_details:
        from api.schemas import QuoteSummary
        quote_resp = QuoteSummary(
            quote_id        = state.get("quote_id", ""),
            subtotal        = quote_details.get("subtotal", 0),
            discount_amount = quote_details.get("discount_amount", 0),
            gst_amount      = quote_details.get("gst_amount", 0),
            total_amount    = quote_details.get("total_amount", 0),
            status          = "APPROVED" if state.get("human_approved") else "PENDING",
        )

    return ROResponse(
        ro_id                  = state.get("ro_id", ""),
        vin                    = state.get("vin", ""),
        customer_name          = state.get("customer_details", {}).get("full_name") if state.get("customer_details") else None,
        fault_classification   = state.get("fault_classification"),
        urgency                = state.get("urgency"),
        intake_confidence      = state.get("intake_confidence"),
        required_parts         = state.get("required_parts", []),
        parts_available        = state.get("parts_available"),
        quote_id               = state.get("quote_id"),
        transaction_status     = state.get("transaction_status"),
        approved_by            = state.get("approved_by"),
        status                 = state.get("transaction_status", "OPEN") or "OPEN",
        is_ev_job              = state.get("is_ev_job", False),
        recall_action_required = state.get("recall_action_required"),
        hitl_triggered         = state.get("hitl_triggered"),
        intake_hitl_triggered  = state.get("intake_hitl_triggered"),
        supervisor_override    = state.get("supervisor_override"),
        reorder_summary        = state.get("reorder_summary"),
        error                  = state.get("error"),
        vehicle                = vehicle_resp,
        quote                  = quote_resp,
        oem_quote              = state.get("oem_quote"),
        aftermarket_quote      = state.get("aftermarket_quote"),
    )


# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=ROResponse)
def create_repair_order(
    request:    CreateRORequest,
    background: BackgroundTasks,
    db:         Session = Depends(get_db),
):
    """
    Creates a new repair order and runs the full CONDUIT pipeline.

    Steps:
        1. Validate VIN exists in vehicles table
        2. Create RO record in PostgreSQL
        3. Run pipeline (intake → inventory → quoting → transaction → replenishment)
        4. Return final state as ROResponse
    """

    # Validate VIN exists
    vehicle = db.query(Vehicle).filter(
        Vehicle.vin == request.vin.upper().strip()
    ).first()

    if not vehicle:
        raise HTTPException(
            status_code = 404,
            detail      = f"VIN {request.vin} not found in vehicle catalog"
        )

    # Create RO record
    ro_id = f"RO-{str(uuid.uuid4())[:8].upper()}"

    ro = RepairOrder(
        ro_id          = ro_id,
        vin            = vehicle.vin,
        complaint_text = request.complaint_text,
        customer_id    = request.customer_id,
        status         = "OPEN",
        vehicle_make   = vehicle.make,
        vehicle_model  = vehicle.model,
        vehicle_year   = vehicle.year,
        vehicle_fuel_type = vehicle.fuel_type,
        is_ev_job      = vehicle.is_ev,
    )
    db.add(ro)
    db.commit()

    logger.info({
        "event":  "ro_created",
        "ro_id":  ro_id,
        "vin":    vehicle.vin,
    })

    # Run pipeline
    try:
        from orchestrator import run_pipeline

        state = run_pipeline(
            ro_id          = ro_id,
            vin            = vehicle.vin,
            complaint_text = request.complaint_text,
            customer_id    = request.customer_id,
        )

        return build_ro_response(state, db)

    except Exception:
        logger.error({
            "event": "pipeline_error",
            "ro_id": ro_id,
            "error": str(e),
        })
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
def create_repair_order_stream(
    request: CreateRORequest,
    db:      Session = Depends(get_db),
):
    """
    Streaming version of create_repair_order.
    Returns Server-Sent Events (SSE) — one event per agent completion.
    Dashboard reads this stream to show real-time pipeline progress.

    SSE format:
        data: {"event": "agent_running", "agent": "intake_agent", ...}\n\n
        data: {"event": "agent_complete", "agent": "intake_agent", ...}\n\n
        data: {"event": "pipeline_complete", ...}\n\n
    """

    # Validate VIN
    vehicle = db.query(Vehicle).filter(
        Vehicle.vin == request.vin.upper().strip()
    ).first()

    if not vehicle:
        def error_stream():
            yield f"data: {json.dumps({'event': 'error', 'message': f'VIN {request.vin} not found'})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    # Create RO
    ro_id = f"RO-{str(uuid.uuid4())[:8].upper()}"

    ro = RepairOrder(
        ro_id             = ro_id,
        vin               = vehicle.vin,
        complaint_text    = request.complaint_text,
        customer_id       = request.customer_id,
        status            = "OPEN",
        vehicle_make      = vehicle.make,
        vehicle_model     = vehicle.model,
        vehicle_year      = vehicle.year,
        vehicle_fuel_type = vehicle.fuel_type,
        is_ev_job         = vehicle.is_ev,
    )
    db.add(ro)
    db.commit()

    # Stream pipeline events
    def event_stream():
        # First event — RO created
        yield f"data: {json.dumps({'event': 'ro_created', 'ro_id': ro_id})}\n\n"

        try:
            from orchestrator import run_pipeline_streaming

            for event in run_pipeline_streaming(
                ro_id          = ro_id,
                vin            = vehicle.vin,
                complaint_text = request.complaint_text,
                customer_id    = request.customer_id,
            ):
                yield f"data: {json.dumps(event, default=str)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type = "text/event-stream",
        headers    = {
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        }
    )


@router.get("/", response_model=List[ROListItem])
def list_repair_orders(
    status: Optional[str] = None,
    limit:  int           = 50,
    offset: int           = 0,
    db:     Session       = Depends(get_db),
):
    """Lists repair orders with optional status filter."""
    query = db.query(RepairOrder)

    if status:
        query = query.filter(RepairOrder.status == status.upper())

    ros = query.order_by(
        RepairOrder.created_at.desc()
    ).offset(offset).limit(limit).all()

    return [
        ROListItem(
            ro_id                = ro.ro_id,
            vin                  = ro.vin,
            customer_name        = ro.customer_name,
            vehicle_make         = ro.vehicle_make,
            vehicle_model        = ro.vehicle_model,
            vehicle_year         = ro.vehicle_year,
            fault_classification = ro.fault_category,
            urgency              = ro.classification_payload.get("urgency") if ro.classification_payload else None,
            status               = ro.status,
            final_total          = float(ro.final_total) if ro.final_total else None,
            opened_at            = ro.opened_at,
        )
        for ro in ros
    ]


@router.get("/pending-approval", response_model=List[ROListItem])
def list_pending_approval(db: Session = Depends(get_db)):
    """Lists ROs currently waiting for HITL approval — deduped by ro_id."""
    ros = db.query(RepairOrder).filter(
        RepairOrder.status.in_(["QUOTED", "PENDING_INSPECTION"])
    ).distinct(RepairOrder.ro_id).order_by(
        RepairOrder.ro_id,
        RepairOrder.created_at.desc()
    ).all()

    return [
        ROListItem(
            ro_id                = ro.ro_id,
            vin                  = ro.vin,
            customer_name        = ro.customer_name,
            vehicle_make         = ro.vehicle_make,
            vehicle_model        = ro.vehicle_model,
            vehicle_year         = ro.vehicle_year,
            fault_classification = ro.fault_category,
            urgency              = ro.classification_payload.get("urgency") if ro.classification_payload else None,
            status               = ro.status,
            final_total          = float(ro.final_total) if ro.final_total else None,
            opened_at            = ro.opened_at,
        )
        for ro in ros
    ]


@router.get("/{ro_id}", response_model=ROListItem)
def get_repair_order(ro_id: str, db: Session = Depends(get_db)):
    """Gets a single repair order by ID."""
    ro = db.query(RepairOrder).filter(
        RepairOrder.ro_id == ro_id
    ).first()

    if not ro:
        raise HTTPException(status_code=404, detail=f"RO {ro_id} not found")

    return ROListItem(
        ro_id                = ro.ro_id,
        vin                  = ro.vin,
        customer_name        = ro.customer_name,
        vehicle_make         = ro.vehicle_make,
        vehicle_model        = ro.vehicle_model,
        vehicle_year         = ro.vehicle_year,
        fault_classification = ro.fault_category,
        urgency              = ro.classification_payload.get("urgency") if ro.classification_payload else None,
        status               = ro.status,
        final_total          = float(ro.final_total) if ro.final_total else None,
        opened_at            = ro.opened_at,
    )


@router.post("/{ro_id}/approve")
def approve_quote(
    ro_id:   str,
    request: ApproveQuoteRequest,
    db:      Session = Depends(get_db),
):
    """
    HITL — Approves a quote for a paused repair order.
    Requires valid advisor PIN.
    Resumes the pipeline from the transaction agent pause point.
    """
    if not verify_pin(request.pin):
        raise HTTPException(status_code=403, detail="Invalid PIN")

    try:
        from orchestrator import resume_pipeline

        state = resume_pipeline(
            ro_id      = ro_id,
            approved   = True,
            advisor_id = request.advisor_id,
            notes      = request.notes or "",
        )

        return {
            "message":            "Quote approved — pipeline resumed",
            "ro_id":              ro_id,
            "transaction_status": state.get("transaction_status"),
            "approved_by":        state.get("approved_by"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ro_id}/reject")
def reject_quote(
    ro_id:   str,
    request: RejectQuoteRequest,
    db:      Session = Depends(get_db),
):
    """HITL — Rejects a quote. Releases all part reservations."""
    if not verify_pin(request.pin):
        raise HTTPException(status_code=403, detail="Invalid PIN")

    try:
        from orchestrator import resume_pipeline

        state = resume_pipeline(
            ro_id      = ro_id,
            approved   = False,
            advisor_id = request.advisor_id,
            notes      = request.reason,
        )

        return {
            "message":            "Quote rejected — reservations released",
            "ro_id":              ro_id,
            "transaction_status": state.get("transaction_status"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ro_id}/intake-review")
def submit_intake_review(
    ro_id:   str,
    request: IntakeReviewRequest,
    db:      Session = Depends(get_db),
):
    """
    Intake HITL — Supervisor submits manual parts/labor override.
    Called when agent couldn't identify parts (low confidence or body work).
    Resumes pipeline from inventory agent with supervisor input.
    """
    if not verify_pin(request.pin):
        raise HTTPException(status_code=403, detail="Invalid PIN")

    try:
        from orchestrator import resume_intake_hitl

        state = resume_intake_hitl(
            ro_id                       = ro_id,
            supervisor_id               = request.supervisor_id,
            supervisor_parts            = request.supervisor_parts,
            supervisor_custom_materials = request.supervisor_custom_materials,
            supervisor_labor_description = request.supervisor_labor_description,
            supervisor_labor_hours      = request.supervisor_labor_hours,
            supervisor_labor_rate       = request.supervisor_labor_rate,
            inspection_only             = request.inspection_only,
            supervisor_notes            = request.supervisor_notes,
        )

        return {
            "message":   "Intake review submitted — pipeline resumed",
            "ro_id":     ro_id,
            "quote_id":  state.get("quote_id"),
            "total":     state.get("quote", {}).get("total_amount"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))