"""
WarehouseFlow - Migrate Local Data to Turso (Cloud Database)
==============================================================
Run this ONCE, after setting these two environment variables to your real
Turso credentials:

    TURSO_DATABASE_URL   (starts with libsql://...)
    TURSO_AUTH_TOKEN     (long token string from Turso)

This copies your schema and all local data (warehouseflow.db) into Turso,
so the live app (with those same secrets configured) will keep and persist
every change made through the dashboard, forever - not just for the current
session.

Usage (Windows cmd):
    set TURSO_DATABASE_URL=libsql://your-db-name.turso.io
    set TURSO_AUTH_TOKEN=your-token-here
    python 06_migrate_to_turso.py
"""
import os
import sqlite3
import libsql_client

TURSO_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

if not TURSO_URL or not TURSO_TOKEN:
    raise SystemExit(
        "ERROR: TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must both be set as "
        "environment variables before running this script. See the docstring "
        "at the top of this file for instructions."
    )

print(f"Connecting to Turso at {TURSO_URL} ...")
client = libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)

print("Connecting to local warehouseflow.db ...")
local = sqlite3.connect("warehouseflow.db")
local.row_factory = sqlite3.Row

print("Creating schema on Turso ...")
schema_statements = [
    """CREATE TABLE IF NOT EXISTS Zone (
        zone_id TEXT PRIMARY KEY, zone_name TEXT NOT NULL, description TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS Rack (
        rack_id TEXT PRIMARY KEY, zone_id TEXT NOT NULL, rack_name TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS Bin (
        bin_id TEXT PRIMARY KEY, rack_id TEXT NOT NULL, zone_id TEXT NOT NULL,
        bin_code TEXT NOT NULL, capacity INTEGER, distance_to_dispatch_m REAL NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS SKU (
        sku_id TEXT PRIMARY KEY, product_name TEXT NOT NULL, category TEXT, unit_cost REAL
    )""",
    """CREATE TABLE IF NOT EXISTS SKUBinAssignment (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sku_id TEXT NOT NULL,
        bin_id TEXT NOT NULL, assigned_date TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS PickTaskLog (
        task_id INTEGER PRIMARY KEY AUTOINCREMENT, sku_id TEXT NOT NULL, bin_id TEXT NOT NULL,
        zone_id TEXT NOT NULL, picker_id TEXT NOT NULL, pick_date TEXT NOT NULL,
        shift TEXT, strategy TEXT, travel_distance_m REAL NOT NULL,
        pick_time_seconds REAL NOT NULL, had_error INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS SlottingRecommendation (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sku_id TEXT NOT NULL, current_bin_id TEXT NOT NULL,
        recommended_bin_id TEXT NOT NULL, abc_class TEXT, pick_frequency_30d INTEGER,
        current_distance_m REAL, recommended_distance_m REAL, estimated_daily_savings_m REAL
    )""",
]
for stmt in schema_statements:
    client.execute(stmt)

tables = ["Zone", "Rack", "Bin", "SKU", "SKUBinAssignment", "PickTaskLog", "SlottingRecommendation"]

for table in tables:
    print(f"Copying table: {table} ...")
    rows = local.execute(f"SELECT * FROM {table}").fetchall()
    if not rows:
        print(f"  (no rows in {table}, skipping)")
        continue
    columns = rows[0].keys()
    placeholders = ",".join(["?"] * len(columns))
    col_list = ",".join(columns)
    # Clear existing data on Turso first so re-running this script is safe
    client.execute(f"DELETE FROM {table}")
    for row in rows:
        values = [row[c] for c in columns]
        client.execute(f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})", values)
    print(f"  Copied {len(rows)} rows.")

local.close()
client.close()
print("\nMigration complete! Your Turso database now has all your local WarehouseFlow data.")
