"""CONDUIT — Purchase Orders Routes"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import PurchaseOrder
from api.schemas import PurchaseOrderResponse

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])


@router.get("/", response_model=List[PurchaseOrderResponse])
def list_purchase_orders(
    status: Optional[str] = None,
    db:     Session       = Depends(get_db),
):
    """Lists all purchase orders with optional status filter."""
    query = db.query(PurchaseOrder)

    if status:
        query = query.filter(PurchaseOrder.status == status.upper())

    pos = query.order_by(PurchaseOrder.created_at.desc()).limit(100).all()

    return [
        PurchaseOrderResponse(
            po_id       = po.po_id,
            supplier_id = po.supplier_id,
            total_value = float(po.total_value) if po.total_value else None,
            status      = po.status,
            raised_by   = po.raised_by,
            created_at  = po.created_at,
        )
        for po in pos
    ]


@router.get("/summary")
def get_po_summary(db: Session = Depends(get_db)):
    """Summary stats for PO dashboard panel."""
    from sqlalchemy import func

    total   = db.query(func.count(PurchaseOrder.po_id)).scalar()
    raised  = db.query(func.count(PurchaseOrder.po_id)).filter(
                  PurchaseOrder.status == "RAISED"
              ).scalar()
    total_value = db.query(func.sum(PurchaseOrder.total_value)).filter(
                      PurchaseOrder.status == "RAISED"
                  ).scalar()

    return {
        "total_pos":       total,
        "pending_pos":     raised,
        "total_po_value":  float(total_value or 0),
    }


@router.get("/{po_id}")
def get_purchase_order(po_id: str, db: Session = Depends(get_db)):
    """Gets a single purchase order by ID."""
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.po_id == po_id
    ).first()

    if not po:
        raise HTTPException(status_code=404, detail=f"PO {po_id} not found")

    return PurchaseOrderResponse(
        po_id       = po.po_id,
        supplier_id = po.supplier_id,
        total_value = float(po.total_value) if po.total_value else None,
        status      = po.status,
        raised_by   = po.raised_by,
        created_at  = po.created_at,
    )


@router.patch("/{po_id}/status")
def update_po_status(
    po_id:  str,
    status: str,
    db:     Session = Depends(get_db),
):
    """Updates PO status (RAISED → CONFIRMED → DELIVERED)."""
    allowed = ["RAISED", "CONFIRMED", "DELIVERED", "CANCELLED"]

    if status.upper() not in allowed:
        raise HTTPException(
            status_code = 400,
            detail      = f"Invalid status. Must be one of: {allowed}"
        )

    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.po_id == po_id
    ).first()

    if not po:
        raise HTTPException(status_code=404, detail=f"PO {po_id} not found")

    po.status = status.upper()
    db.commit()

    return {"message": f"PO {po_id} status updated to {status.upper()}"}