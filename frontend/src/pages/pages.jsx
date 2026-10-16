import React, { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid, ResponsiveContainer, BarChart, Bar, ComposedChart, Area, AreaChart } from 'recharts'
import { get, post, put, upload, save } from '../api/client.js'
import { Card, Stat, Loading, ErrorBox, Badge, Btn, Table, useLoad } from '../components/ui.jsx'
const inr = n => '₹' + Number(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })
const addDays = (s, n) => { const d = new Date(s + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10) }
const Chart = ({ children, h = 280 }) => <div style={{ height: h }}><ResponsiveContainer>{children}</ResponsiveContainer></div>
const Wait = ({ s, children }) => s.loading ? <Loading /> : s.error ? <ErrorBox error={s.error} /> : children(s.data)
const grid = <CartesianGrid strokeDasharray="3 3" />
const inp = 'border border-slate-300 rounded px-2 py-1 text-sm w-24'

export function Dashboard({ a }) {
  const s = useLoad(() => get('/sales/summary'), [a]); const sm = a.summary, b = a.budget
  const f = a.forecast.reduce((t, x) => t + x.total, 0); const urgent = a.recommendations.filter(r => ['Critical', 'High'].includes(r.priority))
  return <>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
      <Stat label="Revenue (history)" value={inr(sm.revenue)} /><Stat label="Units sold" value={sm.units_sold} /><Stat label="Active products" value={sm.products} />
      <Stat label="Low-stock products" value={sm.low_stock} tone="text-amber-600" /><Stat label="Critical + High restock" value={sm.critical + sm.high} tone="text-red-600" />
      <Stat label={`Forecast demand (${a.horizon}d units)`} value={Math.round(f)} /><Stat label="Anomalies detected" value={a.anomalies.length} />
      <Stat label="Plan cost / remaining budget" value={`${inr(b.spent)} / ${inr(b.remaining)}`} tone="text-green-700" />
    </div>
    <Card title="Daily units sold (last 90 days)"><Wait s={s}>{d => <Chart><AreaChart data={d.daily}>{grid}<XAxis dataKey="date" tick={{ fontSize: 10 }} /><YAxis /><Tooltip /><Area dataKey="units" stroke="#2563eb" fill="#bfdbfe" /></AreaChart></Chart>}</Wait></Card>
    <Card title="Recommended actions">{urgent.length ? <ul className="list-disc pl-5 text-sm space-y-1">{urgent.map(r => <li key={r.product_id}><b>{r.name}</b>: order {r.order_qty} units ({inr(r.cost)}) <Badge v={r.priority} /> — {r.days_of_supply ?? 'n/a'} days of supply left</li>)}</ul> : 'No urgent actions.'}</Card>
  </>
}

export function SalesPage() {
  const s = useLoad(() => get('/sales/summary'), [])
  return <Wait s={s}>{d => { const c = d.compare, pct = (x, y) => y ? ((x - y) / y * 100).toFixed(1) + '%' : 'n/a'; return <>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4"><Stat label="Units, last 28d" value={c.current_units} /><Stat label="vs previous 28d" value={pct(c.current_units, c.previous_units)} /><Stat label="Revenue, last 28d" value={inr(c.current_revenue)} /><Stat label="Revenue change" value={pct(c.current_revenue, c.previous_revenue)} /></div>
    <Card title="Daily units (left) and revenue ₹ (right)"><Chart><LineChart data={d.daily}>{grid}<XAxis dataKey="date" tick={{ fontSize: 10 }} /><YAxis yAxisId="l" /><YAxis yAxisId="r" orientation="right" /><Tooltip /><Legend /><Line yAxisId="l" dataKey="units" stroke="#2563eb" dot={false} /><Line yAxisId="r" dataKey="revenue" stroke="#16a34a" dot={false} /></LineChart></Chart></Card>
    <Card title="Weekly units"><Chart h={220}><BarChart data={d.weekly}>{grid}<XAxis dataKey="week" tick={{ fontSize: 10 }} /><YAxis /><Tooltip /><Bar dataKey="units" fill="#3b82f6" /></BarChart></Chart></Card>
    <div className="grid md:grid-cols-2 gap-4"><Card title="Best sellers"><Table head={['Product', 'Units', 'Revenue']} rows={d.top.map(r => [r.name, r.units, inr(r.revenue)])} /></Card>
      <Card title="Slow movers">{d.slow_note && <p className="text-amber-700 text-sm">{d.slow_note}</p>}<Table head={['Product', 'Units', 'Revenue']} rows={d.slow.map(r => [r.name, r.units, inr(r.revenue)])} /></Card></div></> }}</Wait>
}

export function ForecastPage() {
  const [h, setH] = useState(7); const [pid, setPid] = useState('P01'); const f = useLoad(() => post('/forecast', { horizon: h }), [h])
  return <Wait s={f}>{d => {
    const all = d.forecasts, p = all.find(x => x.product_id === pid) || all[0]; let chart = [], bt = []
    if (p.reliable) { chart = p.history.map((v, i) => ({ date: addDays(p.last_date, i - p.history.length + 1), actual: v })); const m = p.mae_model
      p.forecast.forEach((v, i) => chart.push({ date: addDays(p.last_date, i + 1), forecast: v, band: [Math.max(0, v - 1.28 * m), v + 1.28 * m] }))
      bt = p.backtest.actual.map((v, i) => ({ day: 'T+' + (i + 1), actual: v, model: p.backtest.model[i], baseline: p.backtest.baseline[i] })) }
    return <>
      <Card title="Demand forecast" right={<div className="flex gap-2"><select className={inp + ' w-48'} value={p.product_id} onChange={e => setPid(e.target.value)}>{all.map(x => <option key={x.product_id} value={x.product_id}>{x.product_id} {x.name}</option>)}</select>
        {[7, 30].map(n => <Btn key={n} className={h === n ? '' : '!bg-slate-400'} onClick={() => setH(n)}>{n} days</Btn>)}</div>}>
        {d.warnings.map(w => <p key={w} className="text-amber-700 text-sm">{w}</p>)}
        {p.reliable ? <><Chart><ComposedChart data={chart}>{grid}<XAxis dataKey="date" tick={{ fontSize: 10 }} /><YAxis /><Tooltip /><Legend /><Area dataKey="band" name="approx. range" stroke="none" fill="#fde68a" /><Line dataKey="actual" stroke="#0f172a" dot={false} /><Line dataKey="forecast" stroke="#2563eb" strokeWidth={2} dot={false} /></ComposedChart></Chart>
          <p className="text-xs text-slate-500 mt-2">Method: {p.method}. Range ≈ forecast ± 1.28 × backtest MAE (rough guide, not a statistical interval). Assumes recent weekday pattern continues; {p.note}.{p.intermittent && ' Intermittent demand: treat with caution.'}</p></> : <p>{p.note}</p>}
      </Card>
      {p.reliable && <Card title="Backtest: last 7 days (model trained only on earlier days)"><Chart h={220}><LineChart data={bt}>{grid}<XAxis dataKey="day" /><YAxis /><Tooltip /><Legend /><Line dataKey="actual" stroke="#0f172a" /><Line dataKey="model" stroke="#2563eb" /><Line dataKey="baseline" stroke="#f59e0b" strokeDasharray="4 4" /></LineChart></Chart><p className="text-xs text-slate-500">MAE — model {p.mae_model}, baseline {p.mae_baseline} units/day.</p></Card>}
      <Card title={`All products — ${h}-day forecast`}><Table head={['Product', 'Total', 'Per day', 'Trend', 'Method', 'MAE model', 'MAE baseline']} rows={all.map(x => [x.name, x.reliable ? x.total.toFixed(1) : '—', x.reliable ? x.daily.toFixed(1) : '—', x.trend || x.note, x.method || '—', x.mae_model ?? '—', x.mae_baseline ?? '—'])} /></Card></> }}</Wait>
}

export function InventoryPage({ a, refresh }) {
  const [rows, setRows] = useState(null); const [err, setErr] = useState(); const [nw, setNw] = useState({ product_id: '', name: '', category: 'General', unit_cost: 0, stock: 0 })
  const load = () => get('/products').then(setRows).catch(setErr); useEffect(() => { load() }, [])
  const rm = Object.fromEntries(a.recommendations.map(r => [r.product_id, r]))
  const edit = (i, k, v) => setRows(rows.map((r, j) => j === i ? { ...r, [k]: v } : r))
  const saveRow = async r => { try { setErr(); await put('/products/' + r.product_id, { stock: +r.stock, min_stock: +r.min_stock, incoming: +r.incoming, unit_cost: +r.unit_cost, lead_days: r.lead_days == null || r.lead_days === '' ? undefined : +r.lead_days }); refresh() } catch (e) { setErr(e) } }
  const add = async () => { try { setErr(); await post('/products', { ...nw, unit_cost: +nw.unit_cost, stock: +nw.stock }); setNw({ product_id: '', name: '', category: 'General', unit_cost: 0, stock: 0 }); await load(); refresh() } catch (e) { setErr(e) } }
  const n = (r, k, w = 'w-20') => <input type="number" className={inp + ' ' + w} value={r[k] ?? ''} onChange={e => edit(rows.indexOf(r), k, e.target.value)} />
  if (!rows) return err ? <ErrorBox error={err} /> : <Loading />
  return <><ErrorBox error={err} />
    <Card title="Inventory monitor (edit and save)"><Table head={['ID', 'Name', 'Category', 'Stock', 'Min', 'Incoming', 'Unit cost', 'Lead d', 'Avg/day', 'Days left', 'Priority', '']}
      rows={rows.map(r => [r.product_id, r.name, r.category, n(r, 'stock'), n(r, 'min_stock'), n(r, 'incoming'), n(r, 'unit_cost'), n(r, 'lead_days'), rm[r.product_id]?.daily_demand ?? '—', rm[r.product_id]?.days_of_supply ?? 'n/a', <Badge v={rm[r.product_id]?.priority || '—'} />, <Btn onClick={() => saveRow(r)}>Save</Btn>])} /></Card>
    <Card title="Add product"><div className="flex flex-wrap gap-2 items-end">{[['product_id', 'ID'], ['name', 'Name'], ['category', 'Category'], ['unit_cost', 'Unit cost'], ['stock', 'Stock']].map(([k, l]) => <label key={k} className="text-xs">{l}<br /><input className={inp} value={nw[k]} onChange={e => setNw({ ...nw, [k]: e.target.value })} /></label>)}<Btn onClick={add}>Add</Btn></div></Card></>
}

export function AnomalyPage() {
  const [z, setZ] = useState(3.5); const s = useLoad(() => post('/anomalies/detect', { z_threshold: z }), [z])
  return <Card title="Unusual sales detection (robust z-score)" right={<label className="text-sm">z threshold <input type="number" step="0.5" className={inp} value={z} onChange={e => setZ(+e.target.value || 3.5)} /></label>}><Wait s={s}>{d => <>
    <p className="text-sm text-slate-600 mb-2">{d.count} flagged. A flag is a prompt to check records, not proof of fraud or a guarantee of future demand.</p>
    <Table head={['Product', 'Date', 'Observed', 'Expected', 'Score', 'Severity', 'Why', 'Next step']} rows={d.anomalies.map(x => [x.name, x.date, x.observed, x.expected, x.score, <Badge v={x.severity} />, x.reason, x.action])} empty="No unusual sales at this threshold." /></>}</Wait></Card>
}

export function RestockPage() {
  const [p, setP] = useState({ cover_days: 7, safety_days: 2 }); const s = useLoad(() => post('/recommendations/restock', p), [p.cover_days, p.safety_days])
  return <Card title="Smart restocking" right={<div className="flex gap-3 text-sm">{[['cover_days', 'Cover days'], ['safety_days', 'Safety days']].map(([k, l]) => <label key={k}>{l} <input type="number" className={inp + ' w-16'} value={p[k]} onChange={e => setP({ ...p, [k]: +e.target.value || 0 })} /></label>)}</div>}>
    <Wait s={s}>{d => <><p className="text-xs text-slate-500 mb-2">Target = daily forecast × (lead time + cover + safety days). Order = max(0, target − stock − incoming). Missing lead times default to 3 days.</p>
      <Table head={['Product', 'Stock', 'Incoming', 'Per day', 'Days left', 'Target', 'Order', 'Cost', 'Priority', 'Reason']} rows={d.recommendations.map(r => [r.name, r.stock, r.incoming, r.daily_demand, r.days_of_supply ?? 'n/a', r.target_stock, r.order_qty, inr(r.cost), <Badge v={r.priority} />, r.reason])} /></>}</Wait></Card>
}

export function BudgetPage({ a, budget }) {
  const [b, setB] = useState(budget); const [cons, setCons] = useState({}); const [res, setRes] = useState(); const [err, setErr] = useState()
  const run = async () => { try { setErr(); setRes(await post('/optimization/budget', { budget: +b, constraints: cons })) } catch (e) { setErr(e) } }
  useEffect(() => { run() }, []); const needs = a.recommendations.filter(r => r.order_qty > 0)
  const setC = (pid, k, v) => setCons({ ...cons, [pid]: { ...(cons[pid] || {}), ...(v === '' ? {} : { [k]: +v }) } })
  return <><ErrorBox error={err} />
    <Card title="Budget optimization" right={<div className="flex gap-2 items-center text-sm">Budget ₹<input type="number" className={inp} value={b} onChange={e => setB(e.target.value)} /><Btn onClick={run}>Recalculate</Btn></div>}>
      {res && <><div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3"><Stat label="Full plan cost" value={inr(res.full_cost)} /><Stat label="Proposed spend" value={inr(res.spent)} tone="text-green-700" /><Stat label="Remaining" value={inr(res.remaining)} /><Stat label="Weighted need covered" value={Math.round(res.weighted_coverage * 100) + '%'} /></div>
        <p className="text-sm mb-1">{res.fits_fully ? 'The full recommended plan fits the budget.' : 'The full plan exceeds the budget; this is the best affordable plan.'} Solver: <b>{res.method === 'milp' ? 'exact integer program (MILP)' : 'greedy fallback (not proven optimal)'}</b>.</p>
        <p className="text-xs text-slate-500 mb-3">Objective: {res.objective}</p>{res.warnings.map(w => <p key={w} className="text-amber-700 text-sm">{w}</p>)}
        <Chart h={260}><BarChart data={res.items}>{grid}<XAxis dataKey="name" tick={{ fontSize: 9 }} interval={0} angle={-30} textAnchor="end" height={70} /><YAxis /><Tooltip /><Legend /><Bar dataKey="needed" fill="#cbd5e1" /><Bar dataKey="buy" fill="#2563eb" /></BarChart></Chart>
        <Table head={['Product', 'Priority', 'Needed', 'Buy', 'Unmet', 'Cost']} rows={res.items.map(i => [i.name, <Badge v={i.priority} />, i.needed, i.buy, i.unmet, inr(i.cost)])} />
        {res.tradeoffs.length > 0 && <><h4 className="font-medium mt-3">Trade-offs</h4><ul className="list-disc pl-5 text-sm">{res.tradeoffs.map(t => <li key={t}>{t}</li>)}</ul></>}</>}</Card>
    {res && res.sensitivity.length > 0 && <Card title="What if the budget changes?"><Chart h={220}><LineChart data={res.sensitivity.map(s => ({ ...s, coverage: Math.round(s.coverage * 100) }))}>{grid}<XAxis dataKey="budget" /><YAxis unit="%" domain={[0, 100]} /><Tooltip /><Line dataKey="coverage" name="weighted coverage" stroke="#2563eb" /></LineChart></Chart></Card>}
    <Card title="Optional constraints (blank = none)"><Table head={['Product', 'Needed', 'Min qty', 'Max qty', 'Priority weight']} rows={needs.map(r => [r.name, r.order_qty, ...['min', 'max', 'weight'].map(k => <input type="number" className={inp + ' w-16'} onChange={e => setC(r.product_id, k, e.target.value)} />)])} /></Card></>
}

export function AssistantPage({ budget }) {
  const [q, setQ] = useState(''); const [log, setLog] = useState([]); const [busy, setBusy] = useState(false)
  const ask = async text => { if (!text.trim()) return; setBusy(true); try { const r = await post('/ai/insights', { question: text, budget: +budget }); setLog(l => [{ q: text, r }, ...l]) } catch (e) { setLog(l => [{ q: text, e }, ...l]) } setBusy(false); setQ('') }
  const ex = ['Which products should I restock first?', 'What might sell the most next week?', 'Which products may run out soon?', 'Why was a product flagged as unusual?', 'What can I purchase with a budget of ₹5000?', 'Which products have declining sales?']
  return <><Card title="AI Decision Assistant"><div className="flex gap-2 mb-2"><input className="flex-1 border border-slate-300 rounded px-3 py-2" value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && ask(q)} placeholder="Ask about your shop…" /><Btn disabled={busy} onClick={() => ask(q)}>{busy ? 'Working…' : 'Ask'}</Btn></div>
    <div className="flex flex-wrap gap-2">{ex.map(e => <button key={e} className="text-xs bg-slate-100 rounded-full px-3 py-1" onClick={() => ask(e)}>{e}</button>)}</div></Card>
    {log.map((m, i) => <Card key={i} title={m.q}>{m.e ? <ErrorBox error={m.e} /> : <><p className="mb-2">{m.r.answer}</p><p className="text-xs text-slate-500">Calculation used: {m.r.tool_used} · {m.r.llm_used ? 'explained by local language model' : m.r.note}</p>{m.r.llm_used && <details className="text-xs mt-1"><summary>Computed facts sent to the model</summary>{m.r.facts}</details>}</>}</Card>)}</>
}

export function DataPage({ refresh, openAnalysis, budget }) {
  const [kind, setKind] = useState('sales'); const [mode, setMode] = useState('append'); const [msg, setMsg] = useState(); const [err, setErr] = useState(); const [tick, setTick] = useState(0)
  const im = useLoad(() => get('/data/imports'), [tick]); const an = useLoad(() => get('/analyses'), [tick])
  const run = async fn => { try { setErr(); setMsg(await fn()); setTick(t => t + 1); refresh() } catch (e) { setErr(e); setMsg() } }
  return <><ErrorBox error={err} />{msg && <div className="bg-green-50 border border-green-200 text-green-800 rounded-lg p-3 mb-3 text-sm">{JSON.stringify(msg)}</div>}
    <Card title="Upload CSV"><div className="flex flex-wrap gap-3 items-center text-sm">
      <select className={inp} value={kind} onChange={e => setKind(e.target.value)}><option value="sales">sales</option><option value="inventory">inventory</option></select>
      <select className={inp} value={mode} onChange={e => setMode(e.target.value)}><option value="append">append (skip duplicates)</option><option value="replace">replace</option></select>
      <input type="file" accept=".csv" onChange={e => e.target.files[0] && run(() => upload(`/data/upload?kind=${kind}&mode=${mode}`, e.target.files[0]))} /></div>
      <p className="text-xs text-slate-500 mt-2">Sales policy: one row per product per day; rows whose date + product already exist are skipped; negative quantities (returns) are rejected; identical files cannot be imported twice.</p>
      <div className="flex gap-3 mt-2 text-sm"><Btn onClick={() => save('/data/templates/sales.csv', 'sales_template.csv')}>Sales template</Btn><Btn onClick={() => save('/data/templates/inventory.csv', 'inventory_template.csv')}>Inventory template</Btn>
        <Btn className="!bg-amber-600" onClick={() => window.confirm('Reset all data to the demo dataset?') && run(() => post('/demo-data/reset'))}>Load / reset demo data</Btn>
        <Btn className="!bg-green-700" onClick={() => save('/reports/export', 'stockwise_report.csv', { budget: +budget })}>Download CSV report</Btn></div></Card>
    <Card title="Import history"><Wait s={im}>{d => <Table head={['#', 'When', 'File', 'Kind', 'Mode', 'Result']} rows={d.map(r => [r.id, r.created, r.filename, r.kind, r.mode, r.summary])} />}</Wait></Card>
    <Card title="Analysis history (click to open)"><Wait s={an}>{d => <Table head={['ID', 'When', 'Horizon', 'Budget', '']} rows={d.map(r => [r.id, r.created, r.horizon + 'd', inr(r.budget), <Btn onClick={() => openAnalysis(r.id)}>Open</Btn>])} />}</Wait></Card></>
}
