"""
WarehouseFlow - Database Schema Setup
Creates all core tables. Works with either local SQLite or Turso (via db.py).
"""
from db import get_conn

conn = get_conn()

conn.executescript("""
DROP TABLE IF EXISTS Zone;
DROP TABLE IF EXISTS Rack;
DROP TABLE IF EXISTS Bin;
DROP TABLE IF EXISTS SKU;
DROP TABLE IF EXISTS SKUBinAssignment;
DROP TABLE IF EXISTS PickTaskLog;
DROP TABLE IF EXISTS SlottingRecommendation;

CREATE TABLE Zone (
    zone_id TEXT PRIMARY KEY,
    zone_name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE Rack (
    rack_id TEXT PRIMARY KEY,
    zone_id TEXT NOT NULL,
    rack_name TEXT NOT NULL
);

CREATE TABLE Bin (
    bin_id TEXT PRIMARY KEY,
    rack_id TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    bin_code TEXT NOT NULL,
    capacity INTEGER,
    distance_to_dispatch_m REAL NOT NULL
);

CREATE TABLE SKU (
    sku_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT,
    unit_cost REAL
);

CREATE TABLE SKUBinAssignment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id TEXT NOT NULL,
    bin_id TEXT NOT NULL,
    assigned_date TEXT NOT NULL
);

CREATE TABLE PickTaskLog (
    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id TEXT NOT NULL,
    bin_id TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    picker_id TEXT NOT NULL,
    pick_date TEXT NOT NULL,
    shift TEXT CHECK(shift IN ('Morning','Afternoon','Night')),
    strategy TEXT CHECK(strategy IN ('Single','Batch','Wave')),
    travel_distance_m REAL NOT NULL,
    pick_time_seconds REAL NOT NULL,
    had_error INTEGER DEFAULT 0
);

CREATE TABLE SlottingRecommendation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id TEXT NOT NULL,
    current_bin_id TEXT NOT NULL,
    recommended_bin_id TEXT NOT NULL,
    abc_class TEXT,
    pick_frequency_30d INTEGER,
    current_distance_m REAL,
    recommended_distance_m REAL,
    estimated_daily_savings_m REAL
);
""")

conn.commit()
conn.close()
print("Schema created: WarehouseFlow tables (Zone, Rack, Bin, SKU, SKUBinAssignment, PickTaskLog, SlottingRecommendation)")
