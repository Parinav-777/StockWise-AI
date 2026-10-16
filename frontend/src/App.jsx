import React, { useState, useEffect, useCallback } from 'react'
import { LayoutDashboard, BarChart3, TrendingUp, Package, AlertTriangle, ShoppingCart, Wallet, Bot, Database } from 'lucide-react'
import { get, post } from './api/client.js'
import { Loading, ErrorBox, Btn } from './components/ui.jsx'
import * as P from './pages/pages.jsx'
const NAV = [['Dashboard', LayoutDashboard], ['Sales Analytics', BarChart3], ['Demand Forecasting', TrendingUp], ['Inventory Monitor', Package], ['Anomaly Detection', AlertTriangle], ['Smart Restocking', ShoppingCart], ['Budget Optimization', Wallet], ['AI Decision Assistant', Bot], ['Data Management', Database]]
export default function App() {
  const [page, setPage] = useState('Dashboard'); const [a, setA] = useState(); const [err, setErr] = useState(); const [budget, setBudget] = useState(5000); const [ai, setAi] = useState()
  const refresh = useCallback(async () => { try { setErr(); setA(await post('/analysis', { horizon: 7, budget: +budget })) } catch (e) { setErr(e) } }, [budget])
  const openAnalysis = async id => { try { setA(await get('/analysis/' + id)); setPage('Dashboard') } catch (e) { setErr(e) } }
  useEffect(() => { refresh() }, []); useEffect(() => { get('/ai/status').then(setAi).catch(() => setAi({ available: false })) }, [])
  const body = () => { if (!a) return err ? null : <Loading />; const props = { a, refresh, budget }
    return { 'Dashboard': <P.Dashboard {...props} />, 'Sales Analytics': <P.SalesPage />, 'Demand Forecasting': <P.ForecastPage />, 'Inventory Monitor': <P.InventoryPage {...props} />, 'Anomaly Detection': <P.AnomalyPage />, 'Smart Restocking': <P.RestockPage />, 'Budget Optimization': <P.BudgetPage key={a.analysis_id} {...props} />, 'AI Decision Assistant': <P.AssistantPage {...props} />, 'Data Management': <P.DataPage {...props} openAnalysis={openAnalysis} /> }[page] }
  return <div className="flex min-h-screen text-slate-800">
    <aside className="w-56 bg-slate-900 text-slate-200 p-3 shrink-0"><h1 className="text-white font-bold text-lg mb-4 px-2">StockWise AI</h1>
      {NAV.map(([n, I]) => <button key={n} onClick={() => setPage(n)} className={'flex items-center gap-2 w-full text-left px-2 py-2 rounded text-sm ' + (page === n ? 'bg-blue-600 text-white' : 'hover:bg-slate-800')}><I size={16} />{n}</button>)}
      <div className="mt-6 text-xs px-2">{ai?.available ? <span className="text-green-400">● AI model ready ({ai.model})</span> : <span className="text-amber-400">● AI model offline — analysis still works. {ai?.help}</span>}</div></aside>
    <main className="flex-1 p-5 overflow-x-hidden"><div className="flex justify-between items-center mb-4"><h2 className="text-xl font-semibold">{page}</h2>
      <div className="flex items-center gap-2 text-sm">{a?.analysis_id && <span className="text-slate-500">analysis #{a.analysis_id}</span>}Budget ₹<input type="number" min="0" value={budget} onChange={e => setBudget(e.target.value)} className="border border-slate-300 rounded px-2 py-1 w-24" /><Btn onClick={refresh}>Recalculate</Btn></div></div>
      <ErrorBox error={err} />{body()}</main></div>
}
