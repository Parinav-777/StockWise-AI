# Data dictionary
## sales.csv
date (YYYY-MM-DD, required), product_id (must exist in products), quantity (number >= 0). One row per product per day; duplicates and existing date+product rows are skipped; negatives rejected.
## inventory.csv
Required: product_id, name, unit_cost (>=0), stock (>=0). Optional: category (General), price (blank = no revenue), min_stock (0), incoming (0), lead_days (blank = 3-day default in restock calculations).
## Demo data
Synthetic, seed 42, 16 products, 120 days. Inserted anomaly: P03 Lays Chips, 70 units, 10 days before the end. P14 trends up, P12 trends down. Not real-world evidence.
