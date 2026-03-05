"""
CONDUIT — Synthetic Parts Catalog Generator
Generates realistic automotive parts with compatibility matrix
This is the most critical dataset — Pinecone RAG is built on this
"""

import random
from typing import List, Dict

SEED = 42
random.seed(SEED)


# ── PARTS MASTER DATA ─────────────────────────────────────────────────────────
# Structured by category → subcategory → individual parts
# Each part has OEM + aftermarket options and vehicle compatibility

PARTS_MASTER = [

    # ── BRAKES ──────────────────────────────────────────────────────────────
    {
        "category": "Brakes",
        "subcategory": "Brake Pads",
        "parts": [
            {
                "part_number": "BRK-PAD-HON-F-01",
                "description": "Front disc brake pads Honda City Amaze 2019-2023 petrol diesel",
                "oem_part_number": "45022-T9A-H01",
                "brand": "Honda Genuine",
                "unit_of_measure": "Set",
                "unit_cost": 3850,
                "sell_price": 5200,
                "compatible_makes": ["Honda"],
                "compatible_models": ["City", "Amaze"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023],
                "compatible_fuel_types": ["Petrol", "Diesel"],
                "shelf_life_days": None,
                "weight_kg": 0.8,
                "bin_location": "A-14",
                "reorder_point": 10,
                "reorder_quantity": 24,
            },
            {
                "part_number": "BRK-PAD-HON-F-02-AM",
                "description": "Front brake pads aftermarket Honda City Amaze Brembo compatible",
                "oem_part_number": None,
                "brand": "Brembo",
                "unit_of_measure": "Set",
                "unit_cost": 1800,
                "sell_price": 2800,
                "compatible_makes": ["Honda"],
                "compatible_models": ["City", "Amaze"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023],
                "compatible_fuel_types": ["Petrol", "Diesel"],
                "shelf_life_days": None,
                "weight_kg": 0.8,
                "bin_location": "A-15",
                "reorder_point": 12,
                "reorder_quantity": 30,
            },
            {
                "part_number": "BRK-PAD-HYN-F-01",
                "description": "Front disc brake pads Hyundai Creta i20 2019-2024 all variants",
                "oem_part_number": "58101-H1A00",
                "brand": "Hyundai Genuine",
                "unit_of_measure": "Set",
                "unit_cost": 3600,
                "sell_price": 4900,
                "compatible_makes": ["Hyundai"],
                "compatible_models": ["Creta", "i20"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Petrol", "Diesel"],
                "shelf_life_days": None,
                "weight_kg": 0.75,
                "bin_location": "A-16",
                "reorder_point": 10,
                "reorder_quantity": 24,
            },
            {
                "part_number": "BRK-PAD-MAR-F-01",
                "description": "Front brake pads Maruti Swift Baleno Brezza petrol 2019-2024",
                "oem_part_number": "55810-77R00",
                "brand": "Maruti Genuine",
                "unit_of_measure": "Set",
                "unit_cost": 2800,
                "sell_price": 3900,
                "compatible_makes": ["Maruti"],
                "compatible_models": ["Swift", "Baleno", "Brezza"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Petrol"],
                "shelf_life_days": None,
                "weight_kg": 0.7,
                "bin_location": "A-17",
                "reorder_point": 15,
                "reorder_quantity": 36,
            },
            {
                "part_number": "BRK-PAD-TAT-F-01",
                "description": "Front brake pads Tata Nexon petrol diesel 2019-2024 XE XM XT XZ",
                "oem_part_number": "270920100120",
                "brand": "Tata Genuine",
                "unit_of_measure": "Set",
                "unit_cost": 3200,
                "sell_price": 4400,
                "compatible_makes": ["Tata"],
                "compatible_models": ["Nexon"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Petrol", "Diesel"],
                "shelf_life_days": None,
                "weight_kg": 0.75,
                "bin_location": "A-18",
                "reorder_point": 10,
                "reorder_quantity": 24,
            },
        ]
    },

    # ── BRAKE ROTORS ────────────────────────────────────────────────────────
    {
        "category": "Brakes",
        "subcategory": "Brake Rotors",
        "parts": [
            {
                "part_number": "BRK-ROT-HON-F-01",
                "description": "Front brake disc rotor Honda City 2019-2023 280mm ventilated",
                "oem_part_number": "45251-T9A-000",
                "brand": "Honda Genuine",
                "unit_of_measure": "Each",
                "unit_cost": 4200,
                "sell_price": 5800,
                "compatible_makes": ["Honda"],
                "compatible_models": ["City"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023],
                "compatible_fuel_types": ["Petrol", "Diesel"],
                "shelf_life_days": None,
                "weight_kg": 4.2,
                "bin_location": "B-07",
                "reorder_point": 8,
                "reorder_quantity": 16,
            },
            {
                "part_number": "BRK-ROT-HYN-F-01",
                "description": "Front brake rotor disc Hyundai Creta 2019-2024 300mm",
                "oem_part_number": "51712-H1000",
                "brand": "Hyundai Genuine",
                "unit_of_measure": "Each",
                "unit_cost": 4800,
                "sell_price": 6500,
                "compatible_makes": ["Hyundai"],
                "compatible_models": ["Creta"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Petrol", "Diesel"],
                "shelf_life_days": None,
                "weight_kg": 5.1,
                "bin_location": "B-08",
                "reorder_point": 6,
                "reorder_quantity": 12,
            },
        ]
    },

    # ── FILTERS ─────────────────────────────────────────────────────────────
    {
        "category": "Filters",
        "subcategory": "Oil Filters",
        "parts": [
            {
                "part_number": "FLT-OIL-HON-01",
                "description": "Engine oil filter Honda City Amaze 1.5L petrol diesel 2019-2023",
                "oem_part_number": "15400-RBA-F01",
                "brand": "Honda Genuine",
                "unit_of_measure": "Each",
                "unit_cost": 380,
                "sell_price": 580,
                "compatible_makes": ["Honda"],
                "compatible_models": ["City", "Amaze"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023],
                "compatible_fuel_types": ["Petrol", "Diesel"],
                "shelf_life_days": 730,
                "weight_kg": 0.15,
                "bin_location": "C-01",
                "reorder_point": 30,
                "reorder_quantity": 60,
            },
            {
                "part_number": "FLT-OIL-UNI-01",
                "description": "Universal oil filter M20x1.5 thread pitch Maruti Hyundai Kia compatible",
                "oem_part_number": None,
                "brand": "Bosch",
                "unit_of_measure": "Each",
                "unit_cost": 220,
                "sell_price": 380,
                "compatible_makes": ["Maruti", "Hyundai", "Kia"],
                "compatible_models": [
                    "Swift", "Baleno", "Brezza",
                    "i20", "Creta", "Sonet", "Seltos"
                ],
                "compatible_years": [2019, 2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Petrol", "Diesel"],
                "shelf_life_days": 730,
                "weight_kg": 0.12,
                "bin_location": "C-02",
                "reorder_point": 50,
                "reorder_quantity": 100,
            },
            {
                "part_number": "FLT-OIL-TAT-01",
                "description": "Oil filter Tata Nexon Punch 1.2L Revotron 2019-2024",
                "oem_part_number": "272060700106",
                "brand": "Tata Genuine",
                "unit_of_measure": "Each",
                "unit_cost": 350,
                "sell_price": 520,
                "compatible_makes": ["Tata"],
                "compatible_models": ["Nexon", "Punch"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Petrol", "Diesel"],
                "shelf_life_days": 730,
                "weight_kg": 0.13,
                "bin_location": "C-03",
                "reorder_point": 25,
                "reorder_quantity": 50,
            },
        ]
    },

    # ── AIR FILTERS ─────────────────────────────────────────────────────────
    {
        "category": "Filters",
        "subcategory": "Air Filters",
        "parts": [
            {
                "part_number": "FLT-AIR-HON-01",
                "description": "Engine air filter Honda City Amaze 1.5L 2019-2023 panel type",
                "oem_part_number": "17220-5PA-000",
                "brand": "Honda Genuine",
                "unit_of_measure": "Each",
                "unit_cost": 650,
                "sell_price": 950,
                "compatible_makes": ["Honda"],
                "compatible_models": ["City", "Amaze"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023],
                "compatible_fuel_types": ["Petrol", "Diesel"],
                "shelf_life_days": None,
                "weight_kg": 0.3,
                "bin_location": "C-10",
                "reorder_point": 20,
                "reorder_quantity": 40,
            },
            {
                "part_number": "FLT-AIR-MAR-01",
                "description": "Air filter Maruti Swift Baleno Brezza K12N K15C engine 2019-2024",
                "oem_part_number": "13780-84M00",
                "brand": "Maruti Genuine",
                "unit_of_measure": "Each",
                "unit_cost": 480,
                "sell_price": 720,
                "compatible_makes": ["Maruti"],
                "compatible_models": ["Swift", "Baleno", "Brezza"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Petrol"],
                "shelf_life_days": None,
                "weight_kg": 0.25,
                "bin_location": "C-11",
                "reorder_point": 25,
                "reorder_quantity": 50,
            },
        ]
    },

    # ── FLUIDS ──────────────────────────────────────────────────────────────
    {
        "category": "Fluids",
        "subcategory": "Engine Oil",
        "parts": [
            {
                "part_number": "FLD-OIL-5W30-4L",
                "description": "Engine oil 5W-30 fully synthetic 4 litre petrol engines universal",
                "oem_part_number": None,
                "brand": "Castrol",
                "unit_of_measure": "4L Can",
                "unit_cost": 1800,
                "sell_price": 2600,
                "compatible_makes": [
                    "Honda", "Hyundai", "Maruti",
                    "Tata", "Kia", "MG", "Toyota"
                ],
                "compatible_models": ["All"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Petrol"],
                "shelf_life_days": 1825,
                "weight_kg": 3.6,
                "bin_location": "D-01",
                "reorder_point": 40,
                "reorder_quantity": 80,
            },
            {
                "part_number": "FLD-OIL-5W40-4L",
                "description": "Engine oil 5W-40 fully synthetic 4 litre diesel engines",
                "oem_part_number": None,
                "brand": "Mobil1",
                "unit_of_measure": "4L Can",
                "unit_cost": 2200,
                "sell_price": 3200,
                "compatible_makes": [
                    "Honda", "Hyundai", "Tata", "Kia", "MG", "Toyota"
                ],
                "compatible_models": ["All"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Diesel"],
                "shelf_life_days": 1825,
                "weight_kg": 3.6,
                "bin_location": "D-02",
                "reorder_point": 30,
                "reorder_quantity": 60,
            },
            {
                "part_number": "FLD-CLT-UNI-1L",
                "description": "Coolant concentrate universal 1 litre all makes 2019-2024",
                "oem_part_number": None,
                "brand": "Prestone",
                "unit_of_measure": "1L Bottle",
                "unit_cost": 420,
                "sell_price": 650,
                "compatible_makes": [
                    "Honda", "Hyundai", "Maruti",
                    "Tata", "Kia", "MG", "Toyota"
                ],
                "compatible_models": ["All"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Petrol", "Diesel"],
                "shelf_life_days": 730,
                "weight_kg": 1.05,
                "bin_location": "D-05",
                "reorder_point": 30,
                "reorder_quantity": 60,
            },
            {
                "part_number": "FLD-ATF-UNI-1L",
                "description": "ATF hydraulic fluid automatic transmission 1 litre Hyundai Kia Honda",
                "oem_part_number": None,
                "brand": "Valvoline",
                "unit_of_measure": "1L Bottle",
                "unit_cost": 580,
                "sell_price": 850,
                "compatible_makes": ["Honda", "Hyundai", "Kia"],
                "compatible_models": [
                    "City", "Creta", "i20", "Seltos", "Sonet"
                ],
                "compatible_years": [2019, 2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Petrol", "Diesel"],
                "shelf_life_days": 1095,
                "weight_kg": 0.9,
                "bin_location": "D-06",
                "reorder_point": 20,
                "reorder_quantity": 48,
            },
        ]
    },

    # ── BATTERIES ───────────────────────────────────────────────────────────
    {
        "category": "Electrical",
        "subcategory": "Batteries",
        "parts": [
            {
                "part_number": "BAT-12V-35AH",
                "description": "12V 35Ah MF battery small cars Maruti Swift Baleno i20 2019-2024",
                "oem_part_number": None,
                "brand": "Amaron",
                "unit_of_measure": "Each",
                "unit_cost": 3200,
                "sell_price": 4500,
                "compatible_makes": ["Maruti", "Hyundai"],
                "compatible_models": ["Swift", "Baleno", "i20"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Petrol"],
                "shelf_life_days": None,
                "weight_kg": 9.5,
                "bin_location": "E-01",
                "reorder_point": 8,
                "reorder_quantity": 20,
            },
            {
                "part_number": "BAT-12V-55AH",
                "description": "12V 55Ah MF battery mid-size cars Honda City Creta Nexon 2019-2024",
                "oem_part_number": None,
                "brand": "Exide",
                "unit_of_measure": "Each",
                "unit_cost": 4800,
                "sell_price": 6500,
                "compatible_makes": ["Honda", "Hyundai", "Tata", "Kia", "MG"],
                "compatible_models": [
                    "City", "Amaze", "Creta", "Nexon",
                    "Seltos", "Sonet", "Hector"
                ],
                "compatible_years": [2019, 2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Petrol", "Diesel"],
                "shelf_life_days": None,
                "weight_kg": 14.2,
                "bin_location": "E-02",
                "reorder_point": 6,
                "reorder_quantity": 16,
            },
            {
                "part_number": "BAT-12V-75AH",
                "description": "12V 75Ah MF battery SUV Fortuner Innova diesel 2019-2023",
                "oem_part_number": None,
                "brand": "Amaron",
                "unit_of_measure": "Each",
                "unit_cost": 7200,
                "sell_price": 9800,
                "compatible_makes": ["Toyota"],
                "compatible_models": ["Fortuner", "Innova Crysta"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023],
                "compatible_fuel_types": ["Petrol", "Diesel"],
                "shelf_life_days": None,
                "weight_kg": 19.5,
                "bin_location": "E-03",
                "reorder_point": 4,
                "reorder_quantity": 10,
            },
        ]
    },

    # ── SPARK PLUGS ─────────────────────────────────────────────────────────
    {
        "category": "Ignition",
        "subcategory": "Spark Plugs",
        "parts": [
            {
                "part_number": "IGN-SPK-NGK-IRI-01",
                "description": "NGK iridium spark plug Honda City Amaze 1.5L petrol 4 cylinder",
                "oem_part_number": "DILZKAR7C11GS",
                "brand": "NGK",
                "unit_of_measure": "Each",
                "unit_cost": 850,
                "sell_price": 1200,
                "compatible_makes": ["Honda"],
                "compatible_models": ["City", "Amaze"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023],
                "compatible_fuel_types": ["Petrol"],
                "shelf_life_days": None,
                "weight_kg": 0.05,
                "bin_location": "F-01",
                "reorder_point": 20,
                "reorder_quantity": 48,
            },
            {
                "part_number": "IGN-SPK-UNI-01",
                "description": "Bosch platinum spark plug Maruti Hyundai Kia 1.0L 1.2L 1.5L petrol",
                "oem_part_number": None,
                "brand": "Bosch",
                "unit_of_measure": "Each",
                "unit_cost": 420,
                "sell_price": 650,
                "compatible_makes": ["Maruti", "Hyundai", "Kia"],
                "compatible_models": [
                    "Swift", "Baleno", "Brezza",
                    "i20", "Creta", "Sonet", "Seltos"
                ],
                "compatible_years": [2019, 2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Petrol"],
                "shelf_life_days": None,
                "weight_kg": 0.04,
                "bin_location": "F-02",
                "reorder_point": 30,
                "reorder_quantity": 60,
            },
        ]
    },

    # ── SUSPENSION ──────────────────────────────────────────────────────────
    {
        "category": "Suspension",
        "subcategory": "Shock Absorbers",
        "parts": [
            {
                "part_number": "SUS-SHK-HON-F-01",
                "description": "Front shock absorber Honda City 2019-2023 KYB original equipment",
                "oem_part_number": "51606-T9A-H01",
                "brand": "KYB",
                "unit_of_measure": "Each",
                "unit_cost": 4200,
                "sell_price": 6000,
                "compatible_makes": ["Honda"],
                "compatible_models": ["City"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023],
                "compatible_fuel_types": ["Petrol", "Diesel"],
                "shelf_life_days": None,
                "weight_kg": 3.8,
                "bin_location": "G-01",
                "reorder_point": 4,
                "reorder_quantity": 8,
            },
            {
                "part_number": "SUS-SHK-HYN-F-01",
                "description": "Front shock absorber Hyundai Creta 2019-2024 Gabriel",
                "oem_part_number": "54661-FCA00",
                "brand": "Gabriel",
                "unit_of_measure": "Each",
                "unit_cost": 3800,
                "sell_price": 5500,
                "compatible_makes": ["Hyundai"],
                "compatible_models": ["Creta"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Petrol", "Diesel"],
                "shelf_life_days": None,
                "weight_kg": 4.1,
                "bin_location": "G-02",
                "reorder_point": 4,
                "reorder_quantity": 8,
            },
        ]
    },

    # ── EV SPECIFIC ─────────────────────────────────────────────────────────
    {
        "category": "EV Components",
        "subcategory": "EV Battery",
        "parts": [
            {
                "part_number": "EV-BAT-NEX-MOD-01",
                "description": "Tata Nexon EV battery module Ziptron 30.2kWh cell replacement",
                "oem_part_number": "270920100NEX-EV",
                "brand": "Tata Genuine",
                "unit_of_measure": "Each",
                "unit_cost": 185000,
                "sell_price": 220000,
                "compatible_makes": ["Tata"],
                "compatible_models": ["Nexon EV"],
                "compatible_years": [2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Electric"],
                "shelf_life_days": None,
                "weight_kg": 52.0,
                "bin_location": "EV-01",
                "reorder_point": 1,
                "reorder_quantity": 2,
            },
            {
                "part_number": "EV-BAT-ZS-MOD-01",
                "description": "MG ZS EV battery module 44.5kWh replacement high voltage",
                "oem_part_number": "MGZSEV-BAT-001",
                "brand": "MG Genuine",
                "unit_of_measure": "Each",
                "unit_cost": 245000,
                "sell_price": 290000,
                "compatible_makes": ["MG"],
                "compatible_models": ["ZS EV"],
                "compatible_years": [2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Electric"],
                "shelf_life_days": None,
                "weight_kg": 68.0,
                "bin_location": "EV-02",
                "reorder_point": 1,
                "reorder_quantity": 2,
            },
            {
                "part_number": "EV-OBC-NEX-01",
                "description": "Tata Nexon EV onboard charger 3.3kW AC charger unit replacement",
                "oem_part_number": "270920100OBC-NEX",
                "brand": "Tata Genuine",
                "unit_of_measure": "Each",
                "unit_cost": 42000,
                "sell_price": 52000,
                "compatible_makes": ["Tata"],
                "compatible_models": ["Nexon EV"],
                "compatible_years": [2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Electric"],
                "shelf_life_days": None,
                "weight_kg": 8.5,
                "bin_location": "EV-03",
                "reorder_point": 1,
                "reorder_quantity": 2,
            },
        ]
    },

    # ── WIPER BLADES ────────────────────────────────────────────────────────
    {
        "category": "Exterior",
        "subcategory": "Wiper Blades",
        "parts": [
            {
                "part_number": "WIP-BLD-UNI-24",
                "description": "Universal wiper blade 24 inch frameless all makes Honda Hyundai Maruti",
                "oem_part_number": None,
                "brand": "Bosch",
                "unit_of_measure": "Each",
                "unit_cost": 380,
                "sell_price": 580,
                "compatible_makes": [
                    "Honda", "Hyundai", "Maruti",
                    "Tata", "Kia", "MG", "Toyota"
                ],
                "compatible_models": ["All"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023, 2024],
                "compatible_fuel_types": ["Petrol", "Diesel", "Electric"],
                "shelf_life_days": 730,
                "weight_kg": 0.2,
                "bin_location": "H-01",
                "reorder_point": 20,
                "reorder_quantity": 40,
            },
        ]
    },

    # ── TIMING BELTS ────────────────────────────────────────────────────────
    {
        "category": "Engine",
        "subcategory": "Timing Belt",
        "parts": [
            {
                "part_number": "ENG-TMB-HON-DSL-01",
                "description": "Timing belt kit Honda City Amaze 1.5L diesel N16A1 engine complete",
                "oem_part_number": "14400-RBD-E01",
                "brand": "Honda Genuine",
                "unit_of_measure": "Kit",
                "unit_cost": 8500,
                "sell_price": 12000,
                "compatible_makes": ["Honda"],
                "compatible_models": ["City", "Amaze"],
                "compatible_years": [2019, 2020, 2021, 2022, 2023],
                "compatible_fuel_types": ["Diesel"],
                "shelf_life_days": None,
                "weight_kg": 0.8,
                "bin_location": "I-01",
                "reorder_point": 4,
                "reorder_quantity": 8,
            },
        ]
    },
]


# ── LABOR OPERATIONS CATALOG ──────────────────────────────────────────────────

LABOR_OPERATIONS = [
    {
        "operation_code": "BRK-001",
        "description": "Front brake pad replacement disc brakes",
        "flat_rate_hours": 1.2,
        "skill_level": "Technician",
        "related_parts_categories": ["Brake Pads"],
        "rate_per_hour": 1200,
    },
    {
        "operation_code": "BRK-002",
        "description": "Front brake rotor replacement disc",
        "flat_rate_hours": 1.8,
        "skill_level": "Technician",
        "related_parts_categories": ["Brake Rotors"],
        "rate_per_hour": 1200,
    },
    {
        "operation_code": "BRK-003",
        "description": "Complete front brake service pads rotors caliper",
        "flat_rate_hours": 2.5,
        "skill_level": "Technician",
        "related_parts_categories": ["Brake Pads", "Brake Rotors"],
        "rate_per_hour": 1200,
    },
    {
        "operation_code": "SVC-001",
        "description": "Engine oil and oil filter change",
        "flat_rate_hours": 0.5,
        "skill_level": "Apprentice",
        "related_parts_categories": ["Oil Filters", "Engine Oil"],
        "rate_per_hour": 800,
    },
    {
        "operation_code": "SVC-002",
        "description": "Full periodic service oil filter air filter spark plugs",
        "flat_rate_hours": 1.5,
        "skill_level": "Apprentice",
        "related_parts_categories": ["Oil Filters", "Air Filters",
                                      "Spark Plugs", "Engine Oil"],
        "rate_per_hour": 800,
    },
    {
        "operation_code": "BAT-001",
        "description": "Battery replacement and charging system check",
        "flat_rate_hours": 0.5,
        "skill_level": "Apprentice",
        "related_parts_categories": ["Batteries"],
        "rate_per_hour": 800,
    },
    {
        "operation_code": "SUS-001",
        "description": "Front shock absorber replacement pair",
        "flat_rate_hours": 2.0,
        "skill_level": "Technician",
        "related_parts_categories": ["Shock Absorbers"],
        "rate_per_hour": 1200,
    },
    {
        "operation_code": "WHE-001",
        "description": "Wheel alignment and balancing four wheels",
        "flat_rate_hours": 0.8,
        "skill_level": "Apprentice",
        "related_parts_categories": [],
        "rate_per_hour": 800,
    },
    {
        "operation_code": "ENG-001",
        "description": "Timing belt kit replacement complete",
        "flat_rate_hours": 4.5,
        "skill_level": "Master Technician",
        "related_parts_categories": ["Timing Belt"],
        "rate_per_hour": 1500,
    },
    {
        "operation_code": "EV-001",
        "description": "EV battery module replacement high voltage system",
        "flat_rate_hours": 6.0,
        "skill_level": "EV Certified",
        "related_parts_categories": ["EV Battery"],
        "rate_per_hour": 2000,
    },
    {
        "operation_code": "EV-002",
        "description": "EV onboard charger replacement and system diagnostics",
        "flat_rate_hours": 3.5,
        "skill_level": "EV Certified",
        "related_parts_categories": ["EV Battery"],
        "rate_per_hour": 2000,
    },
]


def generate_parts() -> List[Dict]:
    """
    Flattens the nested PARTS_MASTER into a flat list of parts
    Adds random current stock levels for simulation
    """
    parts = []

    for category_group in PARTS_MASTER:
        category = category_group["category"]
        subcategory = category_group["subcategory"]

        for part in category_group["parts"]:
            # Add category info
            part["category"] = category
            part["subcategory"] = subcategory

            # Generate realistic current stock
            # Some parts are low/critical for demo purposes
            reorder_pt = part["reorder_point"]

            stock_scenario = random.choices(
                ["healthy", "low", "critical", "overstocked"],
                weights=[60, 20, 10, 10],
                k=1
            )[0]

            if stock_scenario == "healthy":
                qty_on_hand = random.randint(
                    reorder_pt + 1,
                    reorder_pt * 3
                )
            elif stock_scenario == "low":
                qty_on_hand = random.randint(
                    max(1, reorder_pt - 3),
                    reorder_pt
                )
            elif stock_scenario == "critical":
                qty_on_hand = random.randint(1, 3)
            else:
                qty_on_hand = random.randint(
                    reorder_pt * 3,
                    reorder_pt * 5
                )

            part["qty_on_hand"] = qty_on_hand
            part["qty_reserved"] = 0
            part["stock_status"] = stock_scenario

            parts.append(part)

    return parts


def generate_labor_operations() -> List[Dict]:
    return LABOR_OPERATIONS


if __name__ == "__main__":
    parts = generate_parts()
    labor = generate_labor_operations()

    print(f"Generated {len(parts)} parts")
    print(f"Generated {len(labor)} labor operations")

    categories = {}
    for p in parts:
        cat = p["category"]
        categories[cat] = categories.get(cat, 0) + 1
    print(f"\nBy category: {categories}")

    ev_parts = [p for p in parts if p["category"] == "EV Components"]
    print(f"\nEV parts: {len(ev_parts)}")

    critical = [p for p in parts if p["stock_status"] == "critical"]
    print(f"Critical stock parts: {len(critical)}")

    import json
    print(f"\nSample part:")
    print(json.dumps(parts[0], indent=2))