import { LEX, LEDGER, PAINS, STACK_PAINS, STOP } from './lexicon.js';

export const daysSince = iso => (Date.now() - new Date(iso).getTime()) / 864e5;

export const ago = iso => {
  const d = daysSince(iso);
  if (d < 1) return 'today';
  if (d < 60) return `${d | 0} days ago`;
  if (d < 365) return `${(d / 30) | 0} months ago`;
  return `${(d / 365) | 0} years ago`;
};

export const fmtStars = n => n >= 1000 ? (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k' : String(n || 0);

export function extractSignals(txt) {
  const found = [];
  for (const [k, rx, g, l] of LEX) {
    const m = rx.exec(txt);
    if (m) found.push({ k, g, l, pos: m.index });
  }
  return found.sort((a, b) => a.pos - b.pos);
}

export function diagnose(text) {
  if (!text.trim()) return null;
  const t = ' ' + text.toLowerCase() + ' ';
  let best = null, bs = 0;
  for (const p of PAINS) {
    let s = 0;
    p.kws.forEach((w, i) => {
      const rx = new RegExp('\\b' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'gi');
      const hits = (t.match(rx) || []).length;
      if (hits) s += hits * (i === 0 ? 3 : 1.4);
    });
    if (s > bs) { bs = s; best = p; }
  }
  return bs >= 2 ? best : null;
}

export function termsFrom(txt) {
  const words = txt.toLowerCase().split(/\s+/).map(w => w.trim())
    .filter(w => w && !w.includes(':') && w.length >= 3 && !STOP.has(w));
  return [...new Set(words)].slice(0, 6);
}

const PUSHED_SINCE = '2025-01-01';
const SORT_NOTE = { best: 'sort by best match', stars: 'sort by stars', updated: 'sort by recent push' };

function hasQualifier(q, name) {
  return new RegExp(`(?:^|\\s)${name}:`, 'i').test(String(q || ''));
}

function starNote(q, minStars) {
  if (hasQualifier(q, 'stars')) return 'star floor as typed';
  if (!minStars) return 'minimum stars any';
  if (minStars >= 1000 && minStars % 1000 === 0) return `minimum stars ${minStars / 1000}K`;
  return `minimum stars ${minStars}`;
}

export function surveyCriteria(q, { sort = 'best', minStars = 0 } = {}) {
  const text = String(q || '');
  return [
    hasQualifier(text, 'archived') ? 'archived filter as typed' : 'not archived',
    hasQualifier(text, 'fork') ? 'fork filter as typed' : 'not a fork',
    hasQualifier(text, 'pushed') ? 'pushed filter as typed' : `pushed since ${PUSHED_SINCE}`,
    hasQualifier(text, 'in') ? 'match scope as typed' : 'words matched in name and description',
    starNote(text, minStars),
    SORT_NOTE[sort] || `sort by ${sort}`,
  ];
}

export function surveyFullQuery(q, minStars) {
  const text = String(q || '').trim();
  const parts = [text];
  if (!hasQualifier(text, 'archived')) parts.push('archived:false');
  if (!hasQualifier(text, 'fork')) parts.push('fork:false');
  if (!hasQualifier(text, 'pushed')) parts.push(`pushed:>=${PUSHED_SINCE}`);
  if (!hasQualifier(text, 'in')) parts.push('in:name,description');
  if (minStars && !hasQualifier(text, 'stars')) parts.push(`stars:>=${minStars}`);
  return parts.filter(Boolean).join(' ');
}

export function planSurvey(q, { sort = 'best', minStars = 0 } = {}) {
  const full = surveyFullQuery(q, minStars);
  const d = diagnose(q);
  const adjacent = d ? d.adj.slice(0, 3) : ['types', 'tests', 'deploy', 'docs'];
  return {
    mode: 'survey',
    queries: [{ q: full, per: 20, sort }],
    ctx: { signals: [], terms: termsFrom(q), painKws: d ? d.kws : null, pain: d },
    adjacent,
    offlineCats: d ? [d.id, ...d.adj.slice(0, 2)] : ['types', 'tests', 'deploy'],
    headline: `search — “${q}”`,
    subline: `raw query: ${full}`,
  };
}

export function planContext(sigs) {
  const use = sigs.slice(0, 3);
  const queries = use.map(s => ({ q: `${s.g} topic:${s.g} stars:>=300`, per: 8 }));
  if (use.length >= 2) queries.push({ q: `${use[0].g} ${use[1].g}`, per: 8 });
  else if (use.length) queries.push({ q: `awesome ${use[0].g}`, per: 8 });
  const adj = [...new Set(sigs.slice(0, 5).flatMap(s => STACK_PAINS[s.k] || []))].slice(0, 6);
  const cats = adj.length ? adj.slice(0, 4) : ['types', 'tests', 'deploy', 'docs'];
  return {
    mode: 'context',
    queries,
    ctx: { signals: sigs.slice(0, 6), terms: [], painKws: null, pain: null },
    adjacent: adj,
    offlineCats: cats,
    headline: `ideation — ${sigs.length} signals`,
    subline: sigs.slice(0, 6).map(s => s.l).join(' · '),
  };
}

export function planPain(txt) {
  const dx = diagnose(txt);
  if (dx) {
    return {
      mode: 'pain',
      queries: dx.qs.map(q => ({ q, per: 8 })),
      ctx: { signals: [], terms: [], painKws: dx.kws, pain: dx },
      adjacent: dx.adj,
      offlineCats: [dx.id, ...dx.adj.slice(0, 2)],
      headline: `diagnosis — ${dx.dx}`,
      subline: dx.say,
    };
  }
  const words = termsFrom(txt);
  const list = words.length ? words : [txt.slice(0, 30)];
  const queries = [{ q: list.join(' '), per: 10 }];
  if (list.length) queries.push({ q: 'awesome ' + list[0], per: 8 });
  return {
    mode: 'pain',
    queries,
    ctx: { signals: [], terms: list, painKws: null, pain: null },
    adjacent: ['types', 'tests', 'deploy', 'docs'],
    offlineCats: ['types', 'tests', 'deploy', 'docs'],
    headline: 'freeform search',
    subline: txt.slice(0, 80),
  };
}

export function cleanReadme(t) {
  t = t.replace(/<!--[\s\S]*?-->/g, '')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/^#{1,6}\s*/gm, '')
    .replace(/[*_>`]/g, '')
    .replace(/\r/g, '');
  const lines = t.split('\n').map(l => l.trim()).filter(Boolean);
  const out = [];
  let len = 0;
  for (const l of lines) {
    if (len > 520) break;
    out.push(l);
    len += l.length;
  }
  return out.join('\n');
}

export function whyFor(r, ctx, overlap) {
  const parts = [];
  if (overlap.length) parts.push(`matches ${overlap.length}/${ctx.signals.length} of your signals (${overlap.map(s => s.l).join(', ')})`);
  if (ctx.pain) parts.push(`prescribed for ${ctx.pain.dx.toLowerCase()}`);
  else if (ctx.terms && ctx.terms.length) {
    const hay = (r.full_name + ' ' + (r.description || '')).toLowerCase();
    const m = ctx.terms.filter(t => hay.includes(t)).slice(0, 3);
    if (m.length) parts.push(`matches your terms: ${m.join(', ')}`);
  }
  const st = r.stargazers_count || 0;
  const d = daysSince(r.pushed_at);
  if (st > 20000) parts.push('heavy field support');
  else if (st > 2000) parts.push('proven in the field');
  else if (st > 200) parts.push('modest but real traction');
  else parts.push('young claim — inspect before trusting');
  if (d < 14) parts.push('pushed ' + ago(r.pushed_at));
  else if (d < 120) parts.push('active recently');
  if (r.archived) parts.push('ARCHIVED — read, don’t adopt');
  if (r.ledger) parts.push('offline ledger entry, counts approximate');
  if (!parts.length) parts.push('surfaced by search relevance');
  return parts.join(' · ');
}

export function makeItem(r, ctx) {
  const hay = (r.full_name + ' ' + (r.description || '') + ' ' + (r.topics || []).join(' ')).toLowerCase();
  let overlap = [];
  if (ctx.signals && ctx.signals.length) {
    overlap = ctx.signals.filter(s => hay.includes(s.k) || hay.includes(s.g) || (r.language || '').toLowerCase() === s.k);
  }
  let painHit = 0;
  if (ctx.painKws) ctx.painKws.forEach(w => { if (hay.includes(w)) painHit++; });

  const st = r.stargazers_count || 0;
  const d = daysSince(r.pushed_at);
  let fit = 0;
  if (ctx.signals && ctx.signals.length) fit += Math.min(30, Math.round(30 * overlap.length / ctx.signals.length));
  if (ctx.painKws) fit += Math.min(12, painHit * 4);
  if (!ctx.signals.length && !ctx.painKws && ctx.terms && ctx.terms.length) {
    const m = ctx.terms.filter(t => hay.includes(t));
    fit += Math.min(28, Math.round(28 * m.length / ctx.terms.length));
  }
  fit += Math.min(44, Math.log10(st + 1) * 10.5);
  fit += d < 14 ? 18 : d < 45 ? 13 : d < 120 ? 8 : d < 365 ? 3 : 0;
  if (r.archived) fit = Math.min(fit, 18);
  fit = Math.max(5, Math.min(98, Math.round(fit)));
  return { r, fit, why: whyFor(r, ctx, overlap) };
}

export function ledgerServe(plan) {
  const cats = (plan.offlineCats && plan.offlineCats.length) ? plan.offlineCats : ['types', 'tests', 'deploy', 'docs'];
  const kw = (plan.ctx.painKws || []).concat(plan.ctx.terms || []).map(w => w.toLowerCase());
  const out = [];
  cats.forEach((c, ci) => {
    (LEDGER[c] || []).forEach((e, i) => {
      const [full, desc, lang, stars] = e;
      let s = Math.log10(stars + 1) * 9 + (ci === 0 ? 7 : 4 - ci);
      const hay = (full + ' ' + desc).toLowerCase();
      kw.forEach(w => { if (hay.includes(w)) s += 2.5; });
      out.push({
        r: {
          full_name: full,
          description: desc,
          language: lang,
          stargazers_count: stars,
          html_url: 'https://github.com/' + full,
          topics: [c],
          archived: false,
          pushed_at: new Date(Date.now() - (4 + i * 9 + ci * 3) * 864e5).toISOString(),
          owner: { login: full.split('/')[0] },
          ledger: true,
        },
        fit: Math.max(12, Math.min(96, Math.round(s))),
        why: '',
      });
    });
  });
  out.forEach(it => { it.why = whyFor(it.r, plan.ctx, []); });
  return out.sort((a, b) => b.fit - a.fit).slice(0, 10);
}

export function settleClaims(items, plan, { rateLimited = false, netDown = false } = {}) {
  if (items.length) {
    const list = items.slice(0, 60).map(r => makeItem(r, plan.ctx)).sort((a, b) => b.fit - a.fit).slice(0, 12);
    return { source: (rateLimited || netDown) ? 'partial' : 'live', list };
  }
  if (rateLimited || netDown) return { source: 'ledger', list: ledgerServe(plan) };
  return { source: 'empty', list: [] };
}
