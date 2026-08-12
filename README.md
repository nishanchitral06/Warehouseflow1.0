<p align="center">
  <img src="https://img.shields.io/badge/WarehouseFlow-1.0-C1502E?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTIwIDhIMTBsLTIgNC0yLTRINCI+PC9wYXRoPjwvc3ZnPg==&logoColor=white" alt="WarehouseFlow Badge"/>
</p>

<h1 align="center">📦 WarehouseFlow 1.0</h1>

<p align="center">
  <b>Smart Warehouse Slotting & Picking Optimization Dashboard</b>
</p>

<p align="center">
  <a href="https://warehouseflow1-0.onrender.com"><img src="https://img.shields.io/badge/🌐_Live_Demo-warehouseflow1--0.onrender.com-2D9CDB?style=for-the-badge" alt="Live Demo"/></a>
  &nbsp;
  <a href="https://github.com/nishanchitral06/Warehouseflow1.0"><img src="https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub Repo"/></a>
</p>


---

## 🔗 Quick Links

| Resource | URL |
|----------|-----|
| **🌐 Live Demo** | [warehouseflow1-0.onrender.com](https://warehouseflow1-0.onrender.com) |
| **📂 GitHub Repo** | [github.com/nishanchitral06/Warehouseflow1.0](https://github.com/nishanchitral06/Warehouseflow1.0) |

---

## 📖 About

**WarehouseFlow** is a full-stack warehouse management dashboard that optimizes product slotting and picking workflows. It uses **ABC analysis** (Pareto classification) to recommend optimal bin placements for high-frequency SKUs, reducing travel distance and improving pick-rate efficiency.

Built with a Flask REST API backend and a single-page interactive dashboard frontend using Plotly.js for rich data visualizations — all deployable to the cloud with zero configuration.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 📊 **Operations Dashboard** | Real-time KPIs — picks/hour, error rate, avg travel distance, weekly trends |
| 🧮 **ABC Slotting Optimization** | Pareto-based classification (A/B/C) with smart bin relocation recommendations |
| 🔍 **Picking Workflow Analysis** | Filter by zone, shift, and strategy; identify bottlenecks instantly |
| 🗂️ **Data Browser** | Explore zones, racks, bins, and SKU assignments interactively |
| ➕ **CRUD Operations** | Add/delete zones, bins, SKUs; reassign SKUs to bins; log picks — all from the UI |
| 🌙 **Dark / Light Mode** | Elegant theme toggle with smooth transitions |
| ☁️ **Dual Database Support** | Seamless switching between local SQLite and Turso cloud DB |

---

## 🏗️ Tech Stack

```
Frontend     →  HTML5 · CSS3 (custom properties) · Vanilla JS · Plotly.js
Backend      →  Python · Flask · Gunicorn
Data Layer   →  Pandas · NumPy
Database     →  SQLite (local) / Turso (cloud, libsql-client)
Deployment   →  Render (PaaS)
```

---

## 📁 Project Structure

```
WarehouseFlow1.0/
├── app.py                         # Flask web server & REST API
├── db.py                          # Database abstraction (SQLite ↔ Turso)
├── index.html                     # Single-page dashboard (template)
├── requirements.txt               # Python dependencies
├── Procfile                       # Render deployment config
├── warehouseflow.db               # Local SQLite database (sample data)
├── 01_create_schema.py            # Database schema setup script
├── 02_generate_sample_data.py     # Sample data generator
├── 03_slotting_optimization.py    # ABC analysis & slotting engine
├── 04_picking_workflow_analysis.py# Picking workflow analysis script
└── 06_migrate_to_turso.py         # Migration script: SQLite → Turso
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/nishanchitral06/Warehouseflow1.0.git
cd Warehouseflow1.0

# 2. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

### Run Locally

```bash
python app.py
```

Open your browser at **http://localhost:5000** — the dashboard loads instantly.

### Set Up the Database (Optional)

If you want to start fresh or regenerate sample data:

```bash
python 01_create_schema.py           # Create tables
python 02_generate_sample_data.py    # Generate sample data
python 03_slotting_optimization.py   # Run ABC slotting optimization
```

### Cloud Database (Turso)

To use Turso instead of local SQLite, set these environment variables:

```bash
export TURSO_DATABASE_URL="libsql://your-db.turso.io"
export TURSO_AUTH_TOKEN="your-auth-token"
```

The app automatically detects and switches to Turso when these are present.

---

## 🔌 API Reference

### Read Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/overview` | Dashboard KPIs, zone distribution, weekly trends |
| `GET` | `/api/slotting` | Slotting recommendations (filterable by ABC class) |
| `GET` | `/api/picking` | Picking task analysis (filterable by zone/shift/strategy) |
| `GET` | `/api/browse/zones` | List all zones and racks |
| `GET` | `/api/browse/bins` | List all bins (searchable) |
| `GET` | `/api/browse/skus` | List all SKUs with current assignments |
| `GET` | `/api/dropdowns` | Dropdown values for forms |

### Write Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/add_zone` | Create a new zone |
| `POST` | `/api/add_bin` | Create a new bin |
| `POST` | `/api/add_sku` | Create a new SKU |
| `POST` | `/api/reassign_sku` | Reassign a SKU to a different bin |
| `POST` | `/api/log_pick` | Log a pick task |
| `POST` | `/api/delete_bin` | Delete a bin and its references |
| `POST` | `/api/delete_sku` | Delete a SKU and its references |

---

## 🗄️ Database Schema

```
┌──────────────────────┐     ┌──────────────────────┐
│        Zone          │     │        Rack          │
├──────────────────────┤     ├──────────────────────┤
│ zone_id    (PK)      │◄────│ zone_id    (FK)      │
│ zone_name            │     │ rack_id    (PK)      │
│ description          │     │ rack_name            │
└──────────────────────┘     └──────────────────────┘
         │                            │
         ▼                            ▼
┌──────────────────────────────────────────────┐
│                    Bin                       │
├──────────────────────────────────────────────┤
│ bin_id  (PK) │ rack_id (FK) │ zone_id (FK)  │
│ bin_code     │ capacity     │ distance_to_  │
│              │              │ dispatch_m    │
└──────────────────────────────────────────────┘
         │                          │
         ▼                          ▼
┌────────────────────┐   ┌─────────────────────────┐
│       SKU          │   │   SKUBinAssignment      │
├────────────────────┤   ├─────────────────────────┤
│ sku_id     (PK)    │◄──│ sku_id    (FK)          │
│ product_name       │   │ bin_id    (FK)          │
│ category           │   │ assigned_date           │
│ unit_cost          │   └─────────────────────────┘
└────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│              PickTaskLog                     │
├──────────────────────────────────────────────┤
│ task_id (PK) │ sku_id    │ bin_id   │ zone_id│
│ picker_id    │ pick_date │ shift    │strategy│
│ travel_distance_m  │ pick_time_seconds      │
│ had_error                                    │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│         SlottingRecommendation               │
├──────────────────────────────────────────────┤
│ sku_id │ current_bin_id │ recommended_bin_id │
│ abc_class  │ pick_frequency_30d              │
│ current_distance_m │ recommended_distance_m  │
│ estimated_daily_savings_m                    │
└──────────────────────────────────────────────┘
```

---

## 🧠 How Slotting Optimization Works

1. **Pick Frequency Calculation** — Counts picks per SKU over the last 30 days
2. **ABC Classification** — Top 20% by frequency → **A**, next 30% → **B**, bottom 50% → **C**
3. **Bin Matching** — A-class SKUs are matched to the closest-to-dispatch bins
4. **Savings Estimation** — `(current_distance - recommended_distance) × daily_picks`
5. **Recommendations** — Results are saved and displayed on the dashboard with estimated daily travel savings in meters

---

## 🌐 Deployment

The app is deployed on **[Render](https://render.com)** using the included `Procfile`:

```
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

To deploy your own instance:
1. Fork the [repository](https://github.com/nishanchitral06/Warehouseflow1.0)
2. Connect to Render and create a new **Web Service**
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `gunicorn app:app`
5. *(Optional)* Add `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` as environment variables

---

## 👤 Author

**Nishan C**
Logistics & Supply Chain Intern

---

## 📜 License

This project was developed as part of a minor project submission for the Logistics & Supply Chain Internship at Persevex. All rights reserved.
</p>
