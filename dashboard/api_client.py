"""
CONDUIT — Dashboard API Client
All API calls go through here — never call requests directly in components.
"""

import os
import requests
from typing import Optional, Dict, List

API_BASE = os.environ.get("API_URL", "http://localhost:8000") + "/api"


def _get(endpoint: str) -> Optional[Dict]:
    try:
        r = requests.get(f"{API_BASE}{endpoint}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return None


def _post(endpoint: str, data: Dict) -> Optional[Dict]:
    try:
        r = requests.post(f"{API_BASE}{endpoint}", json=data, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return None


def _patch(endpoint: str, data: Dict = None) -> Optional[Dict]:
    try:
        r = requests.patch(f"{API_BASE}{endpoint}", json=data or {}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return None


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

def get_stats():
    return _get("/dashboard/stats")

def get_pipeline_trace(ro_id: str):
    return _get(f"/dashboard/pipeline-trace/{ro_id}")


# ── REPAIR ORDERS ─────────────────────────────────────────────────────────────

def create_ro(vin: str, complaint: str, customer_id: str = None):
    return _post("/repair-orders/", {
        "vin":            vin,
        "complaint_text": complaint,
        "customer_id":    customer_id,
    })

def list_ros(status: str = None, limit: int = 50):
    endpoint = f"/repair-orders/?limit={limit}"
    if status:
        endpoint += f"&status={status}"
    return _get(endpoint) or []

def get_ro(ro_id: str):
    return _get(f"/repair-orders/{ro_id}")

def get_pending_approval():
    return _get("/repair-orders/pending-approval") or []

def approve_quote(ro_id: str, advisor_id: str, pin: str, notes: str = ""):
    return _post(f"/repair-orders/{ro_id}/approve", {
        "advisor_id": advisor_id,
        "pin":        pin,
        "notes":      notes,
    })

def reject_quote(ro_id: str, advisor_id: str, pin: str, reason: str):
    return _post(f"/repair-orders/{ro_id}/reject", {
        "advisor_id": advisor_id,
        "pin":        pin,
        "reason":     reason,
    })

def submit_intake_review(ro_id: str, payload: Dict):
    return _post(f"/repair-orders/{ro_id}/intake-review", payload)


# ── INVENTORY ─────────────────────────────────────────────────────────────────

def list_parts(status: str = None, category: str = None):
    endpoint = "/inventory/"
    params   = []
    if status:   params.append(f"status={status}")
    if category: params.append(f"category={category}")
    if params:   endpoint += "?" + "&".join(params)
    return _get(endpoint) or []

def get_stock_alerts():
    return _get("/inventory/alerts")


# ── QUOTES ────────────────────────────────────────────────────────────────────

def get_quote(quote_id: str):
    return _get(f"/quotes/{quote_id}")


# ── PURCHASE ORDERS ───────────────────────────────────────────────────────────

def list_pos(status: str = None):
    endpoint = "/purchase-orders/"
    if status: endpoint += f"?status={status}"
    return _get(endpoint) or []

def get_po_summary():
    return _get("/purchase-orders/summary")

def update_po_status(po_id: str, status: str):
    return _patch(f"/purchase-orders/{po_id}/status?status={status}")