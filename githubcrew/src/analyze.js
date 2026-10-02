import {
  AI_HIGH, AI_PROHIBITED, AI_SIGNALS, DAYS, KNOWN, SEC_WF, SENSITIVE, STACKMAP,
} from './data.js';

export class GHError extends Error {
  constructor(kind) {
    super(kind);
    this.kind = kind;
  }
}

export function parseRepo(raw) {
  let s = (raw || '').trim();
  if (/^https?:\/\//i.test(s)) {
    try {
      const u = new URL(s);
      if (u.hostname !== 'github.com' && u.hostname !== 'www.github.com') return null;
      s = u.pathname;
    } catch {
      return null;
    }
  } else {
    s = s.replace(/^(www\.)?github\.com\//i, '');
  }
  s = s.replace(/^\/|\/$/g, '').replace(/\.git$/i, '');
  const m = s.match(/^([a-z0-9](?:[a-z0-9-]{0,38}))\/([a-z0-9_.-]+)$/i);
  return m && !['.', '..'].includes(m[2]) ? `${m[1]}/${m[2]}` : null;
}

const trunc = (s, n) => (s.length > n ? `${s.slice(0, n - 1).trimEnd()}…` : s);
const fmtN = (n) => {
  n = Number(n) || 0;
  return n >= 1000 ? `${(n / 1000).toFixed(1).replace(/\.0$/, '')}k` : String(n);
};
const fmtDate = (iso) => new Date(iso).toISOString().slice(0, 10);
const daysSince = (iso) => (Date.now() - +new Date(iso)) / 864e5;

function rel(x) {
  const t = typeof x === 'number' ? x : +new Date(x);
  const s = (Date.now() - t) / 1000;
  if (s < 0) return 'just now';
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  const d = s / 86400;
  if (d < 60) return `${Math.round(d)}d ago`;
  if (d < 730) return `${Math.round(d / 30)}mo ago`;
  return `${Math.round(d / 365)}y ago`;
}

const median = (a) => {
  if (!a.length) return 0;
  const s = [...a].sort((x, y) => x - y);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : Math.round((s[m - 1] + s[m]) / 2);
};

const matchPat = (name, pat) => (
  pat.startsWith('*.')
    ? name.toLowerCase().endsWith(pat.slice(1).toLowerCase())
    : name.toLowerCase() === pat.toLowerCase()
);

async function agentScout(P, fresh, io) {
  io.current('scout');
  io.setAgent('scout', 'working');
  const A = 'scout';
  io.say(A, `Target locked — running reconnaissance on ${P.repo}…`);
  if (fresh) {
    const rl = await io.gh('/rate_limit');
    P.quota = rl.resources.core.remaining;
    P.quotaMax = rl.resources.core.limit;
    io.setQuota(`${P.quota}/${P.quotaMax}`);
    io.say(A, `API quota healthy — ${P.quota} of ${P.quotaMax} calls remaining this hour.`, 'ok');
    if (P.quota < 12) throw new GHError('quota');
    P.meta = await io.gh(`/repos/${P.repo}`);
  } else {
    io.say(A, 'Replaying recorded intelligence from this session’s cache.', 'tool');
  }
  const m = P.meta;
  io.say(A, `Target acquired — “${m.name}” by ${m.owner.login}.`, 'ok');
  io.say(A, `▸ ${fmtN(m.stargazers_count)} stars · ${fmtN(m.forks_count)} forks · ${fmtN(m.open_issues_count)} open issues & pulls`);
  io.say(A, `▸ created ${fmtDate(m.created_at)} (${rel(m.created_at)} old) · last push ${rel(m.pushed_at)}`);
  io.say(A, `▸ declared language: ${m.language || 'none'} · license: ${m.license ? m.license.spdx_id : 'none detected'} · branch: ${m.default_branch}`);
  if (m.description) io.say(A, `▸ field notes: “${trunc(m.description, 110)}”`);
  io.say(A, 'Reconnaissance complete. Handing off to CARTOGRAPHER.');
  io.setAgent('scout', 'done');
}

async function agentCartographer(P, fresh, io) {
  io.current('cartographer');
  io.setAgent('cartographer', 'working');
  const A = 'cartographer';
  io.say(A, `Surveying the structure of ${P.repo}…`);
  if (fresh) {
    P.langs = await io.gh(`/repos/${P.repo}/languages`);
    P.root = (await io.gh(`/repos/${P.repo}/contents`, { empty409: true, soft: true })) || [];
    const wf = await io.gh(`/repos/${P.repo}/contents/.github/workflows`, { soft: true });
    P.wf = wf ? wf.filter((f) => /\.ya?ml$/i.test(f.name)).map((f) => f.name) : [];
  }
  const langs = P.langList = Object.entries(P.langs || {}).sort((a, b) => b[1] - a[1]);
  const total = langs.reduce((s, [, b]) => s + b, 0);
  if (langs.length) {
    io.say(A, `▸ byte census: ${langs.slice(0, 4).map(([n, b]) => `${n} ${(b / total * 100).toFixed(1)}%`).join(' · ')}${langs.length > 4 ? ' · …' : ''}`);
  } else {
    io.say(A, '▸ byte census: no language data — the repository tree is empty.', 'warn');
  }
  const entries = P.root || [];
  io.say(A, `▸ root census: ${entries.filter((e) => e.type === 'file').length} files · ${entries.filter((e) => e.type === 'dir').length} directories at the surface`);
  const found = [];
  for (const [pat, label] of STACKMAP) {
    const hit = entries.find((e) => matchPat(e.name, pat));
    if (hit) found.push([hit.name, label]);
  }
  P.docker = found.some((f) => /docker/i.test(f[1]) && f[0].toLowerCase().startsWith('dockerfile'));
  P.compose = entries.some((e) => /^docker-compose\.yml$/i.test(e.name));
  found.slice(0, 5).forEach(([n, l]) => io.say(A, `artifact identified: ${n} — ${l} detected`, 'ok'));
  if (found.length > 5) io.say(A, `▸ …and ${found.length - 5} further artifacts logged`);
  P.ci = (P.wf || []).length > 0;
  if (P.ci) io.say(A, `CI pipeline live — ${P.wf.length} workflow${P.wf.length > 1 ? 's' : ''}: ${P.wf.slice(0, 3).join(', ')}${P.wf.length > 3 ? '…' : ''}`, 'ok');
  else io.say(A, 'no CI workflows found under .github/workflows', 'warn');
  const testDir = /^(tests?|specs?|__tests__|e2e|unit)$/i;
  const testFile = /^(jest|vitest|karma|pytest|tox|cypress|playwright|noxfile)|\.(test|spec)\./i;
  const testHit = entries.find((e) => (e.type === 'dir' ? testDir.test(e.name) : testFile.test(e.name)));
  P.tests = !!testHit;
  if (P.tests) io.say(A, `test suite detected: ${testHit.name}`, 'ok');
  else io.say(A, 'no test suite detected at the surface', 'warn');
  io.say(A, `Stack manifest compiled — ${langs.slice(0, 3).map((l) => l[0]).join(' / ') || 'unknown'}. Handing off to PULSE.`);
  io.setAgent('cartographer', 'done');
}

async function agentPulse(P, fresh, io) {
  io.current('pulse');
  io.setAgent('pulse', 'working');
  const A = 'pulse';
  io.say(A, `Listening for ${P.repo}'s heartbeat…`);
  if (fresh) {
    P.commits = await io.gh(`/repos/${P.repo}/commits?per_page=100&sha=${encodeURIComponent(P.meta.default_branch)}`, { empty409: true });
    P.contribs = await io.gh(`/repos/${P.repo}/contributors?per_page=100`);
  }
  const cs = P.commits || [];
  P.sampled = cs.length;
  if (!cs.length) {
    io.say(A, 'no commits found — the repository has no heartbeat yet.', 'warn');
    io.setAgent('pulse', 'done');
    return;
  }
  const times = cs.map((c) => +new Date(c.commit.author.date)).sort((a, b) => a - b);
  const newest = times[times.length - 1];
  const spanDays = Math.max(1, (newest - times[0]) / 864e5);
  P.perWeek = cs.length / (spanDays / 7);
  const wd = new Array(7).fill(0);
  const tax = {};
  const lens = [];
  cs.forEach((c) => {
    const d = new Date(c.commit.author.date);
    wd[d.getUTCDay()] += 1;
    lens.push(c.commit.message.length);
    const mm = c.commit.message.match(/^(\w+)(?:\(|:)/);
    if (mm && KNOWN.has(mm[1].toLowerCase())) tax[mm[1].toLowerCase()] = (tax[mm[1].toLowerCase()] || 0) + 1;
  });
  const wdMax = wd.indexOf(Math.max(...wd));
  P.busiest = { day: DAYS[wdMax], n: wd[wdMax], pct: Math.round(wd[wdMax] / cs.length * 100) };
  P.tax = tax;
  P.medianLen = median(lens);
  const longest = cs.reduce((a, c) => (c.commit.message.length > a.commit.message.length ? c : a), cs[0]);
  P.longest = {
    msg: trunc(longest.commit.message.replace(/\s+/g, ' '), 46),
    by: (longest.author && longest.author.login) || longest.commit.author.name,
  };
  const now = Date.now();
  P.buckets = new Array(12).fill(0);
  cs.forEach((c) => {
    const w = Math.floor((now - +new Date(c.commit.author.date)) / 6048e5);
    if (w >= 0 && w < 12) P.buckets[11 - w] += 1;
  });
  io.say(A, `▸ sampled last ${cs.length} commits on “${P.meta.default_branch}” — latest ${rel(newest)}`);
  io.say(A, `▸ cadence ≈ ${P.perWeek.toFixed(1)} commits/week across the sample window`);
  io.say(A, `▸ busiest day: ${P.busiest.day} — ${P.busiest.n} commits (${P.busiest.pct}% of sample)`);
  const tk = Object.entries(P.tax).sort((a, b) => b[1] - a[1]);
  if (tk.length) {
    io.say(A, `▸ commit taxonomy: ${tk.slice(0, 4).map(([k, v]) => `${k} ${v}`).join(' · ')} · other ${cs.length - tk.reduce((s, [, v]) => s + v, 0)}`);
  } else {
    io.say(A, '▸ commit taxonomy: conventional prefixes not detected');
  }
  io.say(A, `▸ median message ${P.medianLen} chars · longest: “${P.longest.msg}” — ${P.longest.by}`);
  const ct = P.contribs || [];
  P.contribTotal = ct.length;
  P.top = ct.slice(0, 5);
  if (ct.length) {
    io.say(A, `▸ ${ct.length}${ct.length === 100 ? '+' : ''} contributors on record — heaviest lifters: ${ct.slice(0, 3).map((c) => c.login).join(', ')}`);
  }
  P.strength = P.perWeek >= 10 ? 'STRONG' : P.perWeek >= 3 ? 'STEADY' : P.perWeek >= 1 ? 'SLOW' : 'FAINT';
  io.say(A, `Heartbeat reads ${P.strength}. Handing off to ARCHIVIST.`);
  io.setAgent('pulse', 'done');
}

async function agentArchivist(P, fresh, io) {
  io.current('archivist');
  io.setAgent('archivist', 'working');
  const A = 'archivist';
  io.say(A, 'Auditing the paperwork…');
  const rootNames = (P.root || []).map((e) => e.name.toLowerCase());
  const has = (pre) => rootNames.some((n) => n.startsWith(pre));
  P.aux = { license: has('license'), contributing: has('contributing'), coc: has('code_of_conduct'), security: has('security') };
  if (fresh) P.readme = await io.gh(`/repos/${P.repo}/readme`, { soft: true, raw: true });
  if (!P.readme) {
    io.say(A, 'no README found at the repository root — the dossier has no cover page.', 'warn');
    P.docScore = 0;
    P.docGaps = ['everything'];
    P.docChecks = [];
    P.docCovered = [];
    io.say(A, 'Documentation audit closed. Handing off to GUARD.');
    io.setAgent('archivist', 'done');
    return;
  }
  const t = P.readme;
  const tl = t.toLowerCase();
  const kb = (t.length / 1024).toFixed(1);
  const words = t.split(/\s+/).filter(Boolean).length;
  const heads = (t.match(/^#{1,6}\s.*$/gm) || []).length;
  P.readmeStats = { kb, words, heads };
  const CH = [
    ['Installation', 14, /#{1,6}[^\n]*(install|set ?up|setup)|getting ?started/i],
    ['Usage', 14, /#{1,6}[^\n]*(usage|quick ?start|getting ?started)|##\s*use/i],
    ['Contributing', 10, /contribut/],
    ['License', 10, /#{1,6}[^\n]*licen[cs]e|licen[cs]e$/im],
    ['Tests', 8, /#{1,6}[^\n]*test|running tests/i],
    ['Examples', 8, /#{1,6}[^\n]*(example|demo|screenshot)/i],
    ['Badges', 6, /shields\.io|badge/i],
    ['Table of contents', 5, /table of contents|^- \[[^\]]+\]\(#/im],
    ['Docs links', 5, /documentation|docs\/|readthedocs/i],
  ];
  P.docChecks = [];
  let score = 20;
  CH.forEach(([label, w, re]) => {
    const ok = re.test(tl);
    P.docChecks.push([label, ok]);
    if (ok) score += w;
  });
  P.docScore = Math.min(100, score);
  P.docCovered = P.docChecks.filter((c) => c[1]).map((c) => c[0]);
  P.docGaps = P.docChecks.filter((c) => !c[1]).map((c) => c[0]);
  io.say(A, `▸ README: ${kb} KB · ${fmtN(words)} words · ${heads} section headings`);
  if (P.docCovered.length) io.say(A, `sections verified: ${P.docCovered.join(' · ')}`, 'ok');
  if (P.docGaps.length) io.say(A, `sections missing: ${P.docGaps.join(' · ')}`, 'warn');
  const au = P.aux;
  io.say(A, `▸ auxiliary docs: LICENSE ${au.license ? '✓' : '✗'} · CONTRIBUTING ${au.contributing ? '✓' : '✗'} · CODE_OF_CONDUCT ${au.coc ? '✓' : '✗'} · SECURITY ${au.security ? '✓' : '✗'}`);
  io.say(A, `Documentation audit closed at ${P.docScore}/100. Handing off to GUARD.`);
  io.setAgent('archivist', 'done');
}

async function agentGuard(P, fresh, io) {
  io.current('guard');
  io.setAgent('guard', 'working');
  const A = 'guard';
  io.say(A, 'Running security & compliance mapping — NIST RMF × EU AI Act…');
  if (fresh) {
    P.ghDot = (await io.gh(`/repos/${P.repo}/contents/.github`, { soft: true })) || [];
    const lr = await io.gh(`/repos/${P.repo}/releases/latest`, { soft: true });
    P.release = lr ? { tag: lr.tag_name || lr.name, at: lr.published_at } : null;
  }
  const rootN = (P.root || []).map((e) => e.name.toLowerCase());
  const dotN = (P.ghDot || []).map((e) => e.name.toLowerCase());
  const has = (list, pre) => list.some((n) => n.startsWith(pre));
  const secMd = has(rootN, 'security') || has(dotN, 'security');
  const depbot = dotN.includes('dependabot.yml') || dotN.includes('dependabot.yaml');
  const codeown = has(rootN, 'codeown') || has(dotN, 'codeown');
  const wf = P.wf || [];
  const secWf = wf.filter((n) => SEC_WF.test(n));
  P.secCtl = { secMd, depbot, codeown, secWf };

  const m = P.meta;
  const scanText = [m.description, (m.topics || []).join(' '), P.readme ? P.readme.slice(0, 6000) : ''].join('\n').toLowerCase();
  const sensRaw = SENSITIVE.filter((k) => scanText.includes(k));
  const sens = sensRaw.filter((k) => !sensRaw.some((o) => o !== k && o.includes(k)));
  P.secSens = sens;

  const pushDays = daysSince(m.pushed_at);
  const mk = (step, st, ev) => ({ step, st, ev });
  const steps = [];
  const prepOk = !!P.readme && !!m.description;
  steps.push(mk('PREPARE', prepOk ? 'ok' : (P.readme || m.description) ? 'warn' : 'gap',
    prepOk ? 'README and repository description establish scope and ownership.'
      : (P.readme || m.description) ? `Partial context — ${P.readme ? 'description missing' : 'README missing'}.`
        : 'No README or description — purpose undocumented.'));
  steps.push(mk('CATEGORIZE', sens.length >= 3 ? 'warn' : 'ok',
    sens.length ? `Indicators detected (${sens.length}): ${sens.slice(0, 4).join(', ')} — formal impact categorization recommended.`
      : 'No sensitive-data indicators — LOW impact candidate.'));
  const selN = [secMd, depbot].filter(Boolean).length;
  steps.push(mk('SELECT', selN === 2 ? 'ok' : selN === 1 ? 'warn' : 'gap',
    `Vulnerability disclosure ${secMd ? '✓' : '✗'} · dependency monitoring ${depbot ? '✓' : '✗'}.`));
  const implN = [P.ci, P.tests, codeown, depbot].filter(Boolean).length;
  steps.push(mk('IMPLEMENT', implN >= 3 ? 'ok' : implN >= 1 ? 'warn' : 'gap',
    `CI ${P.ci ? '✓' : '✗'} · tests ${P.tests ? '✓' : '✗'} · CODEOWNERS ${codeown ? '✓' : '✗'} · dependabot ${depbot ? '✓' : '✗'} — ${implN}/4 safeguards in place.`));
  steps.push(mk('ASSESS', secWf.length ? 'ok' : P.ci ? 'warn' : 'gap',
    secWf.length ? `Security scanning in CI: ${secWf.slice(0, 2).join(', ')}.`
      : P.ci ? 'CI present but no security-scanning workflow detected.'
        : 'No CI — no automated assessment evidence.'));
  const authN = [P.release, m.license].filter(Boolean).length;
  steps.push(mk('AUTHORIZE', authN === 2 ? 'ok' : authN === 1 ? 'warn' : 'gap',
    `${P.release ? `Latest release ${P.release.tag} (${rel(P.release.at)}). ` : 'No published releases. '}${m.license ? `License ${m.license.spdx_id} on record.` : 'No license on record.'}`));
  steps.push(mk('MONITOR', (pushDays <= 30 && (P.ci || depbot)) ? 'ok' : pushDays <= 180 ? 'warn' : 'gap',
    `Last push ${rel(m.pushed_at)} · ${P.contribTotal || 0} contributors · ${fmtN(m.open_issues_count)} open items.`));
  const val = { ok: 100, warn: 50, gap: 0 };
  const rmfScore = Math.round(steps.reduce((s, r) => s + val[r.st], 0) / steps.length);
  const nOk = steps.filter((r) => r.st === 'ok').length;
  const nW = steps.filter((r) => r.st === 'warn').length;
  const nG = steps.filter((r) => r.st === 'gap').length;
  P.rmf = { steps, score: rmfScore, ok: nOk, warn: nW, gap: nG };

  const aiHits = AI_SIGNALS.filter((k) => scanText.includes(k));
  const proh = AI_PROHIBITED.filter((k) => scanText.includes(k));
  const high = AI_HIGH.filter((k) => scanText.includes(k));
  let tier;
  if (proh.length) {
    tier = { key: 'prohibited', word: 'PROHIBITED-PRACTICE RISK', arts: 'ART. 5', cls: 'bad', note: 'Indicators match practices prohibited under the EU AI Act. Independent legal review is required before any deployment.', obl: ['Cease deployment pending legal review', 'Document screening evidence'] };
  } else if (aiHits.length && high.length) {
    tier = { key: 'high', word: 'HIGH-RISK INDICATORS', arts: 'ANNEX III', cls: 'bad', note: 'AI-system signals overlap with Annex III high-risk domains. Conformity assessment, technical documentation and human oversight (Art. 9–15) likely apply.', obl: ['Conformity assessment', 'Technical documentation (Art. 11)', 'Human oversight (Art. 14)', 'Post-market monitoring'] };
  } else if (aiHits.length) {
    tier = { key: 'limited', word: 'LIMITED RISK', arts: 'ART. 13 · 50', cls: 'warn', note: 'AI-system indicators present. Transparency obligations apply: disclose AI interaction and provide machine-readable marking of synthetic content.', obl: ['AI-interaction disclosure (Art. 50)', 'Machine-readable marking', 'Intended-purpose documentation'] };
  } else if (high.length) {
    tier = { key: 'domain', word: 'DOMAIN-SENSITIVE', arts: 'ANNEX III — VERIFY', cls: 'warn', note: 'Sensitive-domain keywords without clear AI-system signals. Verify whether the Annex III high-risk classification applies to the deployed system.', obl: ['Scope verification', 'Document intended use'] };
  } else {
    tier = { key: 'minimal', word: 'MINIMAL RISK', arts: 'OUT OF SCOPE', cls: 'ok', note: 'No AI-system indicators detected — treated as general-purpose software. Standard software obligations only.', obl: ['None beyond standard software duties'] };
  }
  P.ai = { tier, hits: aiHits, high, proh };
  const factor = { prohibited: 0.4, high: 0.7, domain: 0.85, limited: 0.9, minimal: 1 }[tier.key];
  P.secScore = Math.round(rmfScore * factor);

  io.say(A, `▸ control sweep: SECURITY.md ${secMd ? '✓' : '✗'} · dependabot ${depbot ? '✓' : '✗'} · CODEOWNERS ${codeown ? '✓' : '✗'} · security CI ${secWf.length ? '✓' : '✗'}`, (secMd || depbot) ? 'ok' : 'warn');
  io.say(A, sens.length ? `▸ sensitive-data indicators (${sens.length}): ${sens.slice(0, 5).join(', ')}` : '▸ sensitive-data indicators: none detected', sens.length ? 'warn' : 'ok');
  io.say(A, `▸ NIST RMF mapping: ${nOk} satisfied · ${nW} partial · ${nG} gaps — readiness ${rmfScore}/100`);
  io.say(A, `▸ EU AI Act screening: ${aiHits.length} AI-system signal(s), ${high.length} domain indicator(s), ${proh.length} prohibited-practice hit(s)`);
  io.say(A, `▸ tier hypothesis: ${tier.word} — ${tier.arts}`, tier.cls === 'ok' ? 'ok' : 'warn');
  io.say(A, 'Compliance mapping complete. Handing off to WARDEN.');
  io.setAgent('guard', 'done');
}

export function buildDossier(P) {
  const m = P.meta;
  const langs = P.langList || [];
  const daysPush = daysSince(m.pushed_at);
  const recency = daysPush <= 7 ? 100 : daysPush <= 30 ? 85 : daysPush <= 90 ? 60 : daysPush <= 180 ? 35 : daysPush <= 365 ? 15 : 5;
  const volume = Math.min(100, ((P.perWeek || 0) / 8) * 100);
  const activity = Math.round(recency * 0.6 + volume * 0.4);
  const docs = P.readme
    ? P.docScore
    : Math.min(45, 5 + (P.aux.license ? 15 : 0) + (P.aux.contributing ? 15 : 0) + (P.aux.coc ? 10 : 0) + (P.aux.security ? 10 : 0));
  const cN = P.contribTotal || 0;
  const sC = Math.min(100, Math.log2(cN + 1) / Math.log2(201) * 100);
  const sS = Math.min(100, Math.log10((m.stargazers_count || 0) + 1) / Math.log10(10001) * 100);
  const community = Math.round(Math.min(100, sC * 0.5 + sS * 0.35 + (P.aux.contributing ? 15 : 0)));
  const eng = Math.round(Math.min(100, (P.ci ? 30 : 0) + (P.tests ? 25 : 0) + (P.docker ? 12 : 0) + (P.aux.license ? 18 : 0) + (P.compose ? 5 : 0) + (langs.length >= 3 ? 5 : 0) + (P.readme ? 5 : 0)));
  const compliance = P.secScore;
  const score = Math.round(activity * 0.25 + docs * 0.20 + community * 0.15 + eng * 0.20 + compliance * 0.20);
  const tier = score >= 80 ? { word: 'CLEARED', cls: '', note: 'fit for duty' }
    : score >= 60 ? { word: 'SOUND', cls: '', note: 'minor wear noted' }
      : score >= 40 ? { word: 'FLAGGED', cls: 'warn', note: 'needs attention' }
        : { word: 'CRITICAL', cls: 'bad', note: 'high risk — proceed with care' };
  const scores = { activity, docs: Math.round(docs), community, eng, compliance };
  const recs = [];
  if (!P.readme) recs.push('Publish a README — document what this is, how to install it, and how to run it.');
  if (!P.aux.license) recs.push('Add a LICENSE file — without one, default copyright applies and reuse is legally ambiguous.');
  if (!P.ci) recs.push('Stand up CI under .github/workflows so every push is verified automatically.');
  if (!P.tests) recs.push('Introduce a test suite — none was detected (tests/ directory or test config).');
  if (!P.secCtl.secMd) recs.push('Add a SECURITY.md with a vulnerability-disclosure policy (NIST RMF: SELECT).');
  if (!P.secCtl.depbot) recs.push('Enable Dependabot via .github/dependabot.yml to keep dependencies continuously patched.');
  if (!P.secCtl.secWf.length && P.ci) recs.push('Add security scanning to CI (CodeQL, Semgrep or Trivy) — the RMF ASSESS step currently has no automated evidence.');
  if (!P.secCtl.codeown) recs.push('Add a CODEOWNERS file so security-relevant changes receive qualified review.');
  if (P.ai.tier.key === 'high' || P.ai.tier.key === 'prohibited') {
    recs.push(`EU AI Act: run a conformity assessment and prepare technical documentation before any EU deployment (${P.ai.tier.arts.toLowerCase()}).`);
  } else if (P.ai.tier.key === 'limited') {
    recs.push('EU AI Act Art. 50: add a clear AI-interaction disclosure to the product surface and README.');
  }
  if (P.readme && P.docGaps.length && P.docScore < 75) {
    recs.push(`Extend the README with ${P.docGaps.slice(0, 3).join(', ').toLowerCase()} to lift documentation beyond ${Math.round(docs)}/100.`);
  }
  if (daysPush > 180) recs.push(`Last push was ${rel(m.pushed_at)} — if the project lives on, a maintenance-status note would help evaluators.`);

  const signals = [
    ['scout', `Public since ${fmtDate(m.created_at)} — ${fmtN(m.stargazers_count)} stars, ${fmtN(m.forks_count)} forks, ${fmtN(m.open_issues_count)} open items.`],
    ['cartographer', `${langs.length ? `${langs[0][0]} leads a ${langs.length}-language stack` : 'Stack census unavailable'} · CI ${P.ci ? 'live' : 'absent'} · tests ${P.tests ? 'detected' : 'not detected'}${P.docker ? ' · containerized' : ''}.`],
    ['pulse', P.sampled ? `≈${P.perWeek.toFixed(1)} commits/week across the last ${P.sampled}; heartbeat ${P.strength.toLowerCase()}; last push ${rel(m.pushed_at)}.` : 'No commit history to measure.'],
    ['archivist', P.readme ? `README runs ${fmtN(P.readmeStats.words)} words — ${P.docCovered.length}/${P.docChecks.length} core sections verified.` : 'No README — the repository documents itself nowhere.'],
    ['guard', `NIST RMF readiness ${P.rmf.score}/100 (${P.rmf.ok} satisfied · ${P.rmf.warn} partial · ${P.rmf.gap} gaps) · EU AI Act screening: ${P.ai.tier.word.toLowerCase()} (${P.ai.tier.arts}).`],
    ['warden', `Composite health ${score}/100 — ${tier.word.toLowerCase()}: ${tier.note}.`],
  ];
  return {
    repo: P.repo,
    name: m.name,
    owner: m.owner.login,
    score,
    tier,
    scores,
    recs: recs.slice(0, 6),
    signals,
    rmf: P.rmf,
    ai: P.ai,
    fileNo: `GCRW-${Math.floor(1000 + Math.random() * 9000)}`,
  };
}

async function agentWarden(P, io) {
  io.current('warden');
  io.setAgent('warden', 'working');
  const A = 'warden';
  io.say(A, 'Synthesizing five specialist reports…');
  const D = buildDossier(P);
  P.D = D;
  io.say(A, `▸ activity ${D.scores.activity} · documentation ${D.scores.docs} · community ${D.scores.community} · engineering ${D.scores.eng} · compliance ${D.scores.compliance}`);
  io.say(A, `▸ weighted composite: ${D.score}/100 — verdict: ${D.tier.word} (${D.tier.note})`);
  if (D.recs.length) D.recs.forEach((r) => io.say(A, `▸ recommendation: ${r}`));
  else io.say(A, '▸ no blocking gaps detected — this repository is in excellent standing.', 'ok');
  io.say(A, 'Dossier compiled. Rendering report…');
  io.setAgent('warden', 'done');
}

export async function runCrew(P, fresh, io) {
  await agentScout(P, fresh, io);
  if (io.aborted()) throw new GHError('abort');
  await io.beat();
  await agentCartographer(P, fresh, io);
  if (io.aborted()) throw new GHError('abort');
  await io.beat();
  await agentPulse(P, fresh, io);
  if (io.aborted()) throw new GHError('abort');
  await io.beat();
  await agentArchivist(P, fresh, io);
  if (io.aborted()) throw new GHError('abort');
  await io.beat();
  await agentGuard(P, fresh, io);
  if (io.aborted()) throw new GHError('abort');
  await io.beat();
  await agentWarden(P, io);
  if (io.aborted()) throw new GHError('abort');
}

export function relTime(x) {
  return rel(x);
}

export function formatCount(n) {
  return fmtN(n);
}

export function formatDate(iso) {
  return fmtDate(iso);
}
