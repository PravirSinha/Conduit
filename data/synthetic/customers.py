"""Synthetic customer profile generator."""

from __future__ import annotations

import random


_FIRST_NAMES = [
	"Aarav", "Vivaan", "Aditya", "Ishaan", "Arjun", "Rohan", "Karan", "Rahul", "Neha", "Aisha",
	"Priya", "Ananya", "Diya", "Meera", "Kavya", "Sneha", "Pooja", "Riya", "Nisha", "Tanvi",
]
_LAST_NAMES = [
	"Sharma", "Verma", "Gupta", "Patel", "Reddy", "Nair", "Iyer", "Kapoor", "Singh", "Joshi",
]
_CITIES = [
	("Mumbai", "MH"), ("Delhi", "DL"), ("Bengaluru", "KA"), ("Chennai", "TN"),
	("Pune", "MH"), ("Ahmedabad", "GJ"), ("Hyderabad", "TS"), ("Kochi", "KL"),
]


def generate_customers(n: int = 300, vehicles: list[dict] | None = None) -> list[dict]:
	random.seed(202)
	vehicles = vehicles or []
	vehicle_vins = [vehicle["vin"] for vehicle in vehicles]

	customers: list[dict] = []
	for index in range(1, n + 1):
		first_name = random.choice(_FIRST_NAMES)
		last_name = random.choice(_LAST_NAMES)
		full_name = f"{first_name} {last_name}"
		city, state = random.choice(_CITIES)

		loyalty_tier = random.choices([1, 2, 3], weights=[65, 25, 10], k=1)[0]
		tier_name = {1: "Bronze", 2: "Silver", 3: "Gold"}[loyalty_tier]
		discount_rate = {1: 0.0, 2: 5.0, 3: 10.0}[loyalty_tier]

		linked_vins = random.sample(vehicle_vins, k=min(len(vehicle_vins), random.choice([1, 1, 1, 2]))) if vehicle_vins else []

		customers.append(
			{
				"customer_id": f"CUST-{index:05d}",
				"first_name": first_name,
				"last_name": last_name,
				"full_name": full_name,
				"phone": f"+91-{random.randint(7000000000, 9999999999)}",
				"email": f"{first_name.lower()}.{last_name.lower()}{index}@example.com",
				"area": random.choice(["North", "South", "East", "West", "Central"]),
				"city": city,
				"state": state,
				"pincode": str(random.randint(100000, 999999)),
				"occupation": random.choice(["Engineer", "Doctor", "Teacher", "Business", "Consultant"]),
				"loyalty_tier": loyalty_tier,
				"loyalty_tier_name": tier_name,
				"discount_rate": discount_rate,
				"total_visits": random.randint(1, 24),
				"payment_behavior": random.choice(["on_time", "delayed", "advance"]),
				"avg_payment_days": random.randint(0, 35),
				"preferred_contact": random.choice(["phone", "email", "whatsapp"]),
				"vehicle_vins": linked_vins,
				"is_corporate": random.random() < 0.12,
				"marketing_consent": random.random() < 0.75,
			}
		)

	return customers

