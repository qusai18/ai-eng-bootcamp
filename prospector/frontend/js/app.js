import { PAINS, SAMPLE, STACK_PAINS } from './lexicon.js';
import { fetchReadme, ghSearch, refreshBudget } from './github.js';
import {
  ago,
  extractSignals,
  fmtStars,
  planContext,
  planPain,
  planSurvey,
  settleClaims,
  surveyCriteria,
  surveyFullQuery,
  diagnose,
} from './scoring.js';

const el = id => document.getElementById(id);
const qq = s => [...document.querySelectorAll(s)];
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const S = {
  mode: 'survey',
  running: false,
  results: [],
  plan: null,
  signals: [],
  excl: new Set(),
  sort: 'best',
  minStars: 0,
  bud: { s: { r: '—', l: 10 }, c: { r: '—', l: 60 } },
};
let R = { steps: 0, done: 0 };
let runAbort = null;
let runGen = 0;

const logbox = el('log');
const caret = el('caret');

function tickClock() { el('clock').textContent = new Date().toTimeString().slice(0, 8); }
setInterval(tickClock, 1000);
tickClock();

function renderBudget() {
  el('budget').innerHTML = `SEARCH <b>${S.bud.s.r}/${S.bud.s.l}</b> · CORE <b>${S.bud.c.r}/${S.bud.c.l}</b>`;
}

async function loadBudget() {
  try {
    await refreshBudget(S);
    renderBudget();
  } catch (err) {
    el('budget').textContent = 'UNREACHABLE';
  }
}
loadBudget();

function log(text, sub) {
  const d = document.createElement('div');
  d.className = 'ln' + (sub ? ' sub' : '');
  d.innerHTML = `<span class="pfx">${sub ? '↳ ' : '▸ '}</span>${esc(text)}`;
  logbox.insertBefore(d, caret);
  logbox.scrollTop = logbox.scrollHeight;
}
function resetLog() { qq('#log .ln').forEach(n => n.remove()); }

function setFill() {
  const p = R.steps ? Math.min(100, R.done / R.steps * 100) : 0;
  el('rfill').style.width = p + '%';
  el('rflag').style.left = p + '%';
  el('rflag').style.opacity = R.done ? '1' : '0';
}
function resetRuler(n) { R = { steps: n, done: 0 }; setFill(); el('rread').textContent = `SURVEY 0/${n}`; }
function stepRuler() {
  if (!R.steps) return;
  R.done++;
  setFill();
  el('rread').textContent = R.done >= R.steps ? 'COMPLETE' : `SURVEY ${R.done}/${R.steps}`;
}

const MODE_DESC = {
  survey: 'No. 1 — direct search of the GitHub field. The raw query is shown before it fires; qualifiers (topic:, language:, stars:) pass straight through.',
  context: 'No. 2 — Ideation. Paste what your Cursor agent knows: rules files, chat summaries, READMEs. Signals are panned live as you type; searches are drafted from what turns up.',
  pain: 'No. 3 — describe what hurts. You get a diagnosis, a prescription of repositories, and adjacent digs to follow.',
};

function setMode(m) {
  S.mode = m;
  qq('.mode').forEach(b => b.classList.toggle('on', b.dataset.mode === m));
  qq('.stage').forEach(s => s.classList.toggle('on', s.id === 'st-' + m));
  el('modedesc').textContent = MODE_DESC[m];
}

const activeSignals = () => S.signals.filter(s => !S.excl.has(s.k));

function renderSignals() {
  S.signals = extractSignals(el('ctx').value);
  el('sigcount').textContent = S.signals.length;
  const box = el('sigchips');
  box.innerHTML = S.signals.length
    ? S.signals.slice(0, 14).map(s => `<button class="sig${S.excl.has(s.k) ? ' off' : ''}" data-k="${s.k}" type="button" title="click to strike out">${esc(s.l)}</button>`).join('')
    : '<span class="sp-empty">nothing yet — start pasting</span>';
  const ids = [...new Set(S.signals.slice(0, 5).flatMap(s => STACK_PAINS[s.k] || []))].slice(0, 6);
  el('sigguess').innerHTML = ids.length
    ? ids.map(id => {
      const p = PAINS.find(item => item.id === id);
      return p ? `<button class="adjch" data-say="${esc(p.say)}" type="button">${esc(p.dx.toLowerCase())}?</button>` : '';
    }).join('')
    : '<span class="sp-empty">—</span>';
}

el('ptxt').addEventListener('input', () => {
  const d = diagnose(el('ptxt').value);
  const dx = el('dxval');
  const v = d ? d.dx : (el('ptxt').value.trim() ? 'READING…' : 'AWAITING COMPLAINT');
  if (dx.textContent !== v) {
    dx.textContent = v;
    dx.classList.remove('flip');
    void dx.offsetWidth;
    dx.classList.add('flip');
  }
});

function updatePreview() {
  const q = el('qin').value.trim();
  const full = surveyFullQuery(q, S.minStars);
  el('qprev').textContent = `→ GET /api/search?q=${full}${S.sort === 'best' ? '' : '&sort=' + S.sort}`;
  el('scriteria').textContent = 'CRITERIA — ' + surveyCriteria(q, { sort: S.sort, minStars: S.minStars }).join(' · ');
}
el('qin').addEventListener('input', updatePreview);
el('qin').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); run(); } });

function entryHTML(it, i) {
  const r = it.r;
  const pick = i === 0;
  const filled = Math.round(it.fit / 100 * 12);
  let ticks = '';
  for (let t = 0; t < 12; t++) ticks += `<span class="tick${t < filled ? ' f' : ''}" style="transition-delay:${t * 26}ms"></span>`;
  const topics = (r.topics || []).slice(0, 6).map(t => esc(t.toUpperCase())).join(' · ');
  return `<article class="entry${pick ? ' pick' : ''}" style="animation-delay:${i * 70}ms">
    <div class="e-rank">${String(i + 1).padStart(2, '0')}</div>
    <div class="e-main">
      <div class="e-name"><a href="${esc(r.html_url)}" target="_blank" rel="noopener">${esc(r.full_name)}</a>${pick ? '<span class="stamp">FIELD PICK</span>' : ''}${r.archived ? '<span class="stamp arch">ARCHIVED</span>' : ''}</div>
      <div class="e-meta"><i class="dia"></i>${esc(r.language || '—')} · ${fmtStars(r.stargazers_count)} STARS · PUSHED ${ago(r.pushed_at).toUpperCase()} · ${esc((r.owner && r.owner.login) || '')}</div>
      ${r.description ? `<p class="e-desc">${esc(r.description)}</p>` : ''}
      <p class="e-why"><span class="mark">✳</span> ${esc(it.why)}</p>
      ${topics ? `<div class="e-topics">${topics}</div>` : ''}
      ${pick ? '<div class="e-readme" id="pickreadme" hidden></div>' : ''}
    </div>
    <div class="e-side">
      <div class="fit"><div class="ticks">${ticks}</div><div class="fit-n">FIT <b id="fitn-${i}">0</b><span class="fit-pct">/100</span></div></div>
      <div class="e-actions">
        <a class="mini-btn" href="${esc(r.html_url)}" target="_blank" rel="noopener">OPEN ↗</a>
        <button class="mini-btn copy1" data-i="${i}" type="button">COPY FOR CURSOR</button>
      </div>
    </div>
  </article>`;
}

function countUp(elm, target) {
  if (!elm) return;
  const t0 = performance.now();
  const dur = 600;
  (function frame(t) {
    const p = Math.min(1, (t - t0) / dur);
    elm.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
    if (p < 1) requestAnimationFrame(frame);
  })(t0);
}

function renderResults(list, plan) {
  el('intro').hidden = true;
  el('dhead').hidden = false;
  el('copyall').hidden = !list.length;
  el('dcount').textContent = list.length ? `${list.length} CLAIM${list.length > 1 ? 'S' : ''} RECOVERED · ${plan.headline.toUpperCase()}` : '';
  el('results').innerHTML = list.length
    ? list.map((it, i) => entryHTML(it, i)).join('')
    : `<div class="empty">THE SIEVE CAME BACK EMPTY — no claims matched “${esc(plan.subline)}”. Loosen the query, drop the star floor, or take the complaint to Painpoint.</div>`;
  requestAnimationFrame(() => qq('#results .ticks').forEach(t => t.classList.add('go')));
  list.forEach((it, i) => countUp(el('fitn-' + i), it.fit));
  if (list.length && !list[0].r.ledger) loadReadmeForPick(list[0].r.full_name);
  el('dhead').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function loadReadmeForPick(full) {
  const box = el('pickreadme');
  if (!box) return;
  box.hidden = false;
  box.textContent = '↳ pulling the field note — first lines of the README…';
  const text = await fetchReadme(full, { signal: runAbort && runAbort.signal, state: S });
  renderBudget();
  if (!box.isConnected) return;
  if (text) box.textContent = text;
  else box.hidden = true;
}

function renderAdjacent(plan) {
  const ids = (plan.adjacent || []).filter(Boolean).slice(0, 6);
  const box = el('adjchips');
  box.innerHTML = ids.map(id => {
    const p = PAINS.find(item => item.id === id);
    return p ? `<button class="adjch" data-say="${esc(p.say)}" type="button">→ ${esc(p.dx)}</button>` : '';
  }).join('');
  el('adj').classList.toggle('on', !!box.innerHTML.trim());
}

function showNotice(text) {
  const n = el('notice');
  if (!text) { n.hidden = true; n.textContent = ''; return; }
  n.hidden = false;
  n.textContent = text;
}

function setRunState(on) {
  qq('.run').forEach(b => { b.disabled = on; b.textContent = on ? 'ASSAY RUNNING…' : b.dataset.label; });
}

async function run() {
  let plan;
  if (S.mode === 'survey') {
    const q = el('qin').value.trim();
    if (!q) { toast('Type a query first — or take a complaint to Painpoint.'); return; }
    plan = planSurvey(q, { sort: S.sort, minStars: S.minStars });
  } else if (S.mode === 'context') {
    const txt = el('ctx').value.trim();
    const sigs = activeSignals();
    if (!txt) { toast('Paste notes for ideation first — or load the sample.'); return; }
    if (!sigs.length) { toast('No signals recognized — paste more notes, or use Search.'); return; }
    plan = planContext(sigs);
  } else {
    const txt = el('ptxt').value.trim();
    if (!txt) { toast('Describe what hurts first.'); return; }
    plan = planPain(txt);
  }

  if (runAbort) runAbort.abort();
  const ac = new AbortController();
  runAbort = ac;
  const gen = ++runGen;

  S.running = true;
  setRunState(true);
  resetLog();
  resetRuler(plan.queries.length + 2);
  el('intro').hidden = true;
  el('dhead').hidden = false;
  showNotice('');
  el('adj').classList.remove('on');
  el('results').innerHTML = '<div class="empty">PANNING THE STREAM — the assay log narrates the run.</div>';
  S.results = [];
  S.plan = plan;

  log(`input read — ${plan.mode === 'survey' ? el('qin').value.trim().length : (S.mode === 'context' ? el('ctx').value.length : el('ptxt').value.length)} characters`);
  if (plan.ctx.signals.length) log(`signals detected: ${plan.ctx.signals.map(s => s.l).join(', ')}`);
  if (plan.ctx.pain) log(`diagnosis: ${plan.ctx.pain.dx} — mapping to ${plan.queries.length} searches`);

  let rateLimited = false;
  let netDown = false;
  let resetAt = null;
  let invalidMsg = '';
  const items = [];
  const seen = new Set();

  try {
    for (let i = 0; i < plan.queries.length; i++) {
      if (ac.signal.aborted || gen !== runGen) return;
      const Q = plan.queries[i];
      log(`search ${i + 1}/${plan.queries.length} — “${Q.q}”${Q.sort && Q.sort !== 'best' ? ' (sort: ' + Q.sort + ')' : ''}`);
      try {
        const res = await ghSearch(Q.q, { sort: Q.sort, per: Q.per, signal: ac.signal, state: S });
        if (ac.signal.aborted || gen !== runGen) return;
        renderBudget();
        log(`${res.length} claims recovered`, true);
        res.forEach(r => { if (!seen.has(r.full_name)) { seen.add(r.full_name); items.push(r); } });
        stepRuler();
      } catch (err) {
        if (err.name === 'AbortError' || ac.signal.aborted || gen !== runGen) return;
        if (err.invalid) {
          invalidMsg = err.message || 'GitHub rejected the query';
          log(invalidMsg, true);
          break;
        }
        if (err.rate) {
          resetAt = err.reset;
          rateLimited = true;
          log(items.length ? 'rate budget spent — keeping claims already recovered' : 'rate budget spent — switching to the offline ledger', true);
          break;
        }
        netDown = true;
        log(err.message && err.message !== 'the wire is down' ? err.message : 'the wire is down', true);
        break;
      }
    }

    if (ac.signal.aborted || gen !== runGen) return;

    let settled;
    if (!items.length && invalidMsg && !rateLimited && !netDown) {
      settled = { source: 'invalid', list: [] };
    } else {
      settled = settleClaims(items, plan, { rateLimited, netDown });
    }

    if (settled.source === 'ledger') {
      log(`ledger scoured — ${settled.list.length} entries pulled from the field ledger`);
      for (let i = 0; i < 3; i++) stepRuler();
    } else if (settled.source === 'invalid') {
      log(invalidMsg);
      stepRuler();
      stepRuler();
    } else {
      log(`merging ${items.length} claims — assaying fit (stars, freshness, overlap)`);
      stepRuler();
      log(`${settled.list.length} claims survive the sieve${settled.list.length ? ' — richest: ' + settled.list[0].r.full_name : ''}`);
      stepRuler();
    }

    if (settled.source === 'invalid') {
      el('intro').hidden = true;
      el('dhead').hidden = false;
      el('copyall').hidden = true;
      el('dcount').textContent = '';
      el('results').innerHTML = `<div class="empty">${esc(invalidMsg)}</div>`;
    } else {
      renderResults(settled.list, plan);
    }
    renderAdjacent(plan);

    if (settled.source === 'ledger') {
      const mins = resetAt ? Math.max(1, Math.round((resetAt * 1000 - Date.now()) / 60000)) : null;
      showNotice(`LIVE SEARCH BUDGET SPENT${mins ? ' — resets in ~' + mins + ' min' : ''}. Serving the offline field ledger: a curated set with approximate counts. Every other instrument — scoring, briefing export, adjacent digs — works exactly as usual.`);
    } else if (settled.source === 'partial') {
      const why = rateLimited ? 'LIVE SEARCH BUDGET SPENT' : 'THE WIRE DROPPED MID-SURVEY';
      const mins = resetAt ? Math.max(1, Math.round((resetAt * 1000 - Date.now()) / 60000)) : null;
      showNotice(`${why}${mins ? ' — resets in ~' + mins + ' min' : ''}. Showing ${settled.list.length} claim${settled.list.length === 1 ? '' : 's'} already recovered.`);
    } else if (invalidMsg && settled.list.length) {
      showNotice(invalidMsg);
    }

    S.results = settled.list;
  } finally {
    if (gen === runGen) {
      S.running = false;
      setRunState(false);
    }
  }
}

function copyText(t, msg) {
  const done = () => toast(msg);
  const fallback = () => {
    const ta = document.createElement('textarea');
    ta.value = t;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); done(); } catch (err) { toast('Copy failed — select it manually.'); }
    ta.remove();
  };
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(t).then(done, fallback);
  else fallback();
}

function repoBlock(it, n) {
  const r = it.r;
  return `${n ? n + '. ' : ''}${r.full_name} (${fmtStars(r.stargazers_count)} stars, ${r.language || '—'}, updated ${ago(r.pushed_at)})\n  ${r.description || ''}\n  ${r.html_url}\n  Fit ${it.fit}/100 — ${it.why}`;
}

function copyRepo(i) {
  const it = S.results[i];
  if (!it) return;
  copyText(repoBlock(it), 'Copied — paste into your Cursor chat or rules file.');
}

function copyBriefing() {
  if (!S.results.length || !S.plan) return;
  const head = `## Repo prospects — ${S.plan.headline}\n${S.plan.subline}\nFit is a local score (stars, freshness, signal/term overlap). Panned ${new Date().toDateString()}.\n\n`;
  copyText(head + S.results.map((it, i) => repoBlock(it, i + 1)).join('\n\n'), `Briefing copied — ${S.results.length} claims, ready for your agent.`);
}

let toastT;
function toast(msg) {
  const t = el('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastT);
  toastT = setTimeout(() => t.classList.remove('show'), 2600);
}

document.addEventListener('click', e => {
  const b = e.target.closest('button');
  if (!b) return;
  if (b.classList.contains('mode')) { setMode(b.dataset.mode); return; }
  if (b.classList.contains('run')) { run(); return; }
  if (b.dataset.g) {
    qq(`[data-g="${b.dataset.g}"]`).forEach(x => x.classList.toggle('on', x === b));
    if (b.dataset.g === 'sort') S.sort = b.dataset.v;
    else S.minStars = +b.dataset.v;
    updatePreview();
    return;
  }
  if (b.classList.contains('sig')) {
    const k = b.dataset.k;
    S.excl.has(k) ? S.excl.delete(k) : S.excl.add(k);
    renderSignals();
    return;
  }
  if (b.classList.contains('adjch') || b.classList.contains('exch')) {
    setMode('pain');
    el('ptxt').value = b.dataset.say;
    el('ptxt').dispatchEvent(new Event('input', { bubbles: true }));
    run();
    return;
  }
  if (b.id === 'loadsample') {
    el('ctx').value = SAMPLE;
    el('ctx').dispatchEvent(new Event('input', { bubbles: true }));
    toast('Sample loaded — watch the signal panel.');
    return;
  }
  if (b.classList.contains('copy1')) { copyRepo(+b.dataset.i); return; }
  if (b.id === 'copyall') { copyBriefing(); return; }
  if (b.id === 'speccopy') {
    copyText('BurntSushi/ripgrep (47.6k stars, Rust)\n  ripgrep recursively searches directories for a regex pattern while respecting your gitignore\n  https://github.com/BurntSushi/ripgrep\n', 'Copied — a taste of the briefing format.');
  }
});

document.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); run(); return; }
  const typing = /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName);
  if (typing) return;
  if (e.key === '1') setMode('survey');
  if (e.key === '2') setMode('context');
  if (e.key === '3') setMode('pain');
  if (e.key === '/') {
    e.preventDefault();
    (S.mode === 'survey' ? el('qin') : S.mode === 'context' ? el('ctx') : el('ptxt')).focus();
  }
});

el('ctx').addEventListener('input', renderSignals);

const drop = el('ctxdrop');
['dragover', 'dragenter'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('drag'); }));
['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('drag'); }));
drop.addEventListener('drop', e => {
  const f = e.dataTransfer.files && e.dataTransfer.files[0];
  if (!f) return;
  f.text().then(t => {
    el('ctx').value = t.slice(0, 20000);
    el('ctx').dispatchEvent(new Event('input', { bubbles: true }));
    toast('Loaded ' + f.name + ' — signals panned below.');
  });
});

setMode('survey');
updatePreview();
renderSignals();
const incomingQuery = new URLSearchParams(location.search).get('q');
if (incomingQuery) {
  el('qin').value = incomingQuery.slice(0, 256);
  updatePreview();
  run();
} else {
  el('qin').focus();
}
