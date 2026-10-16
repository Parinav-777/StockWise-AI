import os; os.environ["DB_PATH"] = "test.db"
import numpy as np
from fastapi.testclient import TestClient
from backend import engine as E
from backend.main import app
inv, sales = E.demo_data(); c = TestClient(app)

def test_forecast_horizon_nonneg():
    for f in E.forecast(sales, 7):
        assert len(f["forecast"]) == 7 and min(f["forecast"]) >= 0
def test_insufficient_history():
    assert not E.forecast(sales[sales.date > "2026-10-10"], 7)[0]["reliable"]
def test_zero_demand():
    assert (E.seasonal_ses(np.zeros(60), 7) == 0).all()
def test_anomaly_found_not_everything():
    a = E.anomalies(sales); assert any(x["product_id"] == "P03" and x["observed"] == 70 for x in a); assert len(a) < 60
def test_restock_formula_and_budget():
    recs = E.restock(inv, E.forecast(sales, 7)); assert all(r["order_qty"] >= 0 for r in recs)
    for b in (0, 500, 5000, 1e6):
        p = E.budget_plan(recs, b); assert p["spent"] <= b and p["remaining"] >= 0
def test_api_flow():
    assert c.get("/api/v1/health").json()["status"] == "ok"
    assert c.post("/api/v1/demo-data/reset").status_code == 200
    a = c.post("/api/v1/analysis", json={"horizon": 7, "budget": 3000}).json(); assert a["budget"]["spent"] <= 3000
    assert c.post("/api/v1/analysis", json={"horizon": 7, "budget": -1}).status_code == 422
    r = c.post("/api/v1/ai/insights", json={"question": "What can I buy with 2000?"}).json(); assert r["tool_used"] == "budget" and r["answer"]
    assert c.post("/api/v1/reports/export", json={}).text.startswith("product_id")
    assert c.post("/api/v1/data/upload", files={"file": ("x.csv", b"a,b\n1,2")}).status_code == 422
    assert c.put("/api/v1/products/P01", json={"stock": 99}).status_code == 200

def test_new_routes_and_history():
    c.post("/api/v1/demo-data/reset")
    f = c.post("/api/v1/forecast", json={"horizon": 30}).json(); assert len(f["forecasts"][0]["forecast"]) == 30
    an = c.post("/api/v1/anomalies/detect", json={"z_threshold": 3.5}).json(); assert an["count"] >= 1 and "name" in an["anomalies"][0]
    assert c.post("/api/v1/recommendations/restock", json={}).json()["recommendations"]
    a = c.post("/api/v1/analysis", json={"budget": 1500}).json(); aid = a["analysis_id"]
    assert c.get(f"/api/v1/analysis/{aid}").json()["budget"]["budget"] == 1500 and any(x["id"] == aid for x in c.get("/api/v1/analyses").json())
    assert c.get("/api/v1/analysis/99999").status_code == 404
    o = c.post("/api/v1/optimization/budget", json={"budget": 800, "analysis_id": aid, "constraints": {"P07": {"max": 1}}}).json()
    assert o["spent"] <= 800 and all(i["buy"] <= 1 for i in o["items"] if i["product_id"] == "P07")
def test_upload_dedupe_and_history():
    c.post("/api/v1/demo-data/reset")
    f = {"file": ("s.csv", b"date,product_id,quantity\n2026-11-01,P01,5\n2026-11-01,P01,5\n2026-10-15,P01,3\n2026-11-02,P01,-2\n")}
    r = c.post("/api/v1/data/upload?kind=sales&mode=append", files=f).json(); assert r["imported_rows"] == 1 and r["duplicates_skipped"] == 2 and r["rejected_invalid"] == 1
    assert c.post("/api/v1/data/upload?kind=sales&mode=append", files={"file": ("s.csv", f["file"][1])}).status_code == 409
    assert c.get("/api/v1/data/imports").json()[0]["rows_imported"] == 1
    assert c.post("/api/v1/products", json={"product_id": "Z1", "name": "Zed", "unit_cost": 5}).status_code == 201
def test_milp_not_worse_than_greedy_and_respects_budget():
    recs = E.restock(inv, E.forecast(sales, 7)); items = [r for r in recs if r["order_qty"] > 0]
    need = np.array([r["order_qty"] for r in items]); cost = np.array([r["unit_cost"] for r in items]); val = np.array([E.PW[r["priority"]] for r in items]) / need
    for b in (300, 1000, 4000):
        x, m = E._solve(val, cost, np.zeros(len(need), int), need, b); g = E._greedy(val, cost, np.zeros(len(need), int), need, b)
        assert (x * cost).sum() <= b and (val * x).sum() >= (val * g).sum() - 1e-6
