const BASE = '/api/v1'
async function req(p, o) {
  let r
  try { r = await fetch(BASE + p, o) } catch { throw new Error('Cannot reach the backend. Is it running on port 8000?') }
  if (!r.ok) { let m = 'Request failed (' + r.status + ')'; try { const j = await r.json(); m = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail) } catch {} throw new Error(m) }
  return r
}
const J = (method, b) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) })
export const get = async p => (await req(p)).json()
export const post = async (p, b) => (await req(p, J('POST', b))).json()
export const put = async (p, b) => (await req(p, J('PUT', b))).json()
export const upload = async (p, file) => { const f = new FormData(); f.append('file', file); return (await req(p, { method: 'POST', body: f })).json() }
export async function save(p, name, body) {
  const r = await req(p, body ? J('POST', body) : undefined); const u = URL.createObjectURL(await r.blob())
  const a = document.createElement('a'); a.href = u; a.download = name; a.click(); URL.revokeObjectURL(u)
}
