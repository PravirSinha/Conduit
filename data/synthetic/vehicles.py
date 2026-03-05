"""Synthetic vehicle catalog generator."""

from __future__ import annotations

import random
import string


_VEHICLE_OPTIONS = {
	"Toyota": ["Corolla", "Camry", "Fortuner", "Innova", "Yaris"],
	"Honda": ["City", "Civic", "Amaze", "Elevate", "CR-V"],
	"Hyundai": ["i20", "Verna", "Creta", "Alcazar", "Venue"],
	"Maruti": ["Swift", "Baleno", "Brezza", "Dzire", "Grand Vitara"],
	"Tata": ["Nexon", "Punch", "Harrier", "Safari", "Altroz"],
	"Mahindra": ["XUV700", "Scorpio", "Thar", "XUV300", "Bolero"],
	"Kia": ["Seltos", "Sonet", "Carens", "EV6", "Carnival"],
	"MG": ["Hector", "Astor", "ZS EV", "Comet", "Gloster"],
}

_COLORS = ["White", "Silver", "Black", "Grey", "Blue", "Red"]
_STATES = ["MH", "DL", "KA", "TN", "GJ", "UP", "RJ", "WB", "TS", "KL"]
_TRIMS = ["Base", "S", "SX", "ZX", "Premium", "Top"]


def _random_vin() -> str:
	chars = string.ascii_uppercase + string.digits
	return "".join(random.choices(chars, k=17))


def _registration_number(state: str) -> str:
	district = random.randint(1, 99)
	letters = "".join(random.choices(string.ascii_uppercase, k=2))
	digits = random.randint(1000, 9999)
	return f"{state}{district:02d}{letters}{digits}"


def generate_vehicles(n: int = 500) -> list[dict]:
	random.seed(42)
	vehicles: list[dict] = []

	makes = list(_VEHICLE_OPTIONS.keys())

	for _ in range(n):
		make = random.choice(makes)
		model = random.choice(_VEHICLE_OPTIONS[make])
		year = random.randint(2012, 2025)
		state = random.choice(_STATES)

		is_ev = model in {"EV6", "ZS EV", "Comet"}
		fuel_type = "electric" if is_ev else random.choice(["petrol", "diesel", "cng", "hybrid"])

		vehicles.append(
			{
				"vin": _random_vin(),
				"make": make,
				"model": model,
				"year": year,
				"trim": random.choice(_TRIMS),
				"fuel_type": fuel_type,
				"engine_code": f"{make[:2].upper()}-{random.randint(1000, 9999)}",
				"transmission": random.choice(["manual", "automatic", "amt", "cvt"]),
				"category": random.choice(["hatchback", "sedan", "suv", "mpv"]),
				"color": random.choice(_COLORS),
				"odometer_km": random.randint(5000, 180000),
				"registration_number": _registration_number(state),
				"registration_state": state,
				"warranty_expired": year <= 2020,
				"battery_capacity_kwh": round(random.uniform(18.0, 82.0), 1) if is_ev else None,
				"is_ev": is_ev,
			}
		)

	return vehicles

