"""CONDUIT — Dashboard Stats Route"""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import RepairOrder, Inventory, PurchaseOrder, AgentAuditLog, Quote
from api.schemas import DashboardStats

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    Returns all summary stats needed by Streamlit dashboard.
    Single endpoint — dashboard fetches everything in one call.
    """

    # ── RO STATS ──────────────────────────────────────────────────────────
    total_ros = db.query(func.count(RepairOrder.ro_id)).scalar() or 0

    open_ros = db.query(func.count(RepairOrder.ro_id)).filter(
        RepairOrder.status.in_(["OPEN", "IN_PROGRESS"])
    ).scalar() or 0

    completed_ros = db.query(func.count(RepairOrder.ro_id)).filter(
        RepairOrder.status == "COMPLETE"
    ).scalar() or 0

    pending_approval = db.query(func.count(RepairOrder.ro_id)).filter(
        RepairOrder.status.in_(["QUOTED", "PENDING_INSPECTION"])
    ).scalar() or 0

    ev_job_count = db.query(func.count(RepairOrder.ro_id)).filter(
        RepairOrder.is_ev_job == True
    ).scalar() or 0

    # ── REVENUE STATS ──────────────────────────────────────────────────────
    total_revenue = db.query(func.sum(RepairOrder.final_total)).filter(
        RepairOrder.status == "COMPLETE"
    ).scalar() or 0.0

    avg_ro_value = db.query(func.avg(RepairOrder.final_total)).filter(
        RepairOrder.status == "COMPLETE"
    ).scalar() or 0.0

    # ── INVENTORY STATS ────────────────────────────────────────────────────
    critical_parts = db.query(func.count(Inventory.part_number)).filter(
        Inventory.stock_status == "critical"
    ).scalar() or 0

    low_parts = db.query(func.count(Inventory.part_number)).filter(
        Inventory.stock_status == "low"
    ).scalar() or 0

    # ── PO STATS ──────────────────────────────────────────────────────────
    pending_pos = db.query(func.count(PurchaseOrder.po_id)).filter(
        PurchaseOrder.status == "RAISED"
    ).scalar() or 0

    total_po_value = db.query(func.sum(PurchaseOrder.total_value)).filter(
        PurchaseOrder.status == "RAISED"
    ).scalar() or 0.0

    # ── AGENT CONFIDENCE AVERAGE ───────────────────────────────────────────
    # Read from classification_payload JSONB field
    # Using Python avg since JSONB field extraction varies by DB version
    recent_ros = db.query(RepairOrder.classification_payload).filter(
        RepairOrder.classification_payload != None
    ).limit(100).all()

    confidences = []
    for row in recent_ros:
        payload = row[0]
        if isinstance(payload, dict) and "confidence" in payload:
            confidences.append(float(payload["confidence"]))

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return DashboardStats(
        total_ros        = total_ros,
        open_ros         = open_ros,
        completed_ros    = completed_ros,
        pending_approval = pending_approval,
        total_revenue    = float(total_revenue),
        avg_ro_value     = float(avg_ro_value),
        ev_job_count     = ev_job_count,
        critical_parts   = critical_parts,
        low_parts        = low_parts,
        pending_pos      = pending_pos,
        total_po_value   = float(total_po_value),
        avg_confidence   = round(avg_confidence, 2),
    )


@router.get("/pipeline-trace/{ro_id}")
def get_pipeline_trace(ro_id: str, db: Session = Depends(get_db)):
    """
    Returns agent audit log for a specific RO.
    Used by dashboard to show per-agent timing and status.
    """
    logs = db.query(AgentAuditLog).filter(
        AgentAuditLog.ro_id == ro_id
    ).order_by(AgentAuditLog.created_at.asc()).all()

    return [
        {
            "agent":          log.agent_name,
            "action":         log.action,
            "latency_ms":     log.latency_ms,
            "input_payload":  log.input_payload,
            "output_payload": log.output_payload,
            "timestamp":      log.created_at,
        }
        for log in logs
    ]