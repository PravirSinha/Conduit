"""
CONDUIT — Integration Tests: API Endpoints
============================================
Uses FastAPI TestClient — no real HTTP, no uvicorn needed.
Database must be running (Docker postgres).

Run: pytest tests/integration/ -v
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """
    Creates FastAPI TestClient for the duration of the test module.
    scope="module" — client created once, reused across all tests.
    """
    from api.main import app
    with TestClient(app) as c:
        yield c


# ── HEALTH CHECK ──────────────────────────────────────────────────────────────

class TestHealth:

    def test_health_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_status_is_healthy(self, client):
        r = client.get("/health")
        assert r.json()["status"] == "healthy"

    def test_health_database_connected(self, client):
        r = client.get("/health")
        assert r.json()["database"] == "connected"

    def test_health_tables_present(self, client):
        r = client.get("/health")
        tables = r.json()["tables"]
        assert "vehicles"       in tables
        assert "inventory"      in tables
        assert "repair_orders"  in tables

    def test_health_vehicles_populated(self, client):
        """500 synthetic vehicles must be loaded."""
        r = client.get("/health")
        assert r.json()["tables"]["vehicles"] >= 500

    def test_health_inventory_populated(self, client):
        """28 parts catalog must be present."""
        r = client.get("/health")
        assert r.json()["tables"]["inventory"] >= 28


# ── INVENTORY ─────────────────────────────────────────────────────────────────

class TestInventoryEndpoints:

    def test_list_parts_returns_200(self, client):
        r = client.get("/api/inventory/")
        assert r.status_code == 200

    def test_list_parts_returns_list(self, client):
        r = client.get("/api/inventory/")
        assert isinstance(r.json(), list)

    def test_list_parts_count(self, client):
        r = client.get("/api/inventory/")
        assert len(r.json()) >= 28

    def test_part_has_required_fields(self, client):
        r    = client.get("/api/inventory/")
        part = r.json()[0]
        for field in ["part_number", "description", "qty_on_hand", "stock_status"]:
            assert field in part, f"Missing field: {field}"

    def test_filter_by_status_critical(self, client):
        r     = client.get("/api/inventory/?status=critical")
        parts = r.json()
        for p in parts:
            assert p["stock_status"] == "critical"

    def test_filter_by_status_healthy(self, client):
        r     = client.get("/api/inventory/?status=healthy")
        parts = r.json()
        for p in parts:
            assert p["stock_status"] == "healthy"

    def test_get_specific_part(self, client):
        r = client.get("/api/inventory/BRK-PAD-HON-F-01")
        assert r.status_code == 200
        assert r.json()["part_number"] == "BRK-PAD-HON-F-01"

    def test_get_nonexistent_part_returns_404(self, client):
        r = client.get("/api/inventory/FAKE-PART-999")
        assert r.status_code == 404

    def test_stock_alerts_endpoint(self, client):
        r    = client.get("/api/inventory/alerts")
        data = r.json()
        assert "critical_count" in data
        assert "low_count"      in data
        assert "critical_parts" in data
        assert "low_parts"      in data

    def test_stock_alerts_counts_are_integers(self, client):
        r    = client.get("/api/inventory/alerts")
        data = r.json()
        assert isinstance(data["critical_count"], int)
        assert isinstance(data["low_count"],      int)


# ── REPAIR ORDERS ─────────────────────────────────────────────────────────────

class TestRepairOrderEndpoints:

    def test_list_ros_returns_200(self, client):
        r = client.get("/api/repair-orders/")
        assert r.status_code == 200

    def test_list_ros_returns_list(self, client):
        r = client.get("/api/repair-orders/")
        assert isinstance(r.json(), list)

    def test_ro_list_item_has_required_fields(self, client):
        r   = client.get("/api/repair-orders/?limit=1")
        ros = r.json()
        if ros:
            ro = ros[0]
            for field in ["ro_id", "vin", "status"]:
                assert field in ro, f"Missing field: {field}"

    def test_filter_by_status_complete(self, client):
        r   = client.get("/api/repair-orders/?status=COMPLETE")
        ros = r.json()
        for ro in ros:
            assert ro["status"] == "COMPLETE"

    def test_create_ro_invalid_vin_returns_404(self, client):
        """Non-existent VIN should return 404."""
        r = client.post("/api/repair-orders/", json={
            "vin":            "FAKE-VIN-000000000",
            "complaint_text": "something wrong",
        })
        assert r.status_code == 404

    def test_create_ro_missing_complaint_returns_422(self, client):
        """Missing required field returns 422 Unprocessable Entity."""
        r = client.post("/api/repair-orders/", json={
            "vin": "I0Y6DPBHSAHXTHV3A",
            # complaint_text missing
        })
        assert r.status_code == 422

    def test_pending_approval_returns_list(self, client):
        r = client.get("/api/repair-orders/pending-approval")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_nonexistent_ro_returns_404(self, client):
        r = client.get("/api/repair-orders/RO-DOESNOTEXIST")
        assert r.status_code == 404


# ── DASHBOARD STATS ───────────────────────────────────────────────────────────

class TestDashboardEndpoints:

    def test_stats_returns_200(self, client):
        r = client.get("/api/dashboard/stats")
        assert r.status_code == 200

    def test_stats_has_required_fields(self, client):
        r    = client.get("/api/dashboard/stats")
        data = r.json()
        required = [
            "total_ros", "open_ros", "completed_ros",
            "pending_approval", "total_revenue", "avg_ro_value",
            "ev_job_count", "critical_parts", "low_parts",
            "pending_pos", "total_po_value", "avg_confidence",
        ]
        for field in required:
            assert field in data, f"Missing stat: {field}"

    def test_stats_total_ros_positive(self, client):
        r = client.get("/api/dashboard/stats")
        assert r.json()["total_ros"] > 0

    def test_stats_values_are_numeric(self, client):
        r    = client.get("/api/dashboard/stats")
        data = r.json()
        assert isinstance(data["total_ros"],      int)
        assert isinstance(data["total_revenue"],  float)
        assert isinstance(data["avg_confidence"], float)


# ── PURCHASE ORDERS ───────────────────────────────────────────────────────────

class TestPurchaseOrderEndpoints:

    def test_list_pos_returns_200(self, client):
        r = client.get("/api/purchase-orders/")
        assert r.status_code == 200

    def test_list_pos_returns_list(self, client):
        r = client.get("/api/purchase-orders/")
        assert isinstance(r.json(), list)

    def test_po_summary_returns_200(self, client):
        r = client.get("/api/purchase-orders/summary")
        assert r.status_code == 200

    def test_po_summary_has_required_fields(self, client):
        r    = client.get("/api/purchase-orders/summary")
        data = r.json()
        assert "total_pos"      in data
        assert "pending_pos"    in data
        assert "total_po_value" in data

    def test_get_nonexistent_po_returns_404(self, client):
        r = client.get("/api/purchase-orders/PO-DOESNOTEXIST")
        assert r.status_code == 404