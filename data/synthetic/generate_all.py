"""
CONDUIT — Master Synthetic Data Generator
==========================================
Run this script ONCE to generate all synthetic data
and load it into PostgreSQL.

Usage:
    python data/synthetic/generate_all.py

Requirements:
    - PostgreSQL running (docker-compose up)
    - DATABASE_URL set in .env
    - All tables created (alembic upgrade head)

What this script does:
    1. Generates vehicles          → 500 records
    2. Generates parts catalog     → ~40 parts + 11 labor ops
    3. Generates customers         → 300 records
    4. Generates suppliers         → 8 suppliers + 12mo PO history
    5. Generates repair orders     → ~2000 historical ROs (12 months)
    6. Loads everything to PostgreSQL
    7. Prints summary report
"""

import os
import sys
import json
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))

from dotenv import load_dotenv
load_dotenv()

# Import generators
# Import generators
import importlib.util, os

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

base = os.path.join(os.path.dirname(os.path.abspath(__file__)))

vehicles_mod      = load_module("vehicles",      os.path.join(base, "vehicles.py"))
parts_mod         = load_module("parts",         os.path.join(base, "parts.py"))
customers_mod     = load_module("customers",     os.path.join(base, "customers.py"))
suppliers_mod     = load_module("suppliers",     os.path.join(base, "suppliers.py"))
repair_orders_mod = load_module("repair_orders", os.path.join(base, "repair_orders.py"))

generate_vehicles        = vehicles_mod.generate_vehicles
generate_parts           = parts_mod.generate_parts
generate_labor_operations = parts_mod.generate_labor_operations
generate_customers       = customers_mod.generate_customers
generate_suppliers       = suppliers_mod.generate_suppliers
generate_repair_orders   = repair_orders_mod.generate_repair_orders

parts = generate_parts()
print(f"DEBUG: First part number = {parts[0]['part_number']}")

# ── COLORS FOR TERMINAL OUTPUT ─────────────────────────────────────────────────
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header():
    print(f"\n{BOLD}{CYAN}")
    print("=" * 60)
    print("   CONDUIT — Synthetic Data Generator")
    print("   Intelligence That Moves")
    print("=" * 60)
    print(f"{RESET}")


def print_step(step: int, total: int, message: str):
    print(f"\n{BLUE}[{step}/{total}]{RESET} {BOLD}{message}{RESET}")


def print_success(message: str):
    print(f"  {GREEN}✓{RESET} {message}")


def print_warning(message: str):
    print(f"  {YELLOW}⚠{RESET} {message}")


def print_error(message: str):
    print(f"  {RED}✗{RESET} {message}")


def print_stat(label: str, value):
    print(f"  {CYAN}→{RESET} {label}: {BOLD}{value}{RESET}")


# ── DATABASE LOADER ────────────────────────────────────────────────────────────

def get_db_connection():
    """
    Returns a database connection
    Uses DATABASE_URL from environment
    """
    try:
        import psycopg2
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError(
                "DATABASE_URL not set in environment. "
                "Check your .env file."
            )
        conn = psycopg2.connect(database_url)
        return conn
    except ImportError:
        print_error("psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)
    except Exception as e:
        print_error(f"Database connection failed: {e}")
        print_warning("Is PostgreSQL running? Try: docker-compose up -d postgres")
        sys.exit(1)


def load_vehicles(conn, vehicles: list) -> int:
    """Loads vehicles into the vehicles table"""
    cursor = conn.cursor()
    loaded = 0

    for v in vehicles:
        try:
            cursor.execute("""
                INSERT INTO vehicles (
                    vin, make, model, year, trim, fuel_type,
                    engine_code, transmission, category, color,
                    odometer_km, registration_number,
                    registration_state, warranty_expired,
                    battery_capacity_kwh, is_ev
                ) VALUES (
                    %(vin)s, %(make)s, %(model)s, %(year)s,
                    %(trim)s, %(fuel_type)s, %(engine_code)s,
                    %(transmission)s, %(category)s, %(color)s,
                    %(odometer_km)s, %(registration_number)s,
                    %(registration_state)s, %(warranty_expired)s,
                    %(battery_capacity_kwh)s, %(is_ev)s
                )
                ON CONFLICT (vin) DO NOTHING
            """, v)
            loaded += 1
        except Exception as e:
            print_warning(f"Skipped vehicle {v.get('vin')}: {e}")

    conn.commit()
    cursor.close()
    return loaded


def load_parts(conn, parts: list) -> int:
    """Loads parts catalog into inventory table"""
    cursor = conn.cursor()
    loaded = 0

    for p in parts:
        try:
            cursor.execute("""
                INSERT INTO inventory (
                    part_number, description, category, subcategory,
                    oem_part_number, brand, unit_of_measure,
                    unit_cost, sell_price, compatible_makes,
                    compatible_models, compatible_years,
                    compatible_fuel_types, shelf_life_days,
                    weight_kg, bin_location, qty_on_hand,
                    qty_reserved, reorder_point, reorder_quantity,
                    stock_status
                ) VALUES (
                    %(part_number)s, %(description)s,
                    %(category)s, %(subcategory)s,
                    %(oem_part_number)s, %(brand)s,
                    %(unit_of_measure)s, %(unit_cost)s,
                    %(sell_price)s,
                    %(compatible_makes)s,
                    %(compatible_models)s,
                    %(compatible_years)s,
                    %(compatible_fuel_types)s,
                    %(shelf_life_days)s, %(weight_kg)s,
                    %(bin_location)s, %(qty_on_hand)s,
                    %(qty_reserved)s, %(reorder_point)s,
                    %(reorder_quantity)s, %(stock_status)s
                )
                ON CONFLICT (part_number) DO UPDATE SET
                    qty_on_hand = EXCLUDED.qty_on_hand,
                    stock_status = EXCLUDED.stock_status
            """, {
                **p,
                "compatible_makes": json.dumps(p["compatible_makes"]),
                "compatible_models": json.dumps(p["compatible_models"]),
                "compatible_years": json.dumps(p["compatible_years"]),
                "compatible_fuel_types": json.dumps(
                    p["compatible_fuel_types"]
                ),
            })
            loaded += 1
        except Exception as e:
            print_warning(f"Skipped part {p.get('part_number')}: {e}")

    conn.commit()
    cursor.close()
    return loaded


def load_labor_operations(conn, operations: list) -> int:
    """Loads labor operations catalog"""
    cursor = conn.cursor()
    loaded = 0

    for op in operations:
        try:
            cursor.execute("""
                INSERT INTO labor_operations (
                    operation_code, description, flat_rate_hours,
                    skill_level, related_parts_categories, rate_per_hour
                ) VALUES (
                    %(operation_code)s, %(description)s,
                    %(flat_rate_hours)s, %(skill_level)s,
                    %(related_parts_categories)s, %(rate_per_hour)s
                )
                ON CONFLICT (operation_code) DO NOTHING
            """, {
                **op,
                "related_parts_categories": json.dumps(
                    op["related_parts_categories"]
                ),
            })
            loaded += 1
        except Exception as e:
            print_warning(f"Skipped operation {op.get('operation_code')}: {e}")

    conn.commit()
    cursor.close()
    return loaded


def load_customers(conn, customers: list) -> int:
    """Loads customer profiles"""
    cursor = conn.cursor()
    loaded = 0

    for c in customers:
        try:
            cursor.execute("""
                INSERT INTO customers (
                    customer_id, first_name, last_name, full_name,
                    phone, email, area, city, state, pincode,
                    occupation, loyalty_tier, loyalty_tier_name,
                    discount_rate, total_visits, payment_behavior,
                    avg_payment_days, preferred_contact,
                    vehicle_vins, is_corporate, marketing_consent
                ) VALUES (
                    %(customer_id)s, %(first_name)s, %(last_name)s,
                    %(full_name)s, %(phone)s, %(email)s, %(area)s,
                    %(city)s, %(state)s, %(pincode)s, %(occupation)s,
                    %(loyalty_tier)s, %(loyalty_tier_name)s,
                    %(discount_rate)s, %(total_visits)s,
                    %(payment_behavior)s, %(avg_payment_days)s,
                    %(preferred_contact)s, %(vehicle_vins)s,
                    %(is_corporate)s, %(marketing_consent)s
                )
                ON CONFLICT (customer_id) DO NOTHING
            """, {
                **c,
                "vehicle_vins": json.dumps(c["vehicle_vins"]),
            })
            loaded += 1
        except Exception as e:
            print_warning(f"Skipped customer {c.get('customer_id')}: {e}")

    conn.commit()
    cursor.close()
    return loaded


def load_suppliers(conn, suppliers: list) -> int:
    """Loads supplier profiles"""
    cursor = conn.cursor()
    loaded = 0

    for s in suppliers:
        try:
            cursor.execute("""
                INSERT INTO suppliers (
                    supplier_id, name, short_name, type,
                    integration_type, specialization,
                    categories_supplied, current_on_time_rate,
                    current_fill_rate, composite_score,
                    lead_time_days, min_order_value,
                    payment_terms_days, city, state,
                    contact_email, api_capable, reliability_tier
                ) VALUES (
                    %(supplier_id)s, %(name)s, %(short_name)s,
                    %(type)s, %(integration_type)s,
                    %(specialization)s, %(categories_supplied)s,
                    %(current_on_time_rate)s, %(current_fill_rate)s,
                    %(composite_score)s, %(lead_time_days)s,
                    %(min_order_value)s, %(payment_terms_days)s,
                    %(city)s, %(state)s, %(contact_email)s,
                    %(api_capable)s, %(reliability_tier)s
                )
                ON CONFLICT (supplier_id) DO UPDATE SET
                    current_on_time_rate = EXCLUDED.current_on_time_rate,
                    current_fill_rate = EXCLUDED.current_fill_rate,
                    composite_score = EXCLUDED.composite_score
            """, {
                **s,
                "specialization": json.dumps(s["specialization"]),
                "categories_supplied": json.dumps(
                    s["categories_supplied"]
                ),
            })
            loaded += 1
        except Exception as e:
            print_warning(f"Skipped supplier {s.get('supplier_id')}: {e}")

    conn.commit()
    cursor.close()
    return loaded


def load_po_history(conn, po_history: list) -> int:
    """Loads historical purchase orders"""
    cursor = conn.cursor()
    loaded = 0

    for po in po_history:
        try:
            cursor.execute("""
                INSERT INTO purchase_orders (
                    po_id, supplier_id, total_value,
                    on_time, days_late, fill_rate,
                    partial_delivery, status,
                    raised_by, month, year
                ) VALUES (
                    %(po_id)s, %(supplier_id)s, %(po_value)s,
                    %(on_time)s, %(days_late)s, %(fill_rate)s,
                    %(partial_delivery)s, %(status)s,
                    'HISTORICAL_DATA', %(month)s, %(year)s
                )
                ON CONFLICT (po_id) DO NOTHING
            """, po)
            loaded += 1
        except Exception as e:
            print_warning(f"Skipped PO {po.get('po_id')}: {e}")

    conn.commit()
    cursor.close()
    return loaded


def load_repair_orders(conn, ros: list) -> int:
    """Loads historical repair orders"""
    cursor = conn.cursor()
    loaded = 0

    for ro in ros:
        try:
            cursor.execute("""
                INSERT INTO repair_orders (
                    ro_id, vin, customer_id, customer_name,
                    service_advisor_id, service_advisor_name,
                    technician_id, technician_name, bay,
                    fault_category, complaint_text, dtc_codes,
                    vehicle_make, vehicle_model, vehicle_year,
                    vehicle_fuel_type, is_ev_job,
                    parts_cost, labor_cost, subtotal,
                    discount_rate, discount_amount, gst_amount,
                    final_total, status, opened_at, closed_at,
                    month, year, warranty_claim
                ) VALUES (
                    %(ro_id)s, %(vin)s, %(customer_id)s,
                    %(customer_name)s, %(service_advisor_id)s,
                    %(service_advisor_name)s, %(technician_id)s,
                    %(technician_name)s, %(bay)s,
                    %(fault_category)s, %(complaint_text)s,
                    %(dtc_codes)s, %(vehicle_make)s,
                    %(vehicle_model)s, %(vehicle_year)s,
                    %(vehicle_fuel_type)s, %(is_ev_job)s,
                    %(parts_cost)s, %(labor_cost)s,
                    %(subtotal)s, %(discount_rate)s,
                    %(discount_amount)s, %(gst_amount)s,
                    %(final_total)s, %(status)s,
                    %(opened_at)s, %(closed_at)s,
                    %(month)s, %(year)s, %(warranty_claim)s
                )
                ON CONFLICT (ro_id) DO NOTHING
            """, {
                **ro,
                "dtc_codes": json.dumps(ro["dtc_codes"]),
            })
            loaded += 1
        except Exception as e:
            print_warning(f"Skipped RO {ro.get('ro_id')}: {e}")

    conn.commit()
    cursor.close()
    return loaded


# ── VALIDATION ─────────────────────────────────────────────────────────────────

def validate_data(conn) -> bool:
    """
    Runs basic sanity checks after loading
    Returns True if all checks pass
    """
    cursor = conn.cursor()
    checks_passed = True

    checks = [
        ("vehicles", "SELECT COUNT(*) FROM vehicles", 400),
        ("customers", "SELECT COUNT(*) FROM customers", 200),
        ("inventory", "SELECT COUNT(*) FROM inventory", 20),
        ("suppliers", "SELECT COUNT(*) FROM suppliers", 6),
        ("repair_orders", "SELECT COUNT(*) FROM repair_orders", 500),
        ("purchase_orders", "SELECT COUNT(*) FROM purchase_orders", 100),
    ]

    print(f"\n  {BOLD}Validation Checks:{RESET}")

    for name, query, min_expected in checks:
        try:
            cursor.execute(query)
            count = cursor.fetchone()[0]
            if count >= min_expected:
                print_success(f"{name}: {count} records (min: {min_expected})")
            else:
                print_warning(
                    f"{name}: {count} records "
                    f"(expected at least {min_expected})"
                )
                checks_passed = False
        except Exception as e:
            print_error(f"{name}: Query failed — {e}")
            checks_passed = False

    # Check relational integrity
    cursor.execute("""
        SELECT COUNT(*) FROM repair_orders ro
        LEFT JOIN vehicles v ON ro.vin = v.vin
        WHERE v.vin IS NULL
    """)
    orphan_ros = cursor.fetchone()[0]
    if orphan_ros == 0:
        print_success("Relational integrity: All RO VINs exist in vehicles")
    else:
        print_warning(f"Relational integrity: {orphan_ros} ROs with missing VINs")

    cursor.close()
    return checks_passed


# ── SUMMARY REPORT ─────────────────────────────────────────────────────────────

def print_summary_report(
    vehicles, parts, customers, suppliers,
    po_history, ros, elapsed_seconds
):
    print(f"\n{BOLD}{GREEN}")
    print("=" * 60)
    print("   CONDUIT Data Generation Complete!")
    print("=" * 60)
    print(f"{RESET}")

    print(f"\n{BOLD}Dataset Summary:{RESET}")
    print_stat("Vehicles generated", len(vehicles))
    print_stat(
        "EV vehicles",
        f"{sum(1 for v in vehicles if v['is_ev'])} "
        f"({sum(1 for v in vehicles if v['is_ev'])/len(vehicles)*100:.1f}%)"
    )
    print_stat("Parts catalog entries", len(parts))
    ev_parts = sum(1 for p in parts if p["category"] == "EV Components")
    print_stat("EV specific parts", ev_parts)
    print_stat("Customers generated", len(customers))
    gold = sum(1 for c in customers if c["loyalty_tier"] == 3)
    silver = sum(1 for c in customers if c["loyalty_tier"] == 2)
    print_stat("  Gold tier", gold)
    print_stat("  Silver tier", silver)
    print_stat("Suppliers loaded", len(suppliers))
    print_stat("Historical POs", len(po_history))
    print_stat("Historical ROs", len(ros))

    if ros:
        complete_ros = [r for r in ros if r["status"] == "COMPLETE"]
        if complete_ros:
            avg_val = sum(
                r["final_total"] for r in complete_ros
            ) / len(complete_ros)
            print_stat("Avg RO value", f"₹{avg_val:,.0f}")

        ev_ros = sum(1 for r in ros if r["is_ev_job"])
        print_stat("EV service jobs", ev_ros)

        categories = {}
        for r in ros:
            cat = r["fault_category"]
            categories[cat] = categories.get(cat, 0) + 1

        print(f"\n{BOLD}RO Category Distribution:{RESET}")
        for cat, count in sorted(
            categories.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            pct = count / len(ros) * 100
            bar = "█" * int(pct / 3)
            print(f"  {cat:<20} {bar:<15} {count:>4} ({pct:.1f}%)")

    print(f"\n{BOLD}Supplier Scorecard:{RESET}")
    sorted_suppliers = sorted(
        suppliers,
        key=lambda x: x["composite_score"],
        reverse=True
    )
    for s in sorted_suppliers:
        score = s["composite_score_pct"]
        bar = "█" * int(score / 10)
        print(f"  {s['short_name']:<25} {bar:<10} {score:.1f}%")

    critical_stock = sum(
        1 for p in parts if p["stock_status"] == "critical"
    )
    low_stock = sum(1 for p in parts if p["stock_status"] == "low")
    print(f"\n{BOLD}Inventory Health:{RESET}")
    print_stat("Critical stock parts", f"{critical_stock} ⚠")
    print_stat("Low stock parts", f"{low_stock} ⚡")

    print(f"\n{BOLD}Performance:{RESET}")
    print_stat("Total time", f"{elapsed_seconds:.1f} seconds")
    print(f"\n{GREEN}✓ Data is ready!{RESET}")
    print(f"\n{CYAN}Next step:{RESET} Run the Pinecone seed script:")
    print(f"  python data/seed/load_pinecone.py\n")


# ── MAIN ───────────────────────────────────────────────────────────────────────

def main():
    print_header()
    start_time = time.time()
    total_steps = 8

    # ── STEP 1: GENERATE ALL DATA ──────────────────────────────────────────────
    print_step(1, total_steps, "Generating vehicle catalog...")
    vehicles = generate_vehicles(n=500)
    print_success(f"Generated {len(vehicles)} vehicles")
    ev_count = sum(1 for v in vehicles if v["is_ev"])
    print_success(f"Including {ev_count} EV vehicles")

    print_step(2, total_steps, "Generating parts catalog...")
    parts = generate_parts()
    labor_ops = generate_labor_operations()
    print_success(f"Generated {len(parts)} parts")
    print_success(f"Generated {len(labor_ops)} labor operations")

    print_step(3, total_steps, "Generating customer profiles...")
    customers = generate_customers(n=300, vehicles=vehicles)
    print_success(f"Generated {len(customers)} customers")

    print_step(4, total_steps, "Generating supplier data...")
    suppliers, po_history = generate_suppliers()
    print_success(f"Generated {len(suppliers)} suppliers")
    print_success(f"Generated {len(po_history)} historical POs")

    print_step(5, total_steps, "Generating repair order history...")
    ros = generate_repair_orders(
        vehicles=vehicles,
        customers=customers,
        n_months=12,
        daily_ro_base=8
    )
    print_success(f"Generated {len(ros)} repair orders")

    # ── STEP 2: CONNECT TO DB ──────────────────────────────────────────────────
    print_step(6, total_steps, "Connecting to PostgreSQL...")
    try:
        conn = get_db_connection()
        print_success("Connected to PostgreSQL")
    except SystemExit:
        print_warning(
            "Database not available. Saving to JSON files instead..."
        )
        save_to_json(vehicles, parts, labor_ops, customers,
                     suppliers, po_history, ros)
        elapsed = time.time() - start_time
        print_summary_report(
            vehicles, parts, customers, suppliers,
            po_history, ros, elapsed
        )
        return

    # ── STEP 3: LOAD DATA ──────────────────────────────────────────────────────
    print_step(7, total_steps, "Loading data to PostgreSQL...")

    loaded = load_vehicles(conn, vehicles)
    print_success(f"Vehicles loaded: {loaded}/{len(vehicles)}")

    loaded = load_parts(conn, parts)
    print_success(f"Parts loaded: {loaded}/{len(parts)}")

    loaded = load_labor_operations(conn, labor_ops)
    print_success(f"Labor operations loaded: {loaded}/{len(labor_ops)}")

    loaded = load_customers(conn, customers)
    print_success(f"Customers loaded: {loaded}/{len(customers)}")

    loaded = load_suppliers(conn, suppliers)
    print_success(f"Suppliers loaded: {loaded}/{len(suppliers)}")

    loaded = load_po_history(conn, po_history)
    print_success(f"PO history loaded: {loaded}/{len(po_history)}")

    loaded = load_repair_orders(conn, ros)
    print_success(f"Repair orders loaded: {loaded}/{len(ros)}")

    # ── STEP 4: VALIDATE ───────────────────────────────────────────────────────
    print_step(8, total_steps, "Validating loaded data...")
    validation_passed = validate_data(conn)

    if validation_passed:
        print_success("All validation checks passed")
    else:
        print_warning("Some validation checks failed — review warnings above")

    conn.close()

    # ── SUMMARY ────────────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    print_summary_report(
        vehicles, parts, customers, suppliers,
        po_history, ros, elapsed
    )


def save_to_json(
    vehicles, parts, labor_ops, customers,
    suppliers, po_history, ros
):
    """
    Fallback: saves all data to JSON files
    Useful for development when DB is not running
    """
    output_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "output"
    )
    os.makedirs(output_dir, exist_ok=True)

    datasets = {
        "vehicles.json": vehicles,
        "parts.json": parts,
        "labor_operations.json": labor_ops,
        "customers.json": customers,
        "suppliers.json": suppliers,
        "po_history.json": po_history,
        "repair_orders.json": ros,
    }

    for filename, data in datasets.items():
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print_success(f"Saved {filename} ({len(data)} records)")

    print_success(f"All JSON files saved to {output_dir}")


if __name__ == "__main__":
    main()
