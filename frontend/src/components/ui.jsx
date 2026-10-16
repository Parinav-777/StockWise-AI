import React, { useState, useEffect } from 'react'
export const Card = ({ title, children, right }) => (<div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 mb-4">{(title || right) && <div className="flex justify-between items-center mb-3"><h3 className="font-semibold text-slate-800">{title}</h3>{right}</div>}{children}</div>)
export const Stat = ({ label, value, tone }) => (<div className="bg-white rounded-xl border border-slate-200 p-4"><div className="text-xs text-slate-500">{label}</div><div className={'text-2xl font-bold ' + (tone || 'text-slate-900')}>{value}</div></div>)
export const Loading = () => <div className="p-6 text-slate-500 animate-pulse">Loading…</div>
export const ErrorBox = ({ error }) => error ? <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-3">{String(error.message || error)}</div> : null
const T = { Critical: 'bg-red-100 text-red-700', High: 'bg-amber-100 text-amber-700', Medium: 'bg-yellow-100 text-yellow-700', Low: 'bg-blue-100 text-blue-700', 'No action': 'bg-green-100 text-green-700', Medium_: '' }
export const Badge = ({ v }) => <span className={'px-2 py-0.5 rounded text-xs font-medium ' + (T[v] || 'bg-slate-100 text-slate-700')}>{v}</span>
export const Btn = ({ children, ...p }) => <button {...p} className={'bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-md text-sm disabled:opacity-50 ' + (p.className || '')}>{children}</button>
export const Table = ({ head, rows, empty = 'No data yet' }) => rows.length ? (<div className="overflow-auto max-h-96"><table className="w-full text-sm"><thead className="sticky top-0 bg-slate-50"><tr>{head.map(h => <th key={h} className="text-left p-2 font-medium text-slate-600 whitespace-nowrap">{h}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={i} className="border-t border-slate-100">{r.map((c, j) => <td key={j} className="p-2">{c}</td>)}</tr>)}</tbody></table></div>) : <div className="text-slate-500 p-3">{empty}</div>
export function useLoad(fn, deps) {
  const [s, setS] = useState({ loading: true })
  useEffect(() => { let ok = true; setS(x => ({ ...x, loading: true })); fn().then(d => ok && setS({ data: d, loading: false })).catch(e => ok && setS({ error: e, loading: false })); return () => { ok = false } }, deps)
  return s
}
