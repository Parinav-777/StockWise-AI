"""Deterministic calculations: demo data, forecasting, anomalies, restocking, budget."""
import math, numpy as np, pandas as pd

PRODUCTS = [  # id,name,category,cost,price,stock,min,incoming,lead,base_rate
 ("P01","Parle-G Biscuits","Biscuits",8,10,60,40,0,3,22),("P02","Good Day Biscuits","Biscuits",18,22,50,30,0,3,10),
 ("P03","Lays Chips","Chips",16,20,35,25,0,4,12),("P04","Kurkure","Chips",16,20,70,25,0,4,8),
 ("P05","Lux Soap","Soap",28,35,40,20,0,5,6),("P06","Dettol Soap","Soap",34,42,25,15,0,5,4),
 ("P07","Basmati Rice 5kg","Rice",420,480,12,6,0,6,2.5),("P08","Sona Masoori Rice 10kg","Rice",610,690,4,4,10,6,1.2),
 ("P09","Sunflower Oil 1L","Cooking oil",140,155,18,12,0,4,5),("P10","Groundnut Oil 1L","Cooking oil",190,210,30,10,0,4,1.5),
 ("P11","Milk 500ml","Milk",24,27,45,40,0,1,45),("P12","Curd 400g","Milk",30,35,16,15,0,1,12),
 ("P13","Namkeen Mixture","Snacks",45,55,26,12,0,3,5),("P14","Instant Noodles","Snacks",11,14,90,50,0,3,18),
 ("P15","Notebook A4","Stationery",30,40,22,15,0,7,2.0),("P16","Ball Pen Pack","Stationery",40,55,60,10,0,7,0.4)]
COLS = ["product_id","name","category","unit_cost","price","stock","min_stock","incoming","lead_days"]

def demo_data(days=120, end="2026-10-15"):
    rng = np.random.RandomState(42)
    dates = pd.date_range(end=end, periods=days)
    rows = []
    for p in PRODUCTS:
        for i, d in enumerate(dates):
            lam = p[9] * (1.3 if d.dayofweek >= 5 else 1.0)
            if p[0] == "P14": lam *= 1 + i / days          # rising demand
            if p[0] == "P12": lam *= 1.6 - i / days        # declining demand
            q = int(rng.poisson(lam))
            if p[0] == "P03" and i == days - 10: q = 70     # INSERTED ANOMALY: spike
            if q: rows.append((d.strftime("%Y-%m-%d"), p[0], q))
    return pd.DataFrame([p[:9] for p in PRODUCTS], columns=COLS), pd.DataFrame(rows, columns=["date","product_id","quantity"])

def daily_matrix(sales):
    s = sales.copy(); s["date"] = pd.to_datetime(s["date"])
    p = s.pivot_table(index="date", columns="product_id", values="quantity", aggfunc="sum").fillna(0)
    return p.reindex(pd.date_range(p.index.min(), p.index.max()), fill_value=0)

def baseline(y, h): return np.full(h, y[-14:].mean())

def seasonal_ses(y, h, alpha=0.3):
    """Weekday-seasonal factors x simple exponential smoothing of deseasonalised series."""
    n = len(y); w = y[-56:]; dow = np.arange(n - len(w), n) % 7
    m = w.mean()
    if m == 0: return np.zeros(h)
    f = np.array([w[dow == d].mean() / m if (dow == d).any() else 1.0 for d in range(7)])
    f = np.maximum(f, 0.2); des = y / f[np.arange(n) % 7]; lvl = des[0]
    for v in des[1:]: lvl = alpha * v + (1 - alpha) * lvl
    return np.maximum(0, lvl * f[np.arange(n, n + h) % 7])

def forecast(sales, horizon=7, min_history=28):
    out = []
    for pid, s in daily_matrix(sales).items():
        y = s.values.astype(float)
        if len(y) < min_history:
            out.append(dict(product_id=pid, reliable=False, note="Insufficient history", daily=0.0, total=0.0)); continue
        tr, te = y[:-7], y[-7:]  # chronological split: test = last 7 days, never used for training
        mae_b = float(np.abs(baseline(tr, 7) - te).mean()); mae_m = float(np.abs(seasonal_ses(tr, 7) - te).mean())
        use_model = mae_m <= mae_b
        f = seasonal_ses(y, horizon) if use_model else baseline(y, horizon)
        prev, rec = y[-28:-14].mean(), y[-14:].mean()
        trend = "stable" if prev == 0 and rec == 0 else ("increasing" if rec > prev * 1.15 else "decreasing" if rec < prev * 0.85 else "stable")
        out.append(dict(product_id=pid, reliable=True, method="seasonal_ses" if use_model else "baseline_14d_mean",
            mae_baseline=round(mae_b, 2), mae_model=round(mae_m, 2), daily=float(f.mean()), total=float(f.sum()),
            forecast=[round(float(v), 2) for v in f], trend=trend, intermittent=bool((y[-28:] == 0).mean() > 0.5),
            note="Backtest on last 7 days; synthetic data, not real-world accuracy",
            history=[round(float(v),1) for v in y[-60:]], last_date=str(s.index[-1].date()),
            backtest=dict(actual=[float(v) for v in te], model=[round(float(v),2) for v in seasonal_ses(tr,7)], baseline=[round(float(v),2) for v in baseline(tr,7)])))
    return out

def anomalies(sales, z_thresh=3.5):
    res = []
    for pid, s in daily_matrix(sales).items():
        y = s.values.astype(float)
        if len(y) < 28 or (y > 0).sum() < 10: continue
        med = np.median(y); mad = max(np.median(np.abs(y - med)), 1.0)
        z = 0.6745 * (y - med) / mad
        for i in np.where(np.abs(z) > z_thresh)[0]:
            sev = "High" if abs(z[i]) > 2 * z_thresh else "Medium"
            res.append(dict(product_id=pid, date=str(s.index[i].date()), observed=float(y[i]), expected=float(med),
                score=round(float(z[i]), 2), severity=sev,
                reason=f"Robust z-score {z[i]:.1f} vs median {med:.0f} (threshold {z_thresh})",
                action="Check recent transactions and stock; may be a bulk order or entry error." if z[i] > 0 else "Check for stockout or missed entries that day."))
    return sorted(res, key=lambda r: -abs(r["score"]))

def restock(inv, fc, cover_days=7, safety_days=2):
    fmap = {f["product_id"]: f for f in fc}; rows = []
    for r in inv.to_dict("records"):
        f = fmap.get(r["product_id"], {}); d = f.get("daily", 0.0)
        lead = r["lead_days"] if pd.notna(r["lead_days"]) else 3
        target = d * (lead + cover_days + safety_days)
        order = int(math.ceil(max(0.0, target - r["stock"] - r["incoming"])))
        dos = r["stock"] / d if d > 0 else None
        if order == 0: pr = "No action"
        elif dos is not None and dos < lead: pr = "Critical"
        elif dos is not None and dos < lead + 3: pr = "High"
        elif dos is not None and dos < lead + cover_days: pr = "Medium"
        else: pr = "Low"
        rows.append(dict(product_id=r["product_id"], name=r["name"], category=r["category"], stock=r["stock"], incoming=r["incoming"],
            daily_demand=round(d, 2), days_of_supply=None if dos is None else round(dos, 1), reliable=f.get("reliable", False),
            trend=f.get("trend"), target_stock=round(target, 1), order_qty=order, unit_cost=r["unit_cost"],
            cost=round(order * r["unit_cost"], 2), priority=pr,
            reason=f"Target = {d:.1f}/day x ({lead}+{cover_days}+{safety_days}) days = {target:.0f}; stock {r['stock']}+incoming {r['incoming']}."))
    return rows

PW = {"Critical": 8, "High": 4, "Medium": 2, "Low": 1}
OBJ = "Maximise priority-weighted share of each product's need that is funded (= minimise weighted unmet need), subject to total cost <= budget, per-product min/max quantities, integer units."

def _greedy(val, cost, lb, ub, budget):
    x = lb.astype(int).copy(); rem = budget - float((x * cost).sum())
    for i in np.argsort(-val / cost):
        q = max(0, min(int(ub[i] - x[i]), int(rem // cost[i]))); x[i] += q; rem -= q * cost[i]
    return x

def _solve(val, cost, lb, ub, budget):
    """Exact integer program (scipy MILP / HiGHS); greedy fallback if scipy is missing or the result violates the budget."""
    try:
        from scipy.optimize import milp, LinearConstraint, Bounds
        r = milp(-val, constraints=LinearConstraint(cost[None, :], -np.inf, budget), integrality=np.ones(len(val)), bounds=Bounds(lb, ub))
        if r.success:
            x = np.round(r.x).astype(int)
            if float((x * cost).sum()) <= budget + 1e-6: return x, "milp"
    except Exception: pass
    return _greedy(val, cost, lb, ub, budget), "greedy"

def budget_plan(recs, budget, cons=None, sens=True):
    cons = cons or {}; items = [r for r in recs if r["order_qty"] > 0]; warn = []
    base = dict(budget=budget, objective=OBJ)
    if not items:
        return dict(base, full_cost=0.0, spent=0.0, remaining=round(budget, 2), fits_fully=True, method="none", weighted_coverage=1.0, items=[], tradeoffs=[], warnings=[], sensitivity=[])
    g = lambda r, k, d: cons.get(r["product_id"], {}).get(k, d)
    need = np.array([r["order_qty"] for r in items]); ub = np.array([min(int(need[i]), int(g(r, "max", need[i]))) for i, r in enumerate(items)])
    lb = np.array([min(int(g(r, "min", 0)), int(ub[i])) for i, r in enumerate(items)])
    cost = np.array([max(float(r["unit_cost"]), 0.01) for r in items]); w = np.array([float(g(r, "weight", PW[r["priority"]])) for r in items])
    val = w / need
    if (lb * cost).sum() > budget: warn.append("Minimum quantities exceed the budget, so they were ignored."); lb = np.zeros_like(lb)
    x, method = _solve(val, cost, lb, ub, budget)
    cov = lambda xx: round(float((w * xx / need).sum() / w.sum()), 3)
    plan = [dict(product_id=r["product_id"], name=r["name"], priority=r["priority"], needed=int(need[i]), buy=int(x[i]), unmet=int(need[i] - x[i]),
                 unit_cost=float(cost[i]), cost=round(float(x[i] * cost[i]), 2), weight=float(w[i])) for i, r in enumerate(items)]
    spent = round(sum(p["cost"] for p in plan), 2)
    trade = [f"{p['name']} ({p['priority']}): {p['unmet']} of {p['needed']} units not funded; about \u20b9{p['unmet']*p['unit_cost']:.0f} more would cover it." for p in plan if p["unmet"] > 0]
    sen = []
    if sens:
        for b in sorted({round(budget * m) for m in (0.25, 0.5, 1, 1.5, 2)} | {round(sum(r["cost"] for r in recs))}):
            xs, _ = _solve(val, cost, np.zeros_like(lb), ub, b); sen.append(dict(budget=b, spent=round(float((xs * cost).sum()), 2), coverage=cov(xs)))
    return dict(base, full_cost=round(sum(r["cost"] for r in recs), 2), spent=spent, remaining=round(budget - spent, 2),
                fits_fully=all(p["unmet"] == 0 for p in plan), method=method, weighted_coverage=cov(x), items=plan, tradeoffs=trade, warnings=warn, sensitivity=sen)
