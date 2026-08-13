"""
WarehouseFlow - Flask Web App (no Streamlit)
==============================================
Run locally:    python app.py
Run on Render:  gunicorn app:app
"""
import os
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


@app.route("/api/delete_zone", methods=["POST"])
def delete_zone():
    data = request.json
    zone_id = data.get("zone_id")
    if not zone_id:
        return jsonify({"ok": False, "error": "Zone ID is required."}), 400
    conn = get_conn()
    try:
        # Block deleting a zone that still has bins in it, same guard style as delete_bin
        bins_df = conn.read_df("SELECT * FROM Bin")
        if not bins_df.empty and (bins_df["zone_id"] == zone_id).any():
            return jsonify({"ok": False, "error": "Cannot delete a zone that still has bins. Delete its bins first."}), 400
        conn.execute("DELETE FROM Zone WHERE zone_id = ?", (zone_id,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        conn.close()


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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
