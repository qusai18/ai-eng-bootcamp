import { cleanReadme } from './scoring.js';

function detailOf(body) {
  if (!body) return null;
  return body.detail && typeof body.detail === 'object' ? body.detail : body;
}

export function applyRate(rate, bucket, state) {
  if (!rate) return;
  const slot = bucket === 'c' ? state.bud.c : state.bud.s;
  if (rate.remaining != null && rate.remaining !== '') slot.r = +rate.remaining;
  if (rate.limit != null && rate.limit !== '') slot.l = +rate.limit;
}

export async function ghSearch(q, { sort, per = 10, signal, state } = {}) {
  const p = new URLSearchParams({ q, per_page: String(per) });
  if (sort && sort !== 'best') p.set('sort', sort);
  let response;
  try {
    response = await fetch('/api/search?' + p.toString(), { signal });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw { net: true, message: 'the wire is down' };
  }
  let body = null;
  try { body = await response.json(); } catch (err) { body = null; }
  if (state) applyRate(body && body.rate, 's', state);
  const detail = detailOf(body);
  if (response.status === 403 || response.status === 429) {
    throw { rate: true, reset: detail && detail.reset, message: (detail && detail.message) || 'rate budget spent' };
  }
  if (response.status === 422) {
    throw { invalid: true, message: (detail && detail.message) || 'GitHub rejected the query' };
  }
  if (!response.ok) {
    throw { net: true, message: (detail && detail.message) || 'the wire is down' };
  }
  return (body && body.items) || [];
}

export async function fetchReadme(full, { signal, state } = {}) {
  const parts = String(full || '').split('/');
  if (parts.length !== 2 || !parts[0] || !parts[1]) return null;
  let response;
  try {
    response = await fetch('/api/readme/' + encodeURIComponent(parts[0]) + '/' + encodeURIComponent(parts[1]), { signal });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    return null;
  }
  let body = null;
  try { body = await response.json(); } catch (err) { body = null; }
  if (state) applyRate(body && body.rate, 'c', state);
  if (!response.ok || !body || typeof body.text !== 'string') return null;
  return cleanReadme(body.text);
}

export async function refreshBudget(state) {
  const response = await fetch('/api/rate-limit');
  if (!response.ok) throw new Error('rate limit unreachable');
  const data = await response.json();
  state.bud = {
    s: { r: data.search.remaining, l: data.search.limit },
    c: { r: data.core.remaining, l: data.core.limit },
  };
}
