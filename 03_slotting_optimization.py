"""
WarehouseFlow - Phase 2: Slotting Optimization Logic
- Classifies every SKU as A/B/C based on 30-day pick frequency (Pareto/ABC analysis)
- Compares each SKU's current bin distance to the closest available bin
  matching its class (fast movers should sit in the closest bins)
- Recommends a relocation wherever a meaningfully closer bin is available
"""
import pandas as pd
from db import get_conn

conn = get_conn()

tasks = conn.read_df("SELECT * FROM PickTaskLog")
bins_df = conn.read_df("SELECT * FROM Bin")
assign_df = conn.read_df("SELECT * FROM SKUBinAssignment")
skus_df = conn.read_df("SELECT * FROM SKU")

# ---------- Step 1: Pick frequency per SKU (last 30 days) ----------
freq = tasks.groupby("sku_id").size().reset_index(name="pick_frequency_30d")
freq = freq.sort_values("pick_frequency_30d", ascending=False).reset_index(drop=True)

# ---------- Step 2: ABC classification (classic 80/15/5 split by rank) ----------
n = len(freq)
freq["rank_pct"] = (freq.index + 1) / n
def classify(pct):
    if pct <= 0.20:
        return "A"
    elif pct <= 0.50:
        return "B"
    else:
        return "C"
freq["abc_class"] = freq["rank_pct"].apply(classify)

# ---------- Step 3: Current bin + distance per SKU ----------
# Use the most recently assigned bin per SKU
current_assign = assign_df.sort_values("assigned_date").groupby("sku_id").last().reset_index()
current_assign = current_assign.merge(bins_df[["bin_id", "zone_id", "distance_to_dispatch_m"]], on="bin_id", how="left")
current_assign = current_assign.rename(columns={
    "bin_id": "current_bin_id", "zone_id": "current_zone_id", "distance_to_dispatch_m": "current_distance_m"
})

merged = freq.merge(current_assign[["sku_id", "current_bin_id", "current_zone_id", "current_distance_m"]], on="sku_id", how="left")

# ---------- Step 4: Recommend the closest available bin for A-class SKUs ----------
# Sort bins by distance so the closest ones are recommended first
bins_sorted = bins_df.sort_values("distance_to_dispatch_m")
closest_bins_list = list(zip(bins_sorted["bin_id"], bins_sorted["distance_to_dispatch_m"]))

recommendations = []
used_bins_for_a_class = set()

for _, row in merged.sort_values("pick_frequency_30d", ascending=False).iterrows():
    sku_id = row["sku_id"]
    current_bin = row["current_bin_id"]
    current_dist = row["current_distance_m"]
    abc = row["abc_class"]

    if abc == "A":
        # find the closest bin not already recommended to another A-class SKU
        best_bin, best_dist = None, None
        for bin_id, dist in closest_bins_list:
            if bin_id not in used_bins_for_a_class:
                best_bin, best_dist = bin_id, dist
                break
        if best_bin is not None:
            used_bins_for_a_class.add(best_bin)
            savings_per_pick = max(0, current_dist - best_dist)
            daily_picks_est = row["pick_frequency_30d"] / 30
            recommendations.append({
                "sku_id": sku_id,
                "current_bin_id": current_bin,
                "recommended_bin_id": best_bin if best_bin != current_bin else current_bin,
                "abc_class": abc,
                "pick_frequency_30d": int(row["pick_frequency_30d"]),
                "current_distance_m": round(current_dist, 1),
                "recommended_distance_m": round(best_dist, 1),
                "estimated_daily_savings_m": round(savings_per_pick * daily_picks_est, 1),
            })
    else:
        # B/C class: no active relocation push, recommendation = stay put
        recommendations.append({
            "sku_id": sku_id,
            "current_bin_id": current_bin,
            "recommended_bin_id": current_bin,
            "abc_class": abc,
            "pick_frequency_30d": int(row["pick_frequency_30d"]),
            "current_distance_m": round(current_dist, 1),
            "recommended_distance_m": round(current_dist, 1),
            "estimated_daily_savings_m": 0.0,
        })

rec_df = pd.DataFrame(recommendations)
rec_df = rec_df.sort_values("estimated_daily_savings_m", ascending=False)

# Save to DB (drop+recreate via pandas-free insert, since db.py has no to_sql helper)
conn.execute("DELETE FROM SlottingRecommendation")
for _, r in rec_df.iterrows():
    conn.execute("""
        INSERT INTO SlottingRecommendation
        (sku_id, current_bin_id, recommended_bin_id, abc_class, pick_frequency_30d,
         current_distance_m, recommended_distance_m, estimated_daily_savings_m)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        r["sku_id"], r["current_bin_id"], r["recommended_bin_id"], r["abc_class"],
        int(r["pick_frequency_30d"]), float(r["current_distance_m"]),
        float(r["recommended_distance_m"]), float(r["estimated_daily_savings_m"])
    ))
conn.commit()

n_relocate = (rec_df["current_bin_id"] != rec_df["recommended_bin_id"]).sum()
total_savings = rec_df["estimated_daily_savings_m"].sum()

print(f"Classified {len(rec_df)} SKUs: {(rec_df.abc_class=='A').sum()} A, "
      f"{(rec_df.abc_class=='B').sum()} B, {(rec_df.abc_class=='C').sum()} C")
print(f"{n_relocate} SKUs recommended for relocation")
print(f"Estimated total daily travel savings: {total_savings:.1f} meters")

conn.close()
