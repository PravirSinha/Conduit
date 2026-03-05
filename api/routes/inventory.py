"""CONDUIT — Inventory Routes"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Inventory
from api.schemas import PartResponse

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("/", response_model=List[PartResponse])
def list_parts(
    status:   Optional[str] = None,
    category: Optional[str] = None,
    db:       Session       = Depends(get_db),
):
    """Lists all parts with optional filters."""
    query = db.query(Inventory)

    if status:
        query = query.filter(Inventory.stock_status == status)
    if category:
        query = query.filter(Inventory.category == category)

    parts = query.order_by(Inventory.category, Inventory.part_number).all()

    return [
        PartResponse(
            part_number   = p.part_number,
            description   = p.description,
            category      = p.category,
            brand         = p.brand,
            sell_price    = float(p.sell_price) if p.sell_price else None,
            qty_on_hand   = p.qty_on_hand,
            qty_available = p.qty_on_hand - p.qty_reserved,
            stock_status  = p.stock_status,
            bin_location  = p.bin_location,
        )
        for p in parts
    ]


@router.get("/alerts")
def get_stock_alerts(db: Session = Depends(get_db)):
    """Returns critical and low stock parts for dashboard alerts."""
    critical = db.query(Inventory).filter(
        Inventory.stock_status == "critical"
    ).all()

    low = db.query(Inventory).filter(
        Inventory.stock_status == "low"
    ).all()

    return {
        "critical_count": len(critical),
        "low_count":      len(low),
        "critical_parts": [
            {
                "part_number": p.part_number,
                "description": p.description,
                "qty_on_hand": p.qty_on_hand,
                "reorder_point": p.reorder_point,
            }
            for p in critical
        ],
        "low_parts": [
            {
                "part_number": p.part_number,
                "description": p.description,
                "qty_on_hand": p.qty_on_hand,
                "reorder_point": p.reorder_point,
            }
            for p in low
        ],
    }


@router.get("/{part_number}", response_model=PartResponse)
def get_part(part_number: str, db: Session = Depends(get_db)):
    """Gets a single part by part number."""
    part = db.query(Inventory).filter(
        Inventory.part_number == part_number
    ).first()

    if not part:
        raise HTTPException(status_code=404, detail=f"Part {part_number} not found")

    return PartResponse(
        part_number   = part.part_number,
        description   = part.description,
        category      = part.category,
        brand         = part.brand,
        sell_price    = float(part.sell_price) if part.sell_price else None,
        qty_on_hand   = part.qty_on_hand,
        qty_available = part.qty_on_hand - part.qty_reserved,
        stock_status  = part.stock_status,
        bin_location  = part.bin_location,
    )