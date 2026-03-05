"""Synthetic repair order history generator."""

from __future__ import annotations

import random
from datetime import datetime, timedelta


_FAULT_MAP = {
	"Routine Service": ["Periodic service", "Oil change and inspection", "Scheduled maintenance"],
	"Brake System": ["Brake noise while driving", "Brake pedal feels soft", "Brake warning light on"],
	"Engine": ["Engine misfire", "Check engine light", "Overheating concern"],
	"Electrical": ["Battery drains overnight", "Starter issue", "Headlamp flickering"],
	"Suspension": ["Unusual suspension noise", "Vehicle pulling to one side", "Steering vibration"],
	"EV System": ["Charging interruption", "Reduced EV range", "High-voltage warning"],
}


def generate_repair_orders(
	vehicles: list[dict],
	customers: list[dict],
	n_months: int = 12,
	daily_ro_base: int = 8,
) -> list[dict]:
	random.seed(404)
	if not vehicles or not customers:
		return []

	now = datetime.utcnow()
	orders: list[dict] = []
	order_counter = 1

	customer_by_vin: dict[str, dict] = {}
	for customer in customers:
		for vin in customer.get("vehicle_vins", []):
			customer_by_vin.setdefault(vin, customer)

	advisor_ids = ["SA-001", "SA-002", "SA-003", "SA-004"]
	advisor_names = ["Ravi", "Nitin", "Shreya", "Pallavi"]
	tech_ids = ["TECH-011", "TECH-012", "TECH-013", "TECH-014", "TECH-015"]
	tech_names = ["Aman", "Kishore", "Rakesh", "Mahesh", "Fahad"]

	total_days = max(1, n_months * 30)
	for day_offset in range(total_days):
		opened_day = now - timedelta(days=day_offset)
		orders_today = max(1, int(random.gauss(daily_ro_base, 2)))

		for _ in range(orders_today):
			vehicle = random.choice(vehicles)
			customer = customer_by_vin.get(vehicle["vin"], random.choice(customers))
			fault_category = random.choice(list(_FAULT_MAP.keys()))
			complaint = random.choice(_FAULT_MAP[fault_category])

			parts_cost = round(random.uniform(300, 16000), 2)
			labor_cost = round(random.uniform(450, 6500), 2)
			subtotal = round(parts_cost + labor_cost, 2)

			discount_rate = random.choice([0.0, 0.03, 0.05, 0.1])
			discount_amount = round(subtotal * discount_rate, 2)
			taxable = subtotal - discount_amount
			gst_amount = round(taxable * 0.18, 2)
			final_total = round(taxable + gst_amount, 2)

			opened_at = opened_day.replace(hour=random.randint(8, 16), minute=random.randint(0, 59), second=0, microsecond=0)
			closed_at = opened_at + timedelta(hours=random.randint(2, 48))
			status = random.choices(["COMPLETE", "IN_PROGRESS", "CLOSED"], weights=[75, 10, 15], k=1)[0]

			orders.append(
				{
					"ro_id": f"RO-{opened_at.strftime('%Y%m')}-{order_counter:06d}",
					"vin": vehicle["vin"],
					"customer_id": customer["customer_id"],
					"customer_name": customer["full_name"],
					"service_advisor_id": random.choice(advisor_ids),
					"service_advisor_name": random.choice(advisor_names),
					"technician_id": random.choice(tech_ids),
					"technician_name": random.choice(tech_names),
					"bay": f"BAY-{random.randint(1, 12):02d}",
					"fault_category": fault_category,
					"complaint_text": complaint,
					"dtc_codes": [f"P{random.randint(1000, 2999)}"] if random.random() < 0.35 else [],
					"vehicle_make": vehicle["make"],
					"vehicle_model": vehicle["model"],
					"vehicle_year": vehicle["year"],
					"vehicle_fuel_type": vehicle["fuel_type"],
					"is_ev_job": bool(vehicle["is_ev"]),
					"parts_cost": parts_cost,
					"labor_cost": labor_cost,
					"subtotal": subtotal,
					"discount_rate": discount_rate,
					"discount_amount": discount_amount,
					"gst_amount": gst_amount,
					"final_total": final_total,
					"status": status,
					"opened_at": opened_at,
					"closed_at": closed_at,
					"month": opened_at.month,
					"year": opened_at.year,
					"warranty_claim": random.random() < 0.18,
				}
			)
			order_counter += 1

	return orders

