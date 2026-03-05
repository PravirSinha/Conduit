"""CONDUIT — Quotes Routes"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Quote

router = APIRouter(prefix="/quotes", tags=["Quotes"])


@router.get("/{quote_id}")
def get_quote(quote_id: str, db: Session = Depends(get_db)):
    """Gets full quote details including OEM and aftermarket options."""
    quote = db.query(Quote).filter(Quote.quote_id == quote_id).first()

    if not quote:
        raise HTTPException(status_code=404, detail=f"Quote {quote_id} not found")

    return {
        "quote_id":          quote.quote_id,
        "ro_id":             quote.ro_id,
        "line_items":        quote.line_items,
        "subtotal":          float(quote.subtotal or 0),
        "discount_amount":   float(quote.discount_amount or 0),
        "gst_amount":        float(quote.gst_amount or 0),
        "total_amount":      float(quote.total_amount or 0),
        "status":            quote.status,
        "oem_quote":         quote.oem_quote,
        "aftermarket_quote": quote.aftermarket_quote,
        "requires_approval": quote.requires_approval,
        "approved_by":       quote.approved_by,
        "approved_at":       quote.approved_at,
        "valid_until":       quote.valid_until,
        "created_at":        quote.created_at,
    }