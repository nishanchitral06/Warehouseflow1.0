"""
WarehouseFlow - Sample Data Generator
Creates a warehouse layout (zones, racks, bins), SKUs, current bin
assignments, and 30 days of simulated pick task logs.
"""
import random
import numpy as np
from datetime import datetime, timedelta
from db import get_conn

random.seed(11)
np.random.seed(11)

conn = get_conn()

# ---------- Zones ----------
zones = [
    ("Z1", "Fast-Pick Zone (near dispatch)", "Closest zone to packing/dispatch"),
    ("Z2", "Bulk Storage Zone", "Mid-distance general storage"),
    ("Z3", "Reserve Zone", "Furthest zone, overflow/reserve stock"),
]
for z in zones:
    conn.execute("INSERT INTO Zone (zone_id, zone_name, description) VALUES (?,?,?)", z)

# ---------- Racks (3 per zone) ----------
racks = []
for zone_id, base_dist in [("Z1", 10), ("Z2", 40), ("Z3", 80)]:
    for r in range(1, 4):
        rack_id = f"{zone_id}-R{r}"
        racks.append((rack_id, zone_id, f"Rack {r} ({zone_id})"))
for r in racks:
    conn.execute("INSERT INTO Rack (rack_id, zone_id, rack_name) VALUES (?,?,?)", r)

# ---------- Bins (4 per rack) ----------
bins_ = []
zone_base_distance = {"Z1": 10, "Z2": 40, "Z3": 80}
for rack_id, zone_id, _ in racks:
    base = zone_base_distance[zone_id]
    for b in range(1, 5):
        bin_id = f"{rack_id}-B{b}"
        bin_code = f"{rack_id}-B{b}"
        distance = base + random.uniform(0, 15) + (b * 1.5)
        bins_.append((bin_id, rack_id, zone_id, bin_code, 50, round(distance, 1)))
for b in bins_:
    conn.execute(
        "INSERT INTO Bin (bin_id, rack_id, zone_id, bin_code, capacity, distance_to_dispatch_m) VALUES (?,?,?,?,?,?)",
        b
    )

# ---------- SKUs ----------
categories = ["Apparel", "Footwear", "Accessories", "Electronics"]
skus = []
for i in range(1, 31):
    sku_id = f"SKU{i:03d}"
    name = f"Product {i}"
    category = random.choice(categories)
    unit_cost = round(random.uniform(100, 3000), 2)
    skus.append((sku_id, name, category, unit_cost))
for s in skus:
    conn.execute("INSERT INTO SKU (sku_id, product_name, category, unit_cost) VALUES (?,?,?,?)", s)

# ---------- Initial (often suboptimal) Bin Assignments ----------
# Deliberately scatter some fast-moving SKUs into far bins, to give the
# slotting engine something meaningful to fix.
all_bin_ids = [b[0] for b in bins_]
assign_date = "2026-07-01"
sku_velocity_tier = {}  # sku_id -> intended pick frequency tier, used to bias assignment
for idx, (sku_id, *_ ) in enumerate(skus):
    if idx < 6:
        tier = "fast"
    elif idx < 15:
        tier = "medium"
    else:
        tier = "slow"
    sku_velocity_tier[sku_id] = tier

    # Deliberately misplace ~half the fast movers into far bins (Z3) to
    # simulate a real, imperfect warehouse layout.
    if tier == "fast" and idx % 2 == 0:
        candidate_bins = [b for b in all_bin_ids if b.startswith("Z3")]
    else:
        candidate_bins = all_bin_ids
    chosen_bin = random.choice(candidate_bins)
    conn.execute(
        "INSERT INTO SKUBinAssignment (sku_id, bin_id, assigned_date) VALUES (?,?,?)",
        (sku_id, chosen_bin, assign_date)
    )
conn.commit()

# ---------- Pick Task Logs (30 days) ----------
bin_lookup = {b[0]: b for b in bins_}  # bin_id -> (bin_id, rack_id, zone_id, code, cap, dist)
sku_bin = {}
# fetch what we just assigned (re-derive in python since we just inserted it)
conn2 = get_conn()
assign_df = conn2.read_df("SELECT sku_id, bin_id FROM SKUBinAssignment")
for _, row in assign_df.iterrows():
    sku_bin[row["sku_id"]] = row["bin_id"]

pickers = [f"P{i}" for i in range(1, 7)]
shifts = ["Morning", "Afternoon", "Night"]
strategies = ["Single", "Batch", "Wave"]
start_date = datetime(2026, 7, 1)

task_rows = []
for day in range(30):
    date_str = (start_date + timedelta(days=day)).strftime("%Y-%m-%d")
    for sku_id in [s[0] for s in skus]:
        tier = sku_velocity_tier[sku_id]
        base_picks = {"fast": 8, "medium": 3, "slow": 1}[tier]
        n_picks_today = np.random.poisson(base_picks)
        bin_id = sku_bin[sku_id]
        _, rack_id, zone_id, _, _, distance = bin_lookup[bin_id]
        for _ in range(n_picks_today):
            strategy = random.choices(strategies, weights=[0.5, 0.35, 0.15])[0]
            # batch/wave picking reduces effective travel distance per pick
            strategy_factor = {"Single": 1.0, "Batch": 0.7, "Wave": 0.55}[strategy]
            travel = max(2, distance * strategy_factor + np.random.normal(0, 3))
            pick_time = max(8, travel * 0.9 + np.random.normal(15, 4))
            had_error = 1 if np.random.rand() < 0.03 else 0
            picker = random.choice(pickers)
            shift = random.choice(shifts)
            task_rows.append((
                sku_id, bin_id, zone_id, picker, date_str, shift, strategy,
                round(travel, 1), round(pick_time, 1), had_error
            ))

conn.executemany("""
    INSERT INTO PickTaskLog
    (sku_id, bin_id, zone_id, picker_id, pick_date, shift, strategy, travel_distance_m, pick_time_seconds, had_error)
    VALUES (?,?,?,?,?,?,?,?,?,?)
""", task_rows)

conn.commit()
conn.close()
print(f"Sample data generated: {len(zones)} zones, {len(racks)} racks, {len(bins_)} bins, "
      f"{len(skus)} SKUs, {len(assign_df)} bin assignments, {len(task_rows)} pick task logs")
