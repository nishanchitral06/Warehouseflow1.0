"""
WarehouseFlow - Flask Web App (no Streamlit)
==============================================
Run locally:    python app.py
Run on Render:  gunicorn app:app
"""
import os
import re
from datetime import date
from flask import Flask, render_template, request, jsonify
from db import get_conn, DBIntegrityError

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Read APIs
# ---------------------------------------------------------------------------
@app.route("/api/overview")
def api_overview():
    conn = get_conn()
    tasks = conn.read_df("SELECT * FROM PickTaskLog")
    zones = conn.read_df("SELECT * FROM Zone")
    slotting = conn.read_df("SELECT * FROM SlottingRecommendation")
    conn.close()

    total_picks = len(tasks)
    avg_travel = float(tasks["travel_distance_m"].mean()) if not tasks.empty else 0
    error_rate = float(100 * tasks["had_error"].mean()) if not tasks.empty else 0
    total_hours = float(tasks["pick_time_seconds"].sum() / 3600) if not tasks.empty else 0
    picks_per_hour = (total_picks / total_hours) if total_hours else 0
    n_relocate = int((slotting["current_bin_id"] != slotting["recommended_bin_id"]).sum()) if not slotting.empty else 0
    total_savings = float(slotting["estimated_daily_savings_m"].sum()) if not slotting.empty else 0

    zone_counts = []
    if not tasks.empty:
        zc = tasks.groupby("zone_id").size().reset_index(name="picks")
        zc = zc.merge(zones[["zone_id", "zone_name"]], on="zone_id", how="left")
        zone_counts = zc.to_dict(orient="records")

    strategy_summary = []
    if not tasks.empty:
        st_ = tasks.groupby("strategy").agg(avg_time=("pick_time_seconds", "mean")).reset_index()
        strategy_summary = st_.to_dict(orient="records")

    weekly = []
    if not tasks.empty:
        t2 = tasks.copy()
        t2["pick_date"] = pd_to_datetime(t2["pick_date"])
        t2["week"] = t2["pick_date"].dt.isocalendar().week
        w = t2.groupby("week").agg(picks=("task_id", "count")).reset_index()
        weekly = w.to_dict(orient="records")

    return jsonify({
        "picks_per_hour": round(picks_per_hour, 1),
        "total_picks": total_picks,
        "error_rate": round(error_rate, 1),
        "avg_travel": round(avg_travel, 1),
        "n_relocate": n_relocate,
        "total_savings": round(total_savings, 1),
        "zone_counts": zone_counts,
        "strategy_summary": strategy_summary,
        "weekly": weekly,
    })


def pd_to_datetime(series):
    import pandas as pd
    return pd.to_datetime(series)


@app.route("/api/slotting")
def api_slotting():
    conn = get_conn()
    slotting = conn.read_df("SELECT * FROM SlottingRecommendation")
    conn.close()

    abc_filter = request.args.getlist("class")
    only_moves = request.args.get("only_moves", "false") == "true"

    if abc_filter:
        slotting = slotting[slotting["abc_class"].isin(abc_filter)]
    if only_moves:
        slotting = slotting[slotting["current_bin_id"] != slotting["recommended_bin_id"]]

    slotting = slotting.sort_values("estimated_daily_savings_m", ascending=False)
    return jsonify(slotting.to_dict(orient="records"))


@app.route("/api/picking")
def api_picking():
    conn = get_conn()
    tasks = conn.read_df("SELECT * FROM PickTaskLog")
    conn.close()

    zone = request.args.get("zone", "All")
    shift = request.args.get("shift", "All")
    strategy = request.args.get("strategy", "All")

    f = tasks.copy()
    if zone != "All":
        f = f[f.zone_id == zone]
    if shift != "All":
        f = f[f.shift == shift]
    if strategy != "All":
        f = f[f.strategy == strategy]

    zone_bottleneck = f.groupby("zone_id").agg(
        avg_time=("pick_time_seconds", "mean"), picks=("task_id", "count")
    ).reset_index().sort_values("avg_time", ascending=False) if not f.empty else f

    shift_bottleneck = f.groupby("shift").agg(
        avg_time=("pick_time_seconds", "mean"), picks=("task_id", "count")
    ).reset_index().sort_values("avg_time", ascending=False) if not f.empty else f

    recent = f.sort_values("task_id", ascending=False).head(25)

    return jsonify({
        "total_matching": len(f),
        "zone_bottleneck": zone_bottleneck.to_dict(orient="records") if not f.empty else [],
        "shift_bottleneck": shift_bottleneck.to_dict(orient="records") if not f.empty else [],
        "recent": recent.to_dict(orient="records"),
    })


@app.route("/api/browse/zones")
def api_browse_zones():
    conn = get_conn()
    zones = conn.read_df("SELECT * FROM Zone")
    racks = conn.read_df("SELECT * FROM Rack")
    conn.close()
    return jsonify({"zones": zones.to_dict(orient="records"), "racks": racks.to_dict(orient="records")})


@app.route("/api/browse/bins")
def api_browse_bins():
    conn = get_conn()
    bins_df = conn.read_df("SELECT * FROM Bin")
    conn.close()
    search = request.args.get("search", "")
    if search:
        bins_df = bins_df[bins_df["bin_id"].str.contains(search, case=False, na=False)]
    bins_df = bins_df.sort_values("distance_to_dispatch_m")
    return jsonify(bins_df.to_dict(orient="records"))


@app.route("/api/browse/skus")
def api_browse_skus():
    conn = get_conn()
    skus = conn.read_df("SELECT * FROM SKU")
    assign = conn.read_df("SELECT * FROM SKUBinAssignment")
    bins_df = conn.read_df("SELECT * FROM Bin")
    conn.close()

    if assign.empty:
        return jsonify([])

    latest = assign.sort_values("assigned_date").groupby("sku_id").last().reset_index()
    merged = latest.merge(skus[["sku_id", "product_name", "category"]], on="sku_id", how="left")
    merged = merged.merge(bins_df[["bin_id", "zone_id", "distance_to_dispatch_m"]], on="bin_id", how="left")
    return jsonify(merged.to_dict(orient="records"))


@app.route("/api/dropdowns")
def api_dropdowns():
    conn = get_conn()
    zones = conn.read_df("SELECT zone_id FROM Zone")
    racks = conn.read_df("SELECT rack_id FROM Rack")
    bins_df = conn.read_df("SELECT bin_id FROM Bin")
    skus = conn.read_df("SELECT sku_id FROM SKU")
    conn.close()
    return jsonify({
        "zones": zones["zone_id"].tolist(),
        "racks": racks["rack_id"].tolist(),
        "bins": bins_df["bin_id"].tolist(),
        "skus": skus["sku_id"].tolist(),
    })


# ---------------------------------------------------------------------------
# Write APIs (forms)
# ---------------------------------------------------------------------------
@app.route("/api/add_zone", methods=["POST"])
def add_zone():
    data = request.json
    conn = get_conn()
    try:
        conn.execute("INSERT INTO Zone (zone_id, zone_name, description) VALUES (?,?,?)",
                     (data["zone_id"], data["zone_name"], data.get("description", "")))
        conn.commit()
        return jsonify({"ok": True})
    except DBIntegrityError:
        return jsonify({"ok": False, "error": "That Zone ID already exists."}), 400
    finally:
        conn.close()


@app.route("/api/add_bin", methods=["POST"])
def add_bin():
    data = request.json
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO Bin (bin_id, rack_id, zone_id, bin_code, capacity, distance_to_dispatch_m) VALUES (?,?,?,?,?,?)",
            (data["bin_id"], data["rack_id"], data["zone_id"], data["bin_id"],
             int(data.get("capacity", 50)), float(data.get("distance", 20)))
        )
        conn.commit()
        return jsonify({"ok": True})
    except DBIntegrityError:
        return jsonify({"ok": False, "error": "That Bin ID already exists."}), 400
    finally:
        conn.close()


@app.route("/api/add_sku", methods=["POST"])
def add_sku():
    data = request.json
    conn = get_conn()
    try:
        conn.execute("INSERT INTO SKU (sku_id, product_name, category, unit_cost) VALUES (?,?,?,?)",
                     (data["sku_id"], data["product_name"], data.get("category", "Other"), float(data.get("unit_cost", 0))))
        conn.commit()
        return jsonify({"ok": True})
    except DBIntegrityError:
        return jsonify({"ok": False, "error": "That SKU ID already exists."}), 400
    finally:
        conn.close()


@app.route("/api/reassign_sku", methods=["POST"])
def reassign_sku():
    data = request.json
    conn = get_conn()
    conn.execute("INSERT INTO SKUBinAssignment (sku_id, bin_id, assigned_date) VALUES (?,?,?)",
                 (data["sku_id"], data["bin_id"], data.get("date", str(date.today()))))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/log_pick", methods=["POST"])
def log_pick():
    data = request.json
    conn = get_conn()
    conn.execute("""
        INSERT INTO PickTaskLog
        (sku_id, bin_id, zone_id, picker_id, pick_date, shift, strategy, travel_distance_m, pick_time_seconds, had_error)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        data["sku_id"], data["bin_id"], data["zone_id"], data.get("picker_id", "P1"),
        data.get("date", str(date.today())), data["shift"], data["strategy"],
        float(data.get("travel", 20)), float(data.get("time", 45)), int(data.get("had_error", False))
    ))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/delete_bin", methods=["POST"])
def delete_bin():
    data = request.json
    bin_id = data.get("bin_id")
    if not bin_id:
        return jsonify({"ok": False, "error": "Bin ID is required."}), 400
    conn = get_conn()
    try:
        # Clean up rows that reference this bin so the dashboard doesn't
        # break on dangling foreign keys, then remove the bin itself.
        conn.execute("DELETE FROM SKUBinAssignment WHERE bin_id = ?", (bin_id,))
        conn.execute("DELETE FROM PickTaskLog WHERE bin_id = ?", (bin_id,))
        conn.execute("DELETE FROM SlottingRecommendation WHERE current_bin_id = ? OR recommended_bin_id = ?", (bin_id, bin_id))
        conn.execute("DELETE FROM Bin WHERE bin_id = ?", (bin_id,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        conn.close()


@app.route("/api/delete_sku", methods=["POST"])
def delete_sku():
    data = request.json
    sku_id = data.get("sku_id")
    if not sku_id:
        return jsonify({"ok": False, "error": "SKU ID is required."}), 400
    conn = get_conn()
    try:
        conn.execute("DELETE FROM SKUBinAssignment WHERE sku_id = ?", (sku_id,))
        conn.execute("DELETE FROM PickTaskLog WHERE sku_id = ?", (sku_id,))
        conn.execute("DELETE FROM SlottingRecommendation WHERE sku_id = ?", (sku_id,))
        conn.execute("DELETE FROM SKU WHERE sku_id = ?", (sku_id,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        conn.close()


@app.route("/api/delete_zone", methods=["POST"])
def delete_zone():
    data = request.json
    zone_id = data.get("zone_id")
    if not zone_id:
        return jsonify({"ok": False, "error": "Zone ID is required."}), 400
    conn = get_conn()
    try:
        bins_df = conn.read_df("SELECT bin_id FROM Bin WHERE zone_id = ?", [zone_id])
        for b in bins_df["bin_id"].tolist():
            conn.execute("DELETE FROM SKUBinAssignment WHERE bin_id = ?", (b,))
            conn.execute("DELETE FROM PickTaskLog WHERE bin_id = ?", (b,))
            conn.execute("DELETE FROM SlottingRecommendation WHERE current_bin_id = ? OR recommended_bin_id = ?", (b, b))
        conn.execute("DELETE FROM PickTaskLog WHERE zone_id = ?", (zone_id,))
        conn.execute("DELETE FROM Bin WHERE zone_id = ?", (zone_id,))
        conn.execute("DELETE FROM Rack WHERE zone_id = ?", (zone_id,))
        conn.execute("DELETE FROM Zone WHERE zone_id = ?", (zone_id,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        conn.close()


@app.route("/api/delete_rack", methods=["POST"])
def delete_rack():
    data = request.json
    rack_id = data.get("rack_id")
    if not rack_id:
        return jsonify({"ok": False, "error": "Rack ID is required."}), 400
    conn = get_conn()
    try:
        bins_df = conn.read_df("SELECT bin_id FROM Bin WHERE rack_id = ?", [rack_id])
        for b in bins_df["bin_id"].tolist():
            conn.execute("DELETE FROM SKUBinAssignment WHERE bin_id = ?", (b,))
            conn.execute("DELETE FROM PickTaskLog WHERE bin_id = ?", (b,))
            conn.execute("DELETE FROM SlottingRecommendation WHERE current_bin_id = ? OR recommended_bin_id = ?", (b, b))
        conn.execute("DELETE FROM Bin WHERE rack_id = ?", (rack_id,))
        conn.execute("DELETE FROM Rack WHERE rack_id = ?", (rack_id,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Warehouse Map + Shortest Path
# ---------------------------------------------------------------------------
@app.route("/api/warehouse_map")
def api_warehouse_map():
    conn = get_conn()
    zones = conn.read_df("SELECT * FROM Zone")
    racks = conn.read_df("SELECT * FROM Rack")
    bins_df = conn.read_df("SELECT * FROM Bin")
    conn.close()
    return jsonify({
        "zones": zones.to_dict(orient="records"),
        "racks": racks.to_dict(orient="records"),
        "bins": bins_df.to_dict(orient="records"),
    })


def _rack_index(rack_id):
    """Pull the trailing rack number out of an id like 'Z1-R2' -> 2."""
    m = re.search(r"R(\d+)$", str(rack_id))
    return int(m.group(1)) if m else 0


@app.route("/api/shortest_path", methods=["POST"])
def api_shortest_path():
    """
    Estimates walking distance between two bins using a 'return-routing'
    model - a standard, simplified warehouse routing heuristic: a picker
    walks from their current bin back out to the main aisle before heading
    toward a different rack or zone, rather than cutting directly between
    shelves (which usually isn't physically possible in a real warehouse).

    - Same rack: direct distance between the two bins' positions.
    - Same zone, different rack: back out to the cross-aisle, over to the
      other rack, then in - approximated as their distance-to-dispatch gap
      plus a lateral cost per rack aisle crossed.
    - Different zones: back out to the main dispatch aisle and out again to
      the other zone - approximated as the sum of both bins' distance to
      dispatch.
    """
    data = request.json
    start_id = data.get("start_bin_id")
    end_id = data.get("end_bin_id")
    if not start_id or not end_id:
        return jsonify({"ok": False, "error": "Both a start and end bin are required."}), 400

    conn = get_conn()
    bins_df = conn.read_df("SELECT * FROM Bin")
    conn.close()

    start_rows = bins_df[bins_df.bin_id == start_id]
    end_rows = bins_df[bins_df.bin_id == end_id]
    if start_rows.empty or end_rows.empty:
        return jsonify({"ok": False, "error": "Could not find one of those bins."}), 400

    start = start_rows.iloc[0]
    end = end_rows.iloc[0]

    if start_id == end_id:
        return jsonify({
            "ok": True, "distance_m": 0.0,
            "route": "Same bin - no travel needed.", "path_type": "none"
        })

    RACK_LATERAL_GAP_M = 6.0  # approx. walking width between adjacent rack aisles

    if start["rack_id"] == end["rack_id"]:
        dist = abs(float(start["distance_to_dispatch_m"]) - float(end["distance_to_dispatch_m"]))
        path_type = "same_rack"
        route = f"Same rack ({start['rack_id']}) - walk directly between the two bins."
    elif start["zone_id"] == end["zone_id"]:
        rack_gap = abs(_rack_index(start["rack_id"]) - _rack_index(end["rack_id"]))
        lateral = rack_gap * RACK_LATERAL_GAP_M
        dist = abs(float(start["distance_to_dispatch_m"]) - float(end["distance_to_dispatch_m"])) + lateral
        path_type = "same_zone"
        route = f"Same zone ({start['zone_id']}), different racks - via the zone's cross-aisle."
    else:
        dist = float(start["distance_to_dispatch_m"]) + float(end["distance_to_dispatch_m"])
        path_type = "cross_zone"
        route = f"Different zones ({start['zone_id']} \u2192 {end['zone_id']}) - return-routing via the main dispatch aisle."

    return jsonify({
        "ok": True,
        "distance_m": round(float(dist), 1),
        "route": route,
        "path_type": path_type,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
