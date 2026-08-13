"""
WarehouseFlow — Sample Data Generator
Regenerates/expands dummy data for zones, racks, bins, SKUs, and pick tasks.

Run: python 02_generate_sample_data.py
Requires: 01_create_schema.py to have been run first (creates warehouseflow.db)
"""

import sqlite3
import random
from datetime import date, timedelta

DB_PATH = "warehouseflow.db"
random.seed(42)

# ---------- Config (tweak these to scale the dataset up/down) ----------
N_ZONES = 6
RACKS_PER_ZONE = 5
BINS_PER_RACK = 6
N_SKUS = 200
N_PICK_TASKS = 12000
PICK_HISTORY_DAYS = 90

CATEGORIES = ["Apparel", "Footwear", "Accessories", "Electronics", "Other"]
SHIFTS = ["Morning", "Afternoon", "Night"]
STRATEGIES = ["Single", "Batch", "Wave"]
PICKERS = [f"P{i}" for i in range(1, 13)]

PRODUCT_ADJ = ["Classic", "Premium", "Everyday", "Pro", "Compact", "Urban", "Essential", "Deluxe"]
PRODUCT_NOUN = {
    "Apparel": ["Tee", "Hoodie", "Jacket", "Joggers", "Cap"],
    "Footwear": ["Sneaker", "Sandal", "Boot", "Running Shoe", "Loafer"],
    "Accessories": ["Backpack", "Belt", "Wallet", "Sunglasses", "Watch"],
    "Electronics": ["Earbuds", "Charger", "Power Bank", "Cable", "Speaker"],
    "Other": ["Water Bottle", "Notebook", "Tote Bag", "Mug", "Organizer"],
}


def rand_date(days_back):
    return date.today() - timedelta(days=random.randint(0, days_back))


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Clear existing rows so this script can be re-run to "regenerate" data
    for table in ["pick_tasks", "skus", "bins", "racks", "zones"]:
        cur.execute(f"DELETE FROM {table}")

    # ---------- Zones ----------
    zones = []
    zone_words = ["Receiving", "Fast-Pick", "Bulk Storage", "Returns"]
    for i in range(1, N_ZONES + 1):
        zone_id = f"Z{i}"
        name = zone_words[(i - 1) % len(zone_words)]
        desc = f"{name} area, level {((i-1) % 2) + 1}"
        zones.append((zone_id, name, desc))
    cur.executemany("INSERT INTO zones (zone_id, zone_name, description) VALUES (?, ?, ?)", zones)

    # ---------- Racks ----------
    racks = []
    for zone_id, zone_name, _ in zones:
        for r in range(1, RACKS_PER_ZONE + 1):
            rack_id = f"{zone_id}-R{r}"
            racks.append((rack_id, zone_id, f"{zone_name} Rack {r}"))
    cur.executemany("INSERT INTO racks (rack_id, zone_id, rack_name) VALUES (?, ?, ?)", racks)

    # ---------- Bins ----------
    bins_ = []
    for rack_id, zone_id, _ in racks:
        base_dist = random.randint(5, 60)
        for b in range(1, BINS_PER_RACK + 1):
            bin_id = f"{rack_id}-B{b}"
            capacity = random.choice([30, 50, 75, 100])
            distance = base_dist + random.randint(-3, 3)
            bins_.append((bin_id, rack_id, zone_id, capacity, max(distance, 2)))
    cur.executemany(
        "INSERT INTO bins (bin_id, rack_id, zone_id, capacity, distance_to_dispatch_m) VALUES (?, ?, ?, ?, ?)",
        bins_,
    )

    # ---------- SKUs (assigned to random bins) ----------
    skus = []
    used_ids = set()
    for i in range(1, N_SKUS + 1):
        category = random.choice(CATEGORIES)
        product_name = f"{random.choice(PRODUCT_ADJ)} {random.choice(PRODUCT_NOUN[category])}"
        sku_id = f"SKU{i:03d}"
        bin_id, rack_id, zone_id, capacity, distance = random.choice(bins_)
        unit_cost = round(random.uniform(50, 4000), 2)
        assigned_date = rand_date(180).isoformat()
        skus.append((sku_id, product_name, category, bin_id, zone_id, distance, assigned_date, unit_cost))
        used_ids.add(sku_id)
    cur.executemany(
        """INSERT INTO skus
           (sku_id, product_name, category, bin_id, zone_id, distance_to_dispatch_m, assigned_date, unit_cost)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        skus,
    )

    # ---------- Pick tasks ----------
    # Give each SKU a random "popularity" weight so ABC pattern emerges naturally
    weights = {s[0]: random.paretovariate(1.5) for s in skus}
    sku_pool = list(used_ids)
    tasks = []
    for i in range(1, N_PICK_TASKS + 1):
        sku_id = random.choices(sku_pool, weights=[weights[s] for s in sku_pool], k=1)[0]
        sku_row = next(s for s in skus if s[0] == sku_id)
        bin_id, zone_id, base_dist = sku_row[3], sku_row[4], sku_row[5]
        strategy = random.choices(STRATEGIES, weights=[0.5, 0.35, 0.15])[0]
        shift = random.choice(SHIFTS)
        picker_id = random.choice(PICKERS)
        pick_date = rand_date(PICK_HISTORY_DAYS).isoformat()
        travel = max(round(base_dist + random.uniform(-5, 15), 1), 1)
        base_time = 20 if strategy == "Batch" else (35 if strategy == "Wave" else 30)
        pick_time = max(round(base_time + travel * 0.6 + random.uniform(-8, 12)), 5)
        had_error = 1 if random.random() < 0.04 else 0
        tasks.append((i, sku_id, bin_id, zone_id, picker_id, pick_date, shift, strategy, travel, pick_time, had_error))
    cur.executemany(
        """INSERT INTO pick_tasks
           (task_id, sku_id, bin_id, zone_id, picker_id, pick_date, shift, strategy,
            travel_distance_m, pick_time_seconds, had_error)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        tasks,
    )

    # ---------- ABC classification + 30-day pick frequency ----------
    # Standard Pareto split: top 20% of SKUs by pick volume = A, next 30% = B, rest = C
    cutoff_30d = (date.today() - timedelta(days=30)).isoformat()
    counts_all = {s: 0 for s in used_ids}
    counts_30d = {s: 0 for s in used_ids}
    for t in tasks:
        sku_id, pick_date = t[1], t[5]
        counts_all[sku_id] += 1
        if pick_date >= cutoff_30d:
            counts_30d[sku_id] += 1

    ranked = sorted(used_ids, key=lambda s: counts_all[s], reverse=True)
    n = len(ranked)
    a_cut = max(round(n * 0.2), 1)
    b_cut = max(round(n * 0.5), a_cut + 1)
    abc_map = {}
    for idx, sku_id in enumerate(ranked):
        abc_map[sku_id] = "A" if idx < a_cut else ("B" if idx < b_cut else "C")

    cur.executemany(
        "UPDATE skus SET abc_class = ?, pick_frequency_30d = ? WHERE sku_id = ?",
        [(abc_map[s], counts_30d[s], s) for s in used_ids],
    )

    conn.commit()
    conn.close()

    print(f"Done. Generated {len(zones)} zones, {len(racks)} racks, {len(bins_)} bins, "
          f"{len(skus)} SKUs, {len(tasks)} pick tasks -> {DB_PATH}")
    print(f"ABC split: A={sum(1 for v in abc_map.values() if v=='A')}, "
          f"B={sum(1 for v in abc_map.values() if v=='B')}, "
          f"C={sum(1 for v in abc_map.values() if v=='C')}")


if __name__ == "__main__":
    main()
