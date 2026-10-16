import os, re, json, logging, urllib.request
import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Request
from fastapi.responses import Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from backend import engine as E, store as S

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
log = logging.getLogger("stockwise"); app = FastAPI(title="StockWise AI")

@app.exception_handler(Exception)
async def crash(request: Request, exc: Exception):
    log.exception("Unhandled error"); return JSONResponse({"detail": "Unexpected server error. Your saved data was not changed."}, status_code=500)

Cons = dict[str, dict[str, float]]
class AnalysisReq(BaseModel):
    horizon: int = Field(7, ge=1, le=30); budget: float = Field(5000, ge=0); cover_days: int = Field(7, ge=1, le=60); safety_days: int = Field(2, ge=0, le=30)
class ForecastReq(BaseModel):
    horizon: int = Field(7, ge=1, le=30)
class AnomalyReq(BaseModel):
    z_threshold: float = Field(3.5, ge=1.5, le=10)
class RestockReq(BaseModel):
    horizon: int = Field(7, ge=1, le=30); cover_days: int = Field(7, ge=1, le=60); safety_days: int = Field(2, ge=0, le=30)
class BudgetReq(BaseModel):
    budget: float = Field(..., ge=0); analysis_id: int | None = None; constraints: Cons = {}
class ReportReq(BaseModel):
    analysis_id: int | None = None; budget: float = Field(5000, ge=0)
class Ask(BaseModel):
    question: str = Field(..., min_length=2, max_length=500); budget: float = Field(5000, ge=0)
class ProductNew(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=20); name: str = Field(..., min_length=1); category: str = "General"
    unit_cost: float = Field(..., ge=0); price: float | None = Field(None, ge=0); stock: int = Field(0, ge=0); min_stock: int = Field(0, ge=0)
    incoming: int = Field(0, ge=0); lead_days: int | None = Field(None, ge=0)
class ProductUpdate(BaseModel):
    name: str | None = None; category: str | None = None; price: float | None = Field(None, ge=0)
    stock: int | None = Field(None, ge=0); min_stock: int | None = Field(None, ge=0); incoming: int | None = Field(None, ge=0)
    unit_cost: float | None = Field(None, ge=0); lead_days: int | None = Field(None, ge=0)

@app.get("/api/v1/health")
def health(): return {"status": "ok"}
@app.get("/api/v1/ai/status")
def ai_status():
    try: urllib.request.urlopen(OLLAMA_URL.rsplit("/api", 1)[0], timeout=2); ok = True
    except Exception: ok = False
    return {"model": MODEL, "mode": "local-ollama", "available": ok, "help": None if ok else "Install Ollama, run `ollama pull " + MODEL + "`. Analysis works without it."}
@app.get("/api/v1/demo-data")
def demo_get():
    inv, sales = S.ensure(); return {"products": len(inv), "sales_rows": len(sales)}
@app.post("/api/v1/demo-data/reset")
def demo_reset():
    p, s = S.reset_demo(); return {"products": p, "sales_rows": s}
@app.get("/api/v1/data/templates")
def templates(): return {"sales": "/api/v1/data/templates/sales.csv", "inventory": "/api/v1/data/templates/inventory.csv"}
@app.get("/api/v1/data/templates/{name}.csv")
def template_file(name: str):
    if name == "sales": body = "date,product_id,quantity\n2026-10-01,P01,20\n"
    elif name == "inventory": body = ",".join(E.COLS) + "\nP99,Sample Item,General,10,12,50,10,0,3\n"
    else: raise HTTPException(404, "Unknown template")
    return Response(body, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={name}_template.csv"})
@app.post("/api/v1/data/upload")
async def upload(file: UploadFile = File(...), kind: str = Query("sales"), mode: str = Query("append")):
    if not (file.filename or "").lower().endswith(".csv"): raise HTTPException(400, "Only .csv files are supported")
    return S.import_csv(await file.read(), file.filename, kind, mode)
@app.get("/api/v1/data/imports")
def imports(): return S.list_imports()
@app.get("/api/v1/products")
def products(): return S.rec(S.ensure()[0])
@app.post("/api/v1/products", status_code=201)
def create_product(p: ProductNew):
    inv, _ = S.ensure()
    if p.product_id in set(inv.product_id): raise HTTPException(409, "Product ID already exists")
    S.upsert(pd.DataFrame([p.model_dump()])[E.COLS]); return {"created": p.product_id}
@app.put("/api/v1/products/{pid}")
def update_product(pid: str, u: ProductUpdate):
    S.ensure(); f = {k: v for k, v in u.model_dump().items() if v is not None}
    if not f: raise HTTPException(400, "No fields to update")
    with S.con() as c: cur = c.execute(f"update products set {', '.join(k + '=?' for k in f)} where product_id=?", [*f.values(), pid])
    if cur.rowcount == 0: raise HTTPException(404, "Unknown product")
    return {"updated": pid}
@app.get("/api/v1/sales/summary")
def sales_summary(): return S.sales_summary()
@app.post("/api/v1/analysis")
def analysis(r: AnalysisReq): return S.analyse(r.horizon, r.budget, None, r.cover_days, r.safety_days, save=True)
@app.get("/api/v1/analysis/{aid}")
def analysis_get(aid: int): return S.get_analysis(aid)
@app.get("/api/v1/analyses")
def analyses(): return S.list_analyses()
@app.post("/api/v1/forecast")
def forecast(r: ForecastReq):
    inv, sales = S.ensure(); nm = dict(zip(inv.product_id, inv.name)); fc = E.forecast(sales, r.horizon)
    for f in fc: f["name"] = nm.get(f["product_id"], f["product_id"])
    warn = [f"{f['name']}: insufficient history, no forecast" for f in fc if not f["reliable"]]
    return S.json.loads(S.js(dict(horizon=r.horizon, forecasts=fc, warnings=warn)))
@app.post("/api/v1/anomalies/detect")
def anomalies(r: AnomalyReq):
    inv, sales = S.ensure(); nm = dict(zip(inv.product_id, inv.name)); a = E.anomalies(sales, r.z_threshold)
    for x in a: x["name"] = nm.get(x["product_id"], x["product_id"])
    return {"z_threshold": r.z_threshold, "count": len(a), "anomalies": a}
@app.post("/api/v1/recommendations/restock")
def restock(r: RestockReq):
    inv, sales = S.ensure(); return {"recommendations": S.json.loads(S.js(E.restock(inv, E.forecast(sales, r.horizon), r.cover_days, r.safety_days)))}
@app.post("/api/v1/optimization/budget")
def opt(r: BudgetReq):
    recs = S.get_analysis(r.analysis_id)["recommendations"] if r.analysis_id else S.analyse(7, r.budget)["recommendations"]
    return E.budget_plan(recs, r.budget, r.constraints)
@app.post("/api/v1/reports/export")
def export(r: ReportReq):
    a = S.get_analysis(r.analysis_id) if r.analysis_id else S.analyse(7, r.budget)
    fc = {f["product_id"]: f for f in a["forecast"]}; an = {}
    for x in a["anomalies"]: an[x["product_id"]] = an.get(x["product_id"], 0) + 1
    bp = {i["product_id"]: i for i in a["budget"]["items"]}
    df = pd.DataFrame(a["recommendations"]); df["forecast_total"] = df.product_id.map(lambda p: round(fc[p]["total"], 1))
    df["trend"] = df.product_id.map(lambda p: fc[p].get("trend")); df["anomaly_count"] = df.product_id.map(lambda p: an.get(p, 0))
    df["budget_buy_qty"] = df.product_id.map(lambda p: bp.get(p, {}).get("buy", 0)); df["budget_unmet_qty"] = df.product_id.map(lambda p: bp.get(p, {}).get("unmet", 0))
    return Response(df.to_csv(index=False), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=stockwise_report.csv"})

def llm(prompt):
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(OLLAMA_URL, body, {"Content-Type": "application/json"})
    for _ in range(2):  # limited retry
        try:
            t = json.loads(urllib.request.urlopen(req, timeout=30).read()).get("response", "").strip()
            if t: return t
        except Exception: pass
    return None

@app.post("/api/v1/ai/insights")
def insights(a: Ask):
    q = a.question.lower(); m = re.search(r"[₹$]?\s?(\d[\d,]{2,})", a.question)
    budget = float(m.group(1).replace(",", "")) if m else a.budget
    d = S.analyse(7, budget); recs = d["recommendations"]; tool = "restock"
    if "budget" in q or m or "afford" in q:
        tool = "budget"; b = d["budget"]
        facts = f"Budget {budget:.0f}: spend {b['spent']}, remaining {b['remaining']}, full plan costs {b['full_cost']}. Buy: " + "; ".join(f"{i['name']} x{i['buy']} ({i['priority']}, unmet {i['unmet']})" for i in b["items"] if i["buy"] or i["unmet"])
    elif "unusual" in q or "anomal" in q:
        tool = "anomalies"; facts = "Flagged: " + ("; ".join(f"{x['product_id']} {x['date']} observed {x['observed']} vs expected {x['expected']} ({x['severity']})" for x in d["anomalies"][:5]) or "none")
    elif "declin" in q or "increas" in q or "trend" in q:
        tool = "trends"; facts = "Trends: " + "; ".join(f"{r['name']}: {r['trend']}" for r in recs if r["trend"] in ("increasing", "decreasing"))
    elif "run out" in q or "stock" in q or "soon" in q:
        tool = "stockout"; facts = "Low cover: " + "; ".join(f"{r['name']} {r['days_of_supply']} days" for r in sorted(recs, key=lambda r: r["days_of_supply"] if r["days_of_supply"] is not None else 1e9)[:5])
    elif "sell" in q or "next week" in q or "demand" in q:
        tool = "forecast"; nm = {r["product_id"]: r["name"] for r in recs}
        facts = "Top 7-day forecasts: " + "; ".join(f"{nm[f['product_id']]} {f['total']:.0f} units" for f in sorted(d["forecast"], key=lambda f: -f["total"])[:5])
    else:
        facts = "Restock first: " + ("; ".join(f"{r['name']} order {r['order_qty']} ({r['priority']}, cost {r['cost']})" for r in recs if r["priority"] in ("Critical", "High")) or "No urgent items")
    text = llm(f"You are an inventory assistant. Answer simply using ONLY these computed facts; do not invent numbers.\nFacts: {facts}\nQuestion: {a.question}")
    return {"tool_used": tool, "facts": facts, "answer": text or facts, "llm_used": text is not None,
            "note": None if text else "Language model unavailable; showing computed facts only."}


DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(DIST): app.mount("/", StaticFiles(directory=DIST, html=True), name="ui")
else:
    @app.get("/")
    def index(): return {"message": "API running. Start the UI: cd frontend && npm install && npm run dev (or npm run build to serve it here)."}
