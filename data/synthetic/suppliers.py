"""Synthetic supplier and PO history generator."""

from __future__ import annotations

import random
from datetime import datetime


def generate_suppliers(n_suppliers: int = 8, n_months: int = 12) -> tuple[list[dict], list[dict]]:
	random.seed(303)

	base_names = [
		"Prime Auto Spares", "Velocity Components", "Metro Parts Hub", "AxlePoint Distributors",
		"Torque Supplies", "EV Motion Parts", "Reliance Auto Link", "Zenith Fleet Components",
	]
	cities = [("Mumbai", "MH"), ("Delhi", "DL"), ("Bengaluru", "KA"), ("Chennai", "TN")]
	categories = ["Filters", "Brakes", "Engine", "Electrical", "Suspension", "EV Components"]

	suppliers: list[dict] = []
	for index in range(1, n_suppliers + 1):
		on_time = round(random.uniform(0.78, 0.99), 2)
		fill_rate = round(random.uniform(0.75, 0.98), 2)
		composite_score = round((on_time * 0.55) + (fill_rate * 0.45), 4)
		city, state = random.choice(cities)

		suppliers.append(
			{
				"supplier_id": f"SUP-{index:04d}",
				"name": base_names[index - 1] if index <= len(base_names) else f"Supplier {index}",
				"short_name": f"SUP{index:02d}",
				"type": random.choice(["OEM", "Distributor", "Regional"]),
				"integration_type": random.choice(["API", "EDI", "Email"]),
				"specialization": random.sample(categories, k=random.randint(1, 3)),
				"categories_supplied": random.sample(categories, k=random.randint(2, 4)),
				"current_on_time_rate": on_time,
				"current_fill_rate": fill_rate,
				"composite_score": composite_score,
				"composite_score_pct": round(composite_score * 100, 1),
				"lead_time_days": random.randint(2, 12),
				"min_order_value": round(random.uniform(5000, 40000), 2),
				"payment_terms_days": random.choice([15, 30, 45]),
				"city": city,
				"state": state,
				"contact_email": f"procurement{index}@supplier.example.com",
				"api_capable": random.random() < 0.6,
				"reliability_tier": random.choice(["A", "B", "C"]),
			}
		)

	po_history: list[dict] = []
	now = datetime.utcnow()
	po_counter = 1
	for month_offset in range(n_months):
		month = ((now.month - month_offset - 1) % 12) + 1
		year = now.year - ((now.month - month_offset - 1) // 12 < 0)

		for supplier in suppliers:
			orders_this_month = random.randint(4, 8)
			for _ in range(orders_this_month):
				on_time = random.random() < supplier["current_on_time_rate"]
				days_late = 0 if on_time else random.randint(1, 10)
				fill_rate = round(random.uniform(0.75, 1.0), 2)
				partial = fill_rate < 0.95

				po_history.append(
					{
						"po_id": f"PO-HIST-{po_counter:06d}",
						"supplier_id": supplier["supplier_id"],
						"po_value": round(random.uniform(8000, 150000), 2),
						"on_time": on_time,
						"days_late": days_late,
						"fill_rate": fill_rate,
						"partial_delivery": partial,
						"status": "RECEIVED",
						"month": month,
						"year": year,
					}
				)
				po_counter += 1

	return suppliers, po_history

