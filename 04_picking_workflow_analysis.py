"""
WarehouseFlow - Phase 3: Picking Workflow Performance
- Compares Single / Batch / Wave picking strategies on speed and accuracy
- Calculates picks/hour, error rate, and average cycle time
- Flags bottleneck zones and shifts (slowest average pick time)
This script summarizes the PickTaskLog data already generated in Phase 1/2 -
it doesn't need to write new tables, since the dashboard reads PickTaskLog
directly and computes these views live. Running it here just prints a
sanity-check summary so you can confirm the data looks reasonable.
"""
import pandas as pd
from db import get_conn

conn = get_conn()
tasks = conn.read_df("SELECT * FROM PickTaskLog")
conn.close()

tasks["pick_time_hours"] = tasks["pick_time_seconds"] / 3600

print("=== Strategy Comparison ===")
strategy_summary = tasks.groupby("strategy").agg(
    avg_travel_m=("travel_distance_m", "mean"),
    avg_pick_time_s=("pick_time_seconds", "mean"),
    error_rate_pct=("had_error", lambda x: 100 * x.mean()),
    total_picks=("task_id", "count"),
).round(2)
print(strategy_summary.to_string())

print("\n=== Picks per Hour (overall) ===")
total_hours = tasks["pick_time_hours"].sum()
picks_per_hour = len(tasks) / total_hours if total_hours else 0
print(f"{picks_per_hour:.1f} picks/hour (based on cumulative pick time across all tasks)")

print("\n=== Bottleneck Zones (by average pick time) ===")
zone_summary = tasks.groupby("zone_id").agg(
    avg_pick_time_s=("pick_time_seconds", "mean"),
    total_picks=("task_id", "count"),
    error_rate_pct=("had_error", lambda x: 100 * x.mean()),
).round(2).sort_values("avg_pick_time_s", ascending=False)
print(zone_summary.to_string())

print("\n=== Bottleneck Shifts (by average pick time) ===")
shift_summary = tasks.groupby("shift").agg(
    avg_pick_time_s=("pick_time_seconds", "mean"),
    total_picks=("task_id", "count"),
    error_rate_pct=("had_error", lambda x: 100 * x.mean()),
).round(2).sort_values("avg_pick_time_s", ascending=False)
print(shift_summary.to_string())

print("\nDone. The dashboard (05_dashboard.py) reads PickTaskLog directly for live views of all of this.")
