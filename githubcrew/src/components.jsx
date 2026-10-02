import { useEffect, useRef, useState } from 'react';
import { formatCount, formatDate, relTime } from './analyze.js';
import { AGENTS, AGMAP, PATCH } from './data.js';

export function Header({ onDeploy }) {
  return (
    <header className="site">
      <div className="wrap nav">
        <a className="logo" href="#overview"><i />GITHUB<b>CREW</b></a>
        <nav className="links">
          <a href="#overview">Overview</a>
          <a href="#crew">The Crew</a>
          <a href="#console">Mission Console</a>
          <a href="#report">Assessment Report</a>
        </nav>
        <button className="btn primary sm cta" type="button" onClick={onDeploy}>Deploy a crew</button>
      </div>
    </header>
  );
}

export function Hero({ mission }) {
  return (
    <section className="hero" id="home">
      <div className="wrap">
        <p className="eyebrow">Agentic assessment · live GitHub recon</p>
        <h1>Repository due diligence, <em>run by a crew of six.</em></h1>
        <p className="hero-sub">Deploy a team of specialist agents that verify, map, measure, audit, screen and sign — pulling live evidence from the public GitHub API and returning a signed assessment dossier. Scoring stays in your browser. The Warden briefing is written on the server.</p>
        <form
          id="briefForm"
          autoComplete="off"
          onSubmit={(e) => {
            e.preventDefault();
            mission.start(mission.repoInput);
          }}
        >
          <div className="brief">
            <div className="briefrow">
              <input
                id="repoInput"
                ref={mission.inputRef}
                type="text"
                placeholder="owner/repo or https://github.com/owner/repo"
                spellCheck={false}
                aria-label="GitHub repository"
                value={mission.repoInput}
                onChange={(e) => mission.setRepoInput(e.target.value)}
                className={mission.shake ? 'shake' : undefined}
              />
              <button id="deployBtn" type="submit" className="btn primary" disabled={mission.running}>
                {mission.running ? 'Crew deployed…' : 'Deploy Crew'}
              </button>
              <button
                id="abortBtn"
                type="button"
                className={`btn danger${mission.running ? '' : ' hidden'}`}
                onClick={mission.abort}
              >
                Abort
              </button>
            </div>
            <div className="brief-err">
              <span id="inputErr" role="alert" className={mission.inputErr ? undefined : 'hidden'}>{mission.inputErr}</span>
              <span className="dim">ACCEPTS owner/repo OR A FULL GITHUB URL</span>
              <button type="button" className="linklike" onClick={mission.runDemo}>Try offline demo</button>
              <button type="button" className="linklike" onClick={mission.runExample}>run field test → sindresorhus/is</button>
            </div>
          </div>
        </form>
        <div className="hero-small">
          <span>SCORING IN THE BROWSER · BRIEFING VIA OPENAI</span>
          <span>UNAUTHENTICATED QUOTA 60 REQ/HR — ONE MISSION ≈ 10 CALLS</span>
          <span>FRAMEWORKS: NIST RMF · EU AI ACT</span>
        </div>
      </div>
    </section>
  );
}

export function Overview() {
  return (
    <section className="overview" id="overview">
      <div className="wrap ov-grid">
        <div>
          <p className="eyebrow">How an assessment runs</p>
          <h2 className="sec-t">Six specialists. One orchestration. One clear assessment.</h2>
          <p className="lead" style={{ marginTop: 18 }}>
            Scout verifies the target, Cartographer maps its structure, Pulse reads its heartbeat, Archivist audits its paperwork, <em>Guard screens security controls and compliance exposure</em>, and Warden weighs every finding before signing the dossier. Each agent logs its work to the live console as it happens.
          </p>
        </div>
        <div className="note">
          <h3>OPERATING NOTES</h3>
          <p style={{ fontSize: 14, lineHeight: 1.5, marginBottom: 12 }}>Six rule-based analyzers inspect public metadata. Framework indicators are preliminary signals, not a security audit or legal compliance determination.</p>
          <ul>
            <li><span><b>Browser-side scoring.</b> Analysis and the dossier render locally. Only the GitHub REST API is contacted from the browser.</span></li>
            <li><span><b>Warden briefing.</b> After the dossier is signed, composite scores are sent to this app’s server, which asks OpenAI for a short executive note.</span></li>
            <li><span><b>Click an agent</b> in the roster to filter the console to that specialist’s transmissions.</span></li>
            <li><span><b>Abort anytime.</b> In-flight requests are cancelled immediately; partial results are discarded.</span></li>
            <li><span><b>Re-runs are free.</b> Results are cached per session so repeat missions don’t burn quota.</span></li>
          </ul>
        </div>
      </div>
    </section>
  );
}

export function Crew() {
  return (
    <section className="crew" id="crew">
      <div className="wrap">
        <p className="eyebrow">The roster · 06 specialists</p>
        <h2 className="sec-t">A crew built for the job</h2>
        <div className="crew-grid" id="manifest">
          {AGENTS.map((a, i) => (
            <div className="ccard" key={a.id}>
              <div className="c-top">
                <div className="c-ico" dangerouslySetInnerHTML={{ __html: PATCH[a.id] }} />
                <span className="c-num">{String(i + 1).padStart(2, '0')}</span>
              </div>
              <span className="c-label">Phase {String(i + 1).padStart(2, '0')} · {a.role}</span>
              <h3>{a.name.charAt(0)}{a.name.slice(1).toLowerCase()}</h3>
              <p>{a.line}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function Console({ mission }) {
  const feedRef = useRef(null);
  useEffect(() => {
    const el = feedRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [mission.logs]);

  return (
    <section className="console-sec" id="console" ref={mission.consoleRef}>
      <div className="wrap">
        <p className="eyebrow">Mission console</p>
        <h2 className="sec-t">Watch the crew work</h2>
        <div className="mission">
          <aside className="rail">
            <div className="rail-h">CREW ROSTER · 06 <span>click to filter</span></div>
            <div id="roster" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {AGENTS.map((a) => {
                const row = mission.agents[a.id];
                const on = mission.filter === a.id;
                return (
                  <div
                    key={a.id}
                    className={`agent${on ? ' filtered' : ''}`}
                    role="button"
                    tabIndex={0}
                    aria-pressed={on}
                    data-agent={a.id}
                    data-state={row.state}
                    title={`Filter the console to ${a.name}`}
                    onClick={() => mission.toggleFilter(a.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        mission.toggleFilter(a.id);
                      }
                    }}
                  >
                    <div className="patch" dangerouslySetInnerHTML={{ __html: PATCH[a.id] }} />
                    <div className="who"><b>{a.name}</b><span>{a.role}</span></div>
                    <div className="ast"><i className="dot" /><em>{row.label}</em></div>
                  </div>
                );
              })}
            </div>
            <div className="railstats">
              <div><span>STATUS</span><b className={mission.status === 'STANDBY' ? undefined : `st-${mission.status.toLowerCase()}`}>{mission.status}</b></div>
              <div><span>ELAPSED</span><b>{mission.elapsed}</b></div>
              <div><span>API CALLS</span><b>{mission.callCount}</b></div>
              <div><span>QUOTA</span><b>{mission.quota}</b></div>
            </div>
          </aside>
          <div className="wire">
            <div className="wire-h">
              <span><i className={`wdot${mission.running ? ' live' : ''}`} />ORCHESTRATION FEED — LIVE</span>
              <span>FILTER: <b id="filterTag">{mission.filter ? AGMAP[mission.filter].name : '—'}</b></span>
            </div>
            <div className="wire-body" id="feed" data-f={mission.filter} ref={feedRef}>
              {mission.logs.map((line) => (
                <div key={line.id} className={`fl ${line.kind}`} data-a={line.agent}>
                  {line.kind !== 'sys' && <span className="ft">{line.time}</span>}
                  {line.agent && <span className="fa">[{AGMAP[line.agent].name}]</span>}
                  <span className="fx">{line.text}</span>
                </div>
              ))}
              <div className="fl curline"><span className="cur" /></div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Gauge({ label, value, delay }) {
  const C = Math.PI * 32;
  const off = C * (1 - value / 100);
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    el.style.strokeDashoffset = String(C);
    const timer = setTimeout(() => {
      el.style.strokeDashoffset = String(off);
    }, delay);
    return () => clearTimeout(timer);
  }, [C, off, delay]);
  return (
    <div className="gauge">
      <svg viewBox="0 0 76 46">
        <path className="track" d="M6 40 A32 32 0 0 1 70 40" />
        <path ref={ref} className="gval" d="M6 40 A32 32 0 0 1 70 40" strokeDasharray={C} strokeDashoffset={C} />
      </svg>
      <b>{value}</b>
      <span>{label}</span>
    </div>
  );
}

function CountUp({ to }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    const t0 = performance.now();
    const dur = 1100;
    let frame;
    const step = (t) => {
      const p = Math.min(1, (t - t0) / dur);
      const e = 1 - (1 - p) ** 3;
      setN(Math.round(to * e));
      if (p < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [to]);
  return <span>{n}</span>;
}

function LangBar({ langs }) {
  const total = langs.reduce((s, [, b]) => s + b, 0) || 1;
  const pal = ['#0B2E59', '#1E9E5A', '#7C93AE', '#B9C6D6', '#5A6E86'];
  const top = langs.slice(0, 5);
  const rest = langs.slice(5).reduce((s, [, b]) => s + b, 0);
  let acc = 0;
  return (
    <>
      <div className="langbar">
        {top.map(([n, b], i) => {
          const p = (b / total) * 100;
          acc += p;
          return <i key={n} style={{ width: `${p}%`, background: pal[i] }} title={n} />;
        })}
        {rest > 0 && <i style={{ width: `${100 - acc}%`, background: '#E2E8F0' }} title="Other" />}
      </div>
      <div className="lg">
        {top.map(([n, b], i) => (
          <span className="lgit" key={n}>
            <i style={{ background: pal[i] }} />
            {n} <b>{((b / total) * 100).toFixed(1)}%</b>
          </span>
        ))}
        {rest > 0 && (
          <span className="lgit">
            <i style={{ background: '#E2E8F0' }} />
            Other <b>{((rest / total) * 100).toFixed(1)}%</b>
          </span>
        )}
      </div>
    </>
  );
}

function Cadence({ buckets }) {
  const max = Math.max(...buckets, 1);
  const bw = 16;
  const gp = 9;
  const W = 295;
  const H = 92;
  const base = 72;
  const now = new Date();
  const lbl = (d) => d.toLocaleString('en', { month: 'short' }).toUpperCase();
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="cad" role="img" aria-label="Commits per week, last 12 weeks">
      <line x1="0" y1={base + 0.5} x2={W} y2={base + 0.5} className="axis" />
      {buckets.map((v, i) => {
        const x = 2 + i * (bw + gp);
        const h = v ? Math.max(2, Math.round((v / max) * 48)) : 0;
        return <rect key={i} x={x} y={base - h} width={bw} height={h} className={i === 11 ? 'now' : undefined} />;
      })}
      <text x="2" y={H - 4} className="tick">{lbl(new Date(now.getTime() - 11.5 * 6048e5))}</text>
      <text x={W - 2} y={H - 4} textAnchor="end" className="tick nowt">{lbl(now)}</text>
    </svg>
  );
}

const PILL = { ok: ['SATISFIED', 'p-ok'], warn: ['PARTIAL', 'p-warn'], gap: ['GAP', 'p-gap'] };

export function Report({ mission }) {
  const packed = mission.result;
  if (!packed) {
    return <section className="report-sec" id="report"><div className="wrap" /></section>;
  }
  const { dossier: D, payload: P } = packed;
  const m = P.meta;
  const metaPairs = [
    ['STARS', formatCount(m.stargazers_count)],
    ['FORKS', formatCount(m.forks_count)],
    ['OPEN', formatCount(m.open_issues_count)],
    ['LICENSE', m.license ? m.license.spdx_id : 'NONE'],
    ['RMF', `${D.rmf.score}/100`],
    ['AI ACT', D.ai.tier.key.toUpperCase()],
    ['CREATED', formatDate(m.created_at).slice(0, 4)],
    ['PUSHED', relTime(m.pushed_at).toUpperCase()],
  ];
  const chips = [...(D.ai.proh.length ? D.ai.proh.slice(0, 3) : []), ...D.ai.hits.slice(0, 4), ...D.ai.high.slice(0, 3)];

  function download() {
    const blob = new Blob([JSON.stringify({
      mode: P.demo ? 'sample' : 'live',
      generatedAt: new Date().toISOString(),
      assessment: D,
      briefing: mission.briefing?.status === 'ready' ? mission.briefing.text : null,
    }, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${P.repo.replace('/', '-')}-assessment.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <section className="report-sec" id="report">
      <div className="wrap">
        <section className="dossier" id="dossier" ref={mission.dossierRef}>
          {P.demo && <p className="demo-notice">OFFLINE DEMO · Illustrative sample data, not a live repository assessment.</p>}
          <div className="d-top">
            <span>§ ASSESSMENT REPORT — FINDINGS OF THE CREW</span>
            <span>FILE {D.fileNo} · {new Date().toISOString().slice(0, 10)}</span>
          </div>
          <div className="d-title">
            <div>
              <h2>{D.name}</h2>
              <p className="d-owner">github.com/{D.repo}</p>
              {m.description && <p className="d-desc">{m.description}</p>}
            </div>
            <div className="d-verdict">
              <div className={`stamp ${D.tier.cls}`.trim()}>{D.tier.word}<small>GITHUB CREW · HEALTH {D.score}/100</small></div>
              <div className="scorebox">
                <div className="bigscore"><CountUp to={D.score} /><i>/100</i></div>
                <em>COMPOSITE HEALTH</em>
              </div>
            </div>
          </div>
          <div className="d-meta">
            {metaPairs.map(([k, v]) => <span key={k}>{k} <b>{v}</b></span>)}
          </div>
          <div className="briefing">
            <h3>WARDEN BRIEFING</h3>
            {mission.briefing?.status === 'ready' && <p>{mission.briefing.text}</p>}
            {mission.briefing?.status === 'loading' && <p>Warden is writing the executive note…</p>}
            {(!mission.briefing || mission.briefing.status === 'unavailable') && (
              <p>Briefing service unavailable. The scored dossier below is complete.</p>
            )}
          </div>
          <div className="d-grid">
            <div className="dcol">
              <div className="slab">§01 VITALS — SUB-SCORES</div>
              <div className="gauges">
                <Gauge label="ACTIVITY" value={D.scores.activity} delay={250} />
                <Gauge label="DOCS" value={D.scores.docs} delay={380} />
                <Gauge label="COMMUNITY" value={D.scores.community} delay={510} />
                <Gauge label="ENGINEERING" value={D.scores.eng} delay={640} />
                <Gauge label="COMPLIANCE" value={D.scores.compliance} delay={770} />
              </div>
              <div className="slab">§02 SECURITY CONTROLS — NIST RMF</div>
              <div className="rmf">
                {D.rmf.steps.map((r, i) => (
                  <div className="rmf-row" key={r.step}>
                    <div className="rmf-h">
                      <b><i>{String(i + 1).padStart(2, '0')}</i>{r.step}</b>
                      <span className={`pill ${PILL[r.st][1]}`}>{PILL[r.st][0]}</span>
                    </div>
                    <p className="rmf-ev">{r.ev}</p>
                  </div>
                ))}
              </div>
              <p className="cap">RMF READINESS {D.rmf.score}/100 · {D.rmf.ok} SATISFIED · {D.rmf.warn} PARTIAL · {D.rmf.gap} GAPS</p>
              <div className="slab">§03 STACK MANIFEST</div>
              {P.langList?.length ? <LangBar langs={P.langList} /> : <p className="none">No language data recorded.</p>}
              <div className="slab">§04 CADENCE — LAST 12 WEEKS</div>
              {P.sampled ? <Cadence buckets={P.buckets} /> : <p className="none">No commits to chart.</p>}
              {P.sampled ? <p className="cap">SAMPLE: LAST {P.sampled} COMMITS · ≈{P.perWeek.toFixed(1)}/WEEK · HEARTBEAT {P.strength}</p> : null}
            </div>
            <div className="dcol">
              <div className="slab">§05 SIGNALS</div>
              {D.signals.map(([id, text]) => (
                <div className="sig" key={id}>
                  <span className="sp" dangerouslySetInnerHTML={{ __html: PATCH[id] }} />
                  <b>{AGMAP[id].name}</b>
                  <p>{text}</p>
                </div>
              ))}
              <div className="slab">§06 EU AI ACT SCREENING</div>
              <div className="ai">
                <span className={`ai-badge ${D.ai.tier.cls}`}>{D.ai.tier.word}</span>
                <p className="ai-note">{D.ai.tier.note}</p>
                {chips.length > 0 && (
                  <div className="chips">
                    {chips.map((c) => <span className="chip" key={c}>{c.trim()}</span>)}
                  </div>
                )}
                <p className="ai-arts">RELEVANT PROVISIONS: {D.ai.tier.arts}</p>
                <p className="ai-disc">OBLIGATIONS SCREENED: {D.ai.tier.obl.join(' · ')} — automated heuristic screening from public repository metadata; not a legal determination.</p>
              </div>
              <div className="slab">§07 CONTRIBUTORS{P.contribTotal ? ` — ${P.contribTotal}${P.contribTotal === 100 ? '+' : ''}` : ''}</div>
              {(P.top || []).length ? P.top.map((c, i) => {
                const mx = P.top[0].contributions || 1;
                return (
                  <div className="contrib" key={c.login || i}>
                    <span className="crank">{String(i + 1).padStart(2, '0')}</span>
                    <span className="cname">{c.login || 'anonymous'}</span>
                    <span className="cbar"><i style={{ width: `${Math.round((c.contributions / mx) * 100)}%` }} /></span>
                    <b>{formatCount(c.contributions)}</b>
                  </div>
                );
              }) : <p className="none">No contributor records.</p>}
              <div className="slab">§08 RECOMMENDATIONS</div>
              {D.recs.length ? D.recs.map((r, i) => (
                <div className="rec" key={r}>
                  <b>{String(i + 1).padStart(2, '0')}</b>
                  <p>{r}</p>
                </div>
              )) : (
                <div className="rec"><b>✓</b><p>No blocking gaps — this repository is in excellent standing.</p></div>
              )}
            </div>
          </div>
          <div className="d-foot">
            <span>COMPILED BY 6 RULE-BASED ANALYZERS · DATA: API.GITHUB.COM · {new Date().toUTCString().slice(17, 25)} UTC</span>
            <button className="btn ghost sm" type="button" onClick={download}>Download JSON</button>
            <button className="btn ghost sm" type="button" onClick={() => window.print()}>Print / PDF</button>
            <button className="btn ghost sm" type="button" onClick={mission.focusBrief}>NEW MISSION</button>
          </div>
        </section>
      </div>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="site">
      <div className="wrap">
        <div className="f-grid">
          <div>
            <div className="f-logo"><i />GITHUB<b>CREW</b></div>
            <p>An independent field exercise in agentic architecture: six specialists assess any public GitHub repository. Scoring runs in the browser. The Warden’s executive note is generated server-side with OpenAI. Visual language in the style of modern consulting sites; not affiliated with or endorsed by ICF International.</p>
          </div>
          <div>
            <h4>METHOD</h4>
            <ul>
              <li><a href="#overview">Overview</a></li>
              <li><a href="#crew">The Crew</a></li>
              <li><a href="#console">Mission Console</a></li>
              <li><a href="#report">Assessment Report</a></li>
            </ul>
          </div>
          <div>
            <h4>FRAMEWORKS & DATA</h4>
            <ul>
              <li><a href="https://www.nist.gov/itl/ssd/cs/risk-management-framework" target="_blank" rel="noopener noreferrer">NIST Risk Management Framework ↗</a></li>
              <li><a href="https://artificialintelligenceact.eu/" target="_blank" rel="noopener noreferrer">EU AI Act Explorer ↗</a></li>
              <li><a href="https://docs.github.com/rest" target="_blank" rel="noopener noreferrer">GitHub REST API docs ↗</a></li>
            </ul>
          </div>
        </div>
        <div className="f-bar">
          <span>GITHUB CREW · SIX SPECIALISTS, ONE REPOSITORY</span>
          <span>DATA: API.GITHUB.COM · SCORES LOCAL · BRIEFING VIA OPENAI</span>
        </div>
      </div>
    </footer>
  );
}
