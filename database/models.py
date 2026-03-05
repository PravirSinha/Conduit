"""
CONDUIT — Database Models
SQLAlchemy ORM table definitions for all entities
"""

from sqlalchemy import (
    Column, String, Integer, Float, Boolean,
    DateTime, Text, Date, JSON, DECIMAL, BigInteger
)
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class Vehicle(Base):
    """
    Master vehicle catalog
    Source: VIN decode + customer registration
    Used by: Intake Agent (VIN lookup + compatibility)
    """
    __tablename__ = "vehicles"

    vin                     = Column(String(17), primary_key=True)
    make                    = Column(String(50), nullable=False)
    model                   = Column(String(50), nullable=False)
    year                    = Column(Integer, nullable=False)
    trim                    = Column(String(50))
    fuel_type               = Column(String(20))
    engine_code             = Column(String(30))
    transmission            = Column(String(30))
    category                = Column(String(50))
    color                   = Column(String(30))
    odometer_km             = Column(Integer)
    registration_number     = Column(String(20))
    registration_state      = Column(String(5))
    warranty_expired        = Column(Boolean, default=False)
    battery_capacity_kwh    = Column(Float, nullable=True)
    is_ev                   = Column(Boolean, default=False)
    created_at              = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Vehicle {self.vin} {self.year} {self.make} {self.model}>"


class Inventory(Base):
    """
    Parts catalog + real-time stock levels
    Source: WMS + supplier deliveries
    Used by: Inventory Agent (stock check + reservation)
             Replenishment Agent (reorder decisions)
    """
    __tablename__ = "inventory"

    part_number             = Column(String(50), primary_key=True)
    description             = Column(Text, nullable=False)
    category                = Column(String(50))
    subcategory             = Column(String(50))
    oem_part_number         = Column(String(50), nullable=True)
    brand                   = Column(String(50))
    unit_of_measure         = Column(String(20))
    unit_cost               = Column(DECIMAL(10, 2))
    sell_price              = Column(DECIMAL(10, 2))
    compatible_makes        = Column(JSON)
    compatible_models       = Column(JSON)
    compatible_years        = Column(JSON)
    compatible_fuel_types   = Column(JSON)
    shelf_life_days         = Column(Integer, nullable=True)
    weight_kg               = Column(Float)
    bin_location            = Column(String(20))
    qty_on_hand             = Column(Integer, default=0)
    qty_reserved            = Column(Integer, default=0)
    reorder_point           = Column(Integer, default=10)
    reorder_quantity        = Column(Integer, default=20)
    stock_status            = Column(String(20), default="healthy")
    updated_at              = Column(
                                DateTime,
                                default=datetime.utcnow,
                                onupdate=datetime.utcnow
                              )

    def __repr__(self):
        return (
            f"<Inventory {self.part_number} "
            f"qty={self.qty_on_hand} "
            f"status={self.stock_status}>"
        )


class LaborOperation(Base):
    """
    Labor operations catalog with flat-rate hours
    Source: AllData / Chilton equivalent (India)
    Used by: Quoting Agent (labor cost calculation)
    """
    __tablename__ = "labor_operations"

    operation_code              = Column(String(20), primary_key=True)
    description                 = Column(Text)
    flat_rate_hours             = Column(Float)
    skill_level                 = Column(String(30))
    related_parts_categories    = Column(JSON)
    rate_per_hour               = Column(Integer)

    def __repr__(self):
        return (
            f"<LaborOperation {self.operation_code} "
            f"{self.flat_rate_hours}hrs>"
        )


class Customer(Base):
    """
    Customer profiles with loyalty tier and vehicle ownership
    Source: DMS customer records
    Used by: Intake Agent (history lookup)
             Quoting Agent (discount application)
    """
    __tablename__ = "customers"

    customer_id         = Column(String(20), primary_key=True)
    first_name          = Column(String(50))
    last_name           = Column(String(50))
    full_name           = Column(String(100))
    phone               = Column(String(20))
    email               = Column(String(100))
    area                = Column(String(50))
    city                = Column(String(50))
    state               = Column(String(30))
    pincode             = Column(String(10))
    occupation          = Column(String(100))
    loyalty_tier        = Column(Integer, default=1)
    loyalty_tier_name   = Column(String(20))
    discount_rate       = Column(Float, default=0.0)
    total_visits        = Column(Integer, default=0)
    payment_behavior    = Column(String(20))
    avg_payment_days    = Column(Integer)
    preferred_contact   = Column(String(20))
    vehicle_vins        = Column(JSON)
    is_corporate        = Column(Boolean, default=False)
    marketing_consent   = Column(Boolean, default=True)
    created_at          = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return (
            f"<Customer {self.customer_id} "
            f"{self.full_name} "
            f"Tier={self.loyalty_tier}>"
        )


class Supplier(Base):
    """
    Supplier profiles with live performance scorecard
    Source: Procurement records + delivery confirmations
    Used by: Replenishment Agent (supplier selection + scoring)
    """
    __tablename__ = "suppliers"

    supplier_id             = Column(String(20), primary_key=True)
    name                    = Column(String(100), nullable=False)
    short_name              = Column(String(50))
    type                    = Column(String(50))
    integration_type        = Column(String(20))
    specialization          = Column(JSON)
    categories_supplied     = Column(JSON)
    current_on_time_rate    = Column(Float)
    current_fill_rate       = Column(Float)
    composite_score         = Column(Float)
    composite_score_pct     = Column(Float)
    lead_time_days          = Column(Integer)
    min_order_value         = Column(DECIMAL(10, 2))
    payment_terms_days      = Column(Integer)
    city                    = Column(String(50))
    state                   = Column(String(30))
    contact_email           = Column(String(100))
    api_capable             = Column(Boolean, default=False)
    reliability_tier        = Column(String(10))
    updated_at              = Column(
                                DateTime,
                                default=datetime.utcnow,
                                onupdate=datetime.utcnow
                              )

    def __repr__(self):
        return (
            f"<Supplier {self.supplier_id} "
            f"{self.short_name} "
            f"score={self.composite_score_pct}%>"
        )


class RepairOrder(Base):
    """
    Core transaction record — master RO table
    Written by: All five agents at different stages
    - Intake Agent writes: fault_category, complaint, classification_payload
    - Inventory Agent writes: inventory_payload
    - Quoting Agent writes: quote_id
    - Transaction Agent writes: status, closed_at
    """
    __tablename__ = "repair_orders"

    ro_id                   = Column(String(20), primary_key=True)
    vin                     = Column(String(17), nullable=False)
    customer_id             = Column(String(20), nullable=True)
    customer_name           = Column(String(100))
    service_advisor_id      = Column(String(20))
    service_advisor_name    = Column(String(100))
    technician_id           = Column(String(20))
    technician_name         = Column(String(100))
    bay                     = Column(String(20))
    fault_category          = Column(String(50))
    complaint_text          = Column(Text)
    dtc_codes               = Column(JSON)
    vehicle_make            = Column(String(50))
    vehicle_model           = Column(String(50))
    vehicle_year            = Column(Integer)
    vehicle_fuel_type       = Column(String(20))
    is_ev_job               = Column(Boolean, default=False)
    parts_cost              = Column(DECIMAL(10, 2), nullable=True)
    labor_cost              = Column(DECIMAL(10, 2), nullable=True)
    subtotal                = Column(DECIMAL(10, 2), nullable=True)
    discount_rate           = Column(Float, default=0.0)
    discount_amount         = Column(DECIMAL(10, 2), nullable=True)
    gst_amount              = Column(DECIMAL(10, 2), nullable=True)
    final_total             = Column(DECIMAL(10, 2), nullable=True)
    status                  = Column(String(20), default="OPEN")
    classification_payload  = Column(JSON, nullable=True)
    inventory_payload       = Column(JSON, nullable=True)
    quote_id                = Column(String(20), nullable=True)
    opened_at               = Column(DateTime, nullable=True)
    closed_at               = Column(DateTime, nullable=True)
    month                   = Column(Integer, nullable=True)
    year                    = Column(Integer, nullable=True)
    warranty_claim          = Column(Boolean, default=False)
    created_at              = Column(DateTime, default=datetime.utcnow)
    updated_at              = Column(
                                DateTime,
                                default=datetime.utcnow,
                                onupdate=datetime.utcnow
                              )

    def __repr__(self):
        return (
            f"<RepairOrder {self.ro_id} "
            f"vin={self.vin} "
            f"status={self.status}>"
        )


class Quote(Base):
    """
    Generated quotes — OEM and aftermarket options
    Written by: Quoting Agent
    Read by: Transaction Agent (on approval)
             Dashboard (for display)
    """
    __tablename__ = "quotes"

    quote_id            = Column(String(20), primary_key=True)
    ro_id               = Column(String(20), nullable=False)
    line_items          = Column(JSON)
    subtotal            = Column(DECIMAL(10, 2))
    discount_amount     = Column(DECIMAL(10, 2))
    gst_amount          = Column(DECIMAL(10, 2))
    total_amount        = Column(DECIMAL(10, 2))
    status              = Column(String(20), default="DRAFT")
    oem_quote           = Column(JSON, nullable=True)
    aftermarket_quote   = Column(JSON, nullable=True)
    requires_approval   = Column(Boolean, default=False)
    approved_by         = Column(String(50), nullable=True)
    approved_at         = Column(DateTime, nullable=True)
    valid_until         = Column(DateTime, nullable=True)
    created_at          = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return (
            f"<Quote {self.quote_id} "
            f"ro={self.ro_id} "
            f"total={self.total_amount} "
            f"status={self.status}>"
        )


class PurchaseOrder(Base):
    """
    Purchase orders raised by Replenishment Agent
    Tracks full PO lifecycle from RAISED to CLOSED
    Used by: Replenishment Agent (raise + monitor)
             Supplier scorecard (performance tracking)
    """
    __tablename__ = "purchase_orders"

    po_id               = Column(String(50), primary_key=True)
    supplier_id         = Column(String(20))
    total_value         = Column(DECIMAL(10, 2))
    on_time             = Column(Boolean, nullable=True)
    days_late           = Column(Integer, default=0)
    fill_rate           = Column(Float, nullable=True)
    partial_delivery    = Column(Boolean, default=False)
    status              = Column(String(20), default="PENDING")
    raised_by           = Column(
                            String(50),
                            default="REPLENISHMENT_AGENT"
                          )
    month               = Column(Integer, nullable=True)
    year                = Column(Integer, nullable=True)
    created_at          = Column(DateTime, default=datetime.utcnow)
    updated_at          = Column(
                            DateTime,
                            default=datetime.utcnow,
                            onupdate=datetime.utcnow
                          )

    def __repr__(self):
        return (
            f"<PurchaseOrder {self.po_id} "
            f"supplier={self.supplier_id} "
            f"status={self.status}>"
        )


class AgentAuditLog(Base):
    """
    Full audit trail of every agent decision
    Written by: Every agent via agent_logger.py
    Used by: Dashboard (pipeline view)
             Debugging + explainability
             LangSmith fallback for local logging
    """
    __tablename__ = "agent_audit_log"

    log_id          = Column(Integer, primary_key=True, autoincrement=True)
    ro_id           = Column(String(20), nullable=True)
    agent_name      = Column(String(50))
    action          = Column(String(100))
    input_payload   = Column(JSON, nullable=True)
    output_payload  = Column(JSON, nullable=True)
    latency_ms      = Column(Integer, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return (
            f"<AgentAuditLog {self.log_id} "
            f"agent={self.agent_name} "
            f"ro={self.ro_id}>"
        )
