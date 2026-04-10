"""
CONDUIT — API Schemas
Pydantic models for request validation and response serialisation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ── REQUEST SCHEMAS ───────────────────────────────────────────────────────────

class CreateRORequest(BaseModel):
    """Request body for creating a new repair order and running pipeline."""
    vin:            str  = Field(..., description="Vehicle VIN")
    complaint_text: str  = Field(..., description="Customer complaint in natural language")
    customer_id:    Optional[str] = Field(None, description="Customer ID if known")

    class Config:
        json_schema_extra = {
            "example": {
                "vin":            "I0Y6DPBHSAHXTHV3A",
                "complaint_text": "grinding noise from front wheels when braking, car pulls left",
                "customer_id":    "CUST-001",
            }
        }


class ApproveQuoteRequest(BaseModel):
    """Request body for HITL transaction approval."""
    advisor_id: str  = Field(..., description="Service advisor ID")
    pin:        str  = Field(..., description="Advisor PIN for authentication")
    notes:      Optional[str] = Field("", description="Optional approval notes")


class RejectQuoteRequest(BaseModel):
    """Request body for HITL transaction rejection."""
    advisor_id: str  = Field(..., description="Service advisor ID")
    pin:        str  = Field(..., description="Advisor PIN for authentication")
    reason:     str  = Field(..., description="Reason for rejection")


class IntakeReviewRequest(BaseModel):
    """
    Request body for intake HITL supervisor override.
    Supervisor fills this when agent couldn't identify parts.
    Option C — can provide catalog parts, custom materials, or labor-only.
    """
    supervisor_id:   str = Field(..., description="Supervisor ID")
    pin:             str = Field(..., description="Supervisor PIN")

    # Option A — parts from catalog
    supervisor_parts: List[str] = Field(
        default=[],
        description="Part numbers selected from catalog"
    )

    # Option B — custom materials (paint, compound, sundries)
    supervisor_custom_materials: List[Dict] = Field(
        default=[],
        description='Custom materials e.g. [{"description": "Silver paint 2L", "cost": 3500}]'
    )

    # Option C — labor details
    supervisor_labor_description: Optional[str] = Field(
        None,
        description="Labor description e.g. 'Dent repair and full panel respray'"
    )
    supervisor_labor_hours: Optional[float] = Field(
        None,
        description="Estimated labor hours"
    )
    supervisor_labor_rate:  Optional[float] = Field(
        None,
        description="Hourly rate — uses standard rate if not provided"
    )

    # Inspection only flag
    inspection_only: bool = Field(
        False,
        description="True = diagnostic quote only, no parts"
    )
    supervisor_notes: Optional[str] = Field(None, description="Additional notes")

    # Optional — supervisor can refine complaint/dx for re-triage
    supervisor_complaint_override: Optional[str] = Field(
        None,
        description=(
            "Supervisor finding / refined complaint (e.g. 'battery not working'). "
            "If provided, pipeline re-runs Intake classification using this text."
        ),
    )


# ── RESPONSE SCHEMAS ──────────────────────────────────────────────────────────

class VehicleResponse(BaseModel):
    vin:                str
    make:               str
    model:              str
    year:               int
    fuel_type:          Optional[str]
    is_ev:              bool
    odometer_km:        Optional[int]
    warranty_expired:   bool


class QuoteSummary(BaseModel):
    quote_id:        str
    subtotal:        float
    discount_amount: float
    gst_amount:      float
    total_amount:    float
    status:          str


class ROResponse(BaseModel):
    """Full repair order response."""
    ro_id:                  str
    vin:                    str
    customer_name:          Optional[str]
    fault_classification:   Optional[str]
    urgency:                Optional[str]
    intake_confidence:      Optional[float]
    required_parts:         Optional[List[str]]
    parts_available:        Optional[bool]
    quote_id:               Optional[str]
    transaction_status:     Optional[str]
    approved_by:            Optional[str]
    status:                 str
    is_ev_job:              bool
    recall_action_required: Optional[bool]
    hitl_triggered:         Optional[bool]
    intake_hitl_triggered:  Optional[bool]
    supervisor_override:    Optional[bool]
    reorder_summary:        Optional[str]
    error:                  Optional[str]
    vehicle:                Optional[VehicleResponse]
    quote:                  Optional[QuoteSummary]
    oem_quote:              Optional[Dict]
    aftermarket_quote:      Optional[Dict]


class ROListItem(BaseModel):
    """Lightweight RO for list view."""
    ro_id:                str
    vin:                  str
    customer_name:        Optional[str]
    vehicle_make:         Optional[str]
    vehicle_model:        Optional[str]
    vehicle_year:         Optional[int]
    fault_classification: Optional[str]
    urgency:              Optional[str]
    status:               str
    final_total:          Optional[float]
    opened_at:            Optional[datetime]


class PartResponse(BaseModel):
    part_number:    str
    description:    str
    category:       Optional[str]
    brand:          Optional[str]
    sell_price:     Optional[float]
    qty_on_hand:    int
    qty_available:  int
    stock_status:   str
    bin_location:   Optional[str]


class PurchaseOrderResponse(BaseModel):
    po_id:       str
    supplier_id: str
    total_value: Optional[float]
    status:      str
    raised_by:   Optional[str]
    created_at:  Optional[datetime]


class DashboardStats(BaseModel):
    """Summary stats for Streamlit dashboard."""
    total_ros:          int
    open_ros:           int
    in_progress_ros:    int = 0
    completed_ros:      int
    pending_approval:   int
    total_revenue:      float
    avg_ro_value:       float
    ev_job_count:       int
    critical_parts:     int
    low_parts:          int
    pending_pos:        int
    total_po_value:     float
    avg_confidence:     float
    revenue_7d:         float = 0.0
    quotes_7d:          int   = 0