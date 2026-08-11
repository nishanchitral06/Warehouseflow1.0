# WarehouseFlow — Slotting and Picking Efficiency Optimizer
## (Flask version — no Streamlit — built for Render)

Logistics & Supply Chain Internship Project (Persevex)

## What This Is
A plain Flask web app (HTML/CSS/JS frontend + JSON API backend) that maps
a warehouse (zones, racks, bins), classifies products by pick frequency
(ABC analysis), recommends moving fast-moving products closer to dispatch,
and tracks picking performance across shifts, zones, and picking
strategies (Single / Batch / Wave). No Streamlit dependency anywhere.

## Project Structure
| File | Purpose |
|---|---|
| `app.py` | Flask app — serves the dashboard page and all JSON API endpoints |
| `templates/index.html` | The entire frontend — tabs, sidebar forms, charts (Plotly.js via CDN), tables |
| `db.py` | Database layer — auto-switches between Turso (cloud) and local SQLite |
| `01_create_schema.py` | Creates the database schema |
| `02_generate_sample_data.py` | Generates zones, racks, bins, SKUs, 30 days of pick logs |
| `03_slotting_optimization.py` | ABC classification + relocation recommendations |
| `04_picking_workflow_analysis.py` | Prints a strategy/bottleneck summary (optional, for sanity-checking data) |
| `06_migrate_to_turso.py` | One-time script to migrate local data to Turso |
| `warehouseflow.db` | Local database snapshot (for offline/local runs) |
| `requirements.txt` | Flask, gunicorn, pandas, numpy, libsql-client — no Streamlit |
| `Procfile` | Tells Render how to start the app (`gunicorn app:app`) |

## How to Run Locally
```bash
pip install -r requirements.txt
python app.py
```
Then open http://localhost:5000 in your browser. Runs against the included
local `warehouseflow.db` by default.

---

## Deploying to Render (with Turso for persistent storage)

### Step 1 — Push this whole folder to GitHub
Create a new repo and upload every file here, including the `templates`
folder with `index.html` inside it (folder structure must be preserved —
Flask looks for `templates/index.html` specifically).

### Step 2 — Create a Turso database
1. Sign up free at https://turso.tech
2. Create a new database (closest region to you)
3. Create a Database Token: **Expires: Never**, **Authorization: Read & Write**
4. Copy your Database URL (`libsql://...`) and the token somewhere safe

### Step 3 — Migrate your local data to Turso
On your machine, in this folder:
```bash
pip install libsql-client
set TURSO_DATABASE_URL=libsql://your-db-url-here
set TURSO_AUTH_TOKEN=your-token-here
python 06_migrate_to_turso.py
```

### Step 4 — Deploy on Render
1. Go to https://render.com → sign in with GitHub
2. **New +** → **Web Service** → select your repo
3. Settings:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Instance Type:** Free
4. Environment Variables:
   - `TURSO_DATABASE_URL` = your Turso URL
   - `TURSO_AUTH_TOKEN` = your Turso token
5. Click **Create Web Service**

Your live app will be at `https://<your-service-name>.onrender.com`. Since
it's backed by Turso instead of a local file, every SKU, bin, or pick task
added through the dashboard persists permanently — across restarts and
redeploys.

## Note on Render's Free Tier
Render's free web services sleep after ~15 minutes of no traffic, and wake
automatically on the next visit (unlike Streamlit Cloud, a simple uptime
ping actually works here to keep it awake, since Render treats any HTTP
request as real traffic).
