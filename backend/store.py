"""SQLite persistence, imports, saved analyses, aggregate analysis pipeline."""
import os, io, json, sqlite3, hashlib
from datetime import datetime
import numpy as np, pandas as pd
from fastapi import HTTPException
from backend import engine as E

DB = os.getenv("DB_PATH", "stockwise.db")
def con(): return sqlite3.connect(DB)
def now(): return datetime.now().isoformat(timespec="seconds")
def js(o): return json.dumps(o, default=lambda v: v.item() if hasattr(v, "item") else str(v))
def rec(df): return json.loads(df.to_json(orient="records"))
def init():
    with con() as c:
        c.execute("create table if not exists analyses(id integer primary key autoincrement, created text, horizon int, budget real, config text, result text)")
        c.execute("create table if not exists imports(id integer primary key autoincrement, created text, filename text, kind text, sha256 text, mode text, rows_imported int, rows_rejected int, rows_duplicate int, status text, summary text)")
init()
def load():
    with con() as c:
        try: return pd.read_sql("select * from products", c), pd.read_sql("select * from sales", c)
        except Exception: return None, None
def log_import(filename, kind, sha, mode, n, rej, dup):
    with con() as c: c.execute("insert into imports(created,filename,kind,sha256,mode,rows_imported,rows_rejected,rows_duplicate,status,summary) values(?,?,?,?,?,?,?,?,?,?)",
        (now(), filename, kind, sha, mode, n, rej, dup, "ok", f"{n} imported, {rej} rejected, {dup} duplicates skipped"))
def reset_demo():
    inv, sales = E.demo_data()
    with con() as c:
        inv.to_sql("products", c, if_exists="replace", index=False); sales.to_sql("sales", c, if_exists="replace", index=False)
    with con() as c: c.execute("delete from imports")
    log_import("demo-data", "demo", None, "replace", len(sales), 0, 0)
    return len(inv), len(sales)
def ensure():
    inv, sales = load()
    if inv is None or sales is None or inv.empty: reset_demo(); inv, sales = load()
    return inv, sales
def upsert(df, replace=False):
    ex, _ = load()
    if ex is not None and not replace: df = pd.concat([ex[~ex.product_id.isin(df.product_id)], df])
    with con() as c: df.to_sql("products", c, if_exists="replace", index=False)

def import_csv(raw, filename, kind, mode):
    if kind not in ("sales", "inventory") or mode not in ("append", "replace"): raise HTTPException(400, "kind must be sales|inventory and mode append|replace")
    if len(raw) > 5_000_000: raise HTTPException(413, "File larger than 5 MB")
    sha = hashlib.sha256(raw).hexdigest()
    with con() as c:
        if c.execute("select 1 from imports where sha256=? and kind=? and status='ok'", (sha, kind)).fetchone():
            raise HTTPException(409, "This exact file was already imported (see import history).")
    try: df = pd.read_csv(io.BytesIO(raw))
    except Exception: raise HTTPException(400, "Could not parse the file as CSV")
    df.columns = [str(x).strip().lower() for x in df.columns]; rej = dup = 0
    if kind == "sales":
        miss = {"date", "product_id", "quantity"} - set(df.columns)
        if miss: raise HTTPException(422, f"Missing columns: {sorted(miss)}")
        df["date"] = pd.to_datetime(df["date"], errors="coerce"); df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
        ok = df.date.notna() & df.quantity.notna() & (df.quantity >= 0); rej = int((~ok).sum()); df = df[ok]
        inv, sales = ensure(); k = df.product_id.isin(inv.product_id); rej += int((~k).sum()); df = df[k]
        n0 = len(df); df = df.drop_duplicates(["date", "product_id"]); dup += n0 - len(df)
        df = df.assign(date=df.date.dt.strftime("%Y-%m-%d"))[["date", "product_id", "quantity"]]
        if mode == "append":
            key = set(zip(sales.date, sales.product_id)); m = [(a, b) in key for a, b in zip(df.date, df.product_id)]
            dup += sum(m); df = df[[not v for v in m]]
        if df.empty: raise HTTPException(422, "No valid new rows after validation")
        with con() as c: df.to_sql("sales", c, if_exists="append" if mode == "append" else "replace", index=False)
    else:
        miss = {"product_id", "name", "unit_cost", "stock"} - set(df.columns)
        if miss: raise HTTPException(422, f"Missing columns: {sorted(miss)}")
        for col, dv in dict(category="General", price=np.nan, min_stock=0, incoming=0, lead_days=np.nan).items():
            if col not in df.columns: df[col] = dv
        for col in ["unit_cost", "price", "stock", "min_stock", "incoming", "lead_days"]: df[col] = pd.to_numeric(df[col], errors="coerce")
        ok = df.product_id.notna() & df.name.notna() & (df.unit_cost >= 0) & (df.stock >= 0); rej = int((~ok).sum()); df = df[ok]
        n0 = len(df); df = df.drop_duplicates("product_id"); dup = n0 - len(df)
        df[["min_stock", "incoming"]] = df[["min_stock", "incoming"]].fillna(0)
        if df.empty: raise HTTPException(422, "No valid rows after validation")
        upsert(df[E.COLS], replace=(mode == "replace"))
    log_import(filename, kind, sha, mode, len(df), rej, dup)
    return dict(imported_rows=len(df), rejected_invalid=rej, duplicates_skipped=dup, mode=mode, kind=kind)

def analyse(horizon=7, budget=5000, constraints=None, cover=7, safety=2, save=False):
    inv, sales = ensure(); fc = E.forecast(sales, horizon); recs = E.restock(inv, fc, cover, safety)
    rev = sales.merge(inv[["product_id", "price"]], on="product_id")
    out = dict(horizon=horizon, forecast=fc, anomalies=E.anomalies(sales), recommendations=recs, budget=E.budget_plan(recs, budget, constraints),
        summary=dict(units_sold=int(sales.quantity.sum()), products=len(inv), revenue=round(float((rev.quantity * rev.price).sum()), 2),
            critical=sum(r["priority"] == "Critical" for r in recs), high=sum(r["priority"] == "High" for r in recs),
            low_stock=sum(r["stock"] <= m for r, m in zip(recs, inv.min_stock))))
    if save:
        with con() as c:
            cur = c.execute("insert into analyses(created,horizon,budget,config,result) values(?,?,?,?,?)", (now(), horizon, budget, js(dict(cover=cover, safety=safety, constraints=constraints)), js(out)))
        out["analysis_id"] = cur.lastrowid
    return json.loads(js(out))
def get_analysis(i):
    with con() as c: r = c.execute("select id,created,result from analyses where id=?", (i,)).fetchone()
    if not r: raise HTTPException(404, "Analysis not found")
    return dict(json.loads(r[2]), analysis_id=r[0], created=r[1])
def list_analyses():
    with con() as c: return [dict(id=i, created=t, horizon=h, budget=b) for i, t, h, b in c.execute("select id,created,horizon,budget from analyses order by id desc limit 50")]
def list_imports():
    with con() as c: return rec(pd.read_sql("select id,created,filename,kind,mode,rows_imported,rows_rejected,rows_duplicate,status,summary from imports order by id desc limit 50", c))

def sales_summary():
    inv, sales = ensure(); d = sales.copy(); d["date"] = pd.to_datetime(d["date"]); d = d.merge(inv[["product_id", "name", "price"]], on="product_id")
    d["rev"] = d.quantity * d.price.fillna(0)
    daily = d.groupby("date").agg(units=("quantity", "sum"), revenue=("rev", "sum")).reset_index(); daily["date"] = daily.date.dt.strftime("%Y-%m-%d")
    wk = d.groupby(pd.Grouper(key="date", freq="W")).agg(units=("quantity", "sum"), revenue=("rev", "sum")).reset_index(); wk["week"] = wk.date.dt.strftime("%Y-%m-%d")
    by = d.groupby(["product_id", "name"]).agg(units=("quantity", "sum"), revenue=("rev", "sum")).reset_index().sort_values("units", ascending=False)
    end = d.date.max(); cur = d[d.date > end - pd.Timedelta(days=28)]; prev = d[(d.date <= end - pd.Timedelta(days=28)) & (d.date > end - pd.Timedelta(days=56))]
    days = (d.date.max() - d.date.min()).days + 1
    return dict(daily=rec(daily.tail(90)), weekly=rec(wk[["week", "units", "revenue"]]), top=rec(by.head(8)),
        slow=rec(by.tail(8).iloc[::-1]) if days >= 28 else [], slow_note=None if days >= 28 else "Fewer than 28 days of history: slow-mover ranking suppressed.",
        compare=dict(current_units=int(cur.quantity.sum()), previous_units=int(prev.quantity.sum()), current_revenue=float(cur.rev.sum()), previous_revenue=float(prev.rev.sum())))
