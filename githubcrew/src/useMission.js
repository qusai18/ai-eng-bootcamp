import { useEffect, useRef, useState } from 'react';
import { GHError, parseRepo, runCrew } from './analyze.js';
import { AGENTS, EXAMPLES, demoPayload } from './data.js';

const FAIL = {
  notfound: 'TARGET NOT FOUND — DOES NOT EXIST OR IS PRIVATE',
  limit: 'GITHUB API RATE LIMIT REACHED (60/HR, UNAUTHENTICATED) — THE CREW STANDS DOWN',
  quota: 'API QUOTA TOO LOW FOR A FULL MISSION (NEED ≥ 12 CALLS)',
  net: 'NETWORK FAULT — COULD NOT REACH API.GITHUB.COM',
  http: 'GITHUB API RETURNED AN ERROR',
};

function fmtElapsed(ms) {
  const s = ms / 1000;
  const m = Math.floor(s / 60);
  return `${String(m).padStart(2, '0')}:${(s - m * 60).toFixed(1).padStart(4, '0')}`;
}

const standbyAgents = () => Object.fromEntries(AGENTS.map((a) => [a.id, { state: 'standby', label: 'STANDBY' }]));

export function useMission() {
  const [repoInput, setRepoInput] = useState('');
  const [inputErr, setInputErr] = useState('');
  const [shake, setShake] = useState(false);
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState('STANDBY');
  const [elapsed, setElapsed] = useState('00:00.0');
  const [callCount, setCallCount] = useState(0);
  const [quota, setQuota] = useState('—/60');
  const [logs, setLogs] = useState([{ id: 1, kind: 'sys', text: 'CONSOLE IDLE — DEPLOY A CREW TO BEGIN.' }]);
  const [agents, setAgents] = useState(standbyAgents);
  const [filter, setFilter] = useState('');
  const [result, setResult] = useState(null);
  const [briefing, setBriefing] = useState(null);

  const abortedRef = useRef(false);
  const runningRef = useRef(false);
  const controllerRef = useRef(null);
  const cacheRef = useRef(new Map());
  const callsRef = useRef(Object.fromEntries(AGENTS.map((a) => [a.id, 0])));
  const agentRef = useRef(null);
  const callCountRef = useRef(0);
  const logId = useRef(1);
  const timerRef = useRef(null);
  const inputRef = useRef(null);
  const consoleRef = useRef(null);
  const dossierRef = useRef(null);
  const exIdx = useRef(0);
  const reduced = useRef(typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches);

  useEffect(() => () => clearInterval(timerRef.current), []);

  function say(agent, text, kind = 'say') {
    const time = new Date().toTimeString().slice(0, 8);
    setLogs((prev) => [...prev, { id: ++logId.current, agent, text, kind, time }]);
  }

  function sys(text) {
    setLogs((prev) => [...prev, { id: ++logId.current, kind: 'sys', text }]);
  }

  function setAgent(id, st, label) {
    const text = label || { standby: 'STANDBY', working: 'WORKING', done: 'DONE', failed: 'FAILED' }[st];
    setAgents((prev) => ({ ...prev, [id]: { state: st, label: text } }));
  }

  function bump(id) {
    setAgents((prev) => {
      const cur = prev[id];
      if (!cur || cur.state !== 'working') return prev;
      return { ...prev, [id]: { ...cur, label: `WORKING · ${callsRef.current[id]}` } };
    });
  }

  async function gh(path, opt = {}) {
    const { soft = false, raw = false, empty409 = false } = opt;
    const agent = agentRef.current;
    const t0 = performance.now();
    let res;
    try {
      res = await fetch(`https://api.github.com${path}`, {
        signal: controllerRef.current.signal,
        headers: raw
          ? { Accept: 'application/vnd.github.raw' }
          : { Accept: 'application/vnd.github+json' },
      });
    } catch {
      if (abortedRef.current) throw new GHError('abort');
      throw new GHError('net');
    }
    const ms = Math.round(performance.now() - t0);
    callCountRef.current += 1;
    setCallCount(callCountRef.current);
    if (agent) {
      callsRef.current[agent] += 1;
      bump(agent);
    }
    say(agent, `⇄ GET ${path} → ${res.status} · ${ms} ms`, (res.ok || soft) ? 'tool' : 'warn');
    if (res.status === 409 && empty409) return [];
    if (soft && res.status === 404) return null;
    if (res.status === 429 || (res.status === 403 && res.headers.get('x-ratelimit-remaining') === '0')) throw new GHError('limit');
    if (res.status === 404) throw new GHError('notfound');
    if (!res.ok) throw new GHError('http');
    if (res.status === 204) return [];
    return raw ? res.text() : res.json();
  }

  function finishRun(next) {
    clearInterval(timerRef.current);
    setElapsed(fmtElapsed(Date.now() - timerRef.currentStarted));
    runningRef.current = false;
    setRunning(false);
    setStatus(next);
  }

  async function loadBriefing(D) {
    setBriefing({ status: 'loading', text: '' });
    try {
      const res = await fetch('/api/briefing', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          repo: D.repo,
          score: D.score,
          tier: D.tier,
          scores: D.scores,
          signals: D.signals.map(([id, text]) => ({ id, text })),
          recs: D.recs,
          rmf: { score: D.rmf.score, ok: D.rmf.ok, warn: D.rmf.warn, gap: D.rmf.gap },
          ai: { word: D.ai.tier.word, arts: D.ai.tier.arts, key: D.ai.tier.key },
        }),
      });
      if (!res.ok) throw new Error('briefing');
      const data = await res.json();
      setBriefing({ status: 'ready', text: data.briefing });
    } catch {
      setBriefing({ status: 'unavailable', text: '' });
    }
  }

  async function start(raw) {
    if (runningRef.current) return;
    const repo = parseRepo(raw);
    if (!repo) {
      setInputErr('CANNOT PARSE — EXPECTED owner/repo OR A GITHUB.COM URL');
      setShake(true);
      setTimeout(() => setShake(false), 450);
      inputRef.current?.focus();
      return;
    }
    setInputErr('');
    abortedRef.current = false;
    runningRef.current = true;
    setRunning(true);
    controllerRef.current = new AbortController();
    const t0 = Date.now();
    timerRef.currentStarted = t0;
    callCountRef.current = 0;
    callsRef.current = Object.fromEntries(AGENTS.map((a) => [a.id, 0]));
    setCallCount(0);
    setLogs([]);
    setFilter('');
    setAgents(standbyAgents());
    setResult(null);
    setBriefing(null);
    setStatus('RUNNING');
    setQuota('—/60');
    setElapsed('00:00.0');
    clearInterval(timerRef.current);
    timerRef.current = setInterval(() => setElapsed(fmtElapsed(Date.now() - t0)), 100);
    consoleRef.current?.scrollIntoView({ behavior: reduced.current ? 'auto' : 'smooth', block: 'start' });

    const fresh = !cacheRef.current.has(repo);
    const P = fresh ? { repo } : cacheRef.current.get(repo);
    const io = {
      say,
      setAgent,
      setQuota,
      gh,
      aborted: () => abortedRef.current,
      beat: () => new Promise((r) => setTimeout(r, reduced.current ? 0 : 240)),
      current: (id) => { agentRef.current = id; },
    };

    try {
      sys(`CREW DEPLOYED · TARGET ${repo} · ${fresh ? 'LIVE COLLECTION' : 'CACHED INTELLIGENCE'}`);
      await runCrew(P, fresh, io);
      if (fresh) cacheRef.current.set(repo, P);
      sys(`MISSION COMPLETE IN ${fmtElapsed(Date.now() - t0)} · DOSSIER ISSUED`);
      finishRun('COMPLETE');
      setResult({ dossier: P.D, payload: P });
      loadBriefing(P.D);
      setTimeout(() => dossierRef.current?.scrollIntoView({ behavior: reduced.current ? 'auto' : 'smooth', block: 'start' }), 700);
    } catch (err) {
      if (abortedRef.current || err === 'abort' || (err instanceof GHError && err.kind === 'abort')) {
        setAgents((prev) => {
          const next = { ...prev };
          for (const [id, row] of Object.entries(next)) {
            if (row.state === 'working') next[id] = { state: 'standby', label: 'STOPPED' };
          }
          return next;
        });
        finishRun('ABORTED');
        return;
      }
      const k = err instanceof GHError ? err.kind : 'net';
      sys(`MISSION ABORTED · ${FAIL[k] || FAIL.http}`);
      if (agentRef.current) setAgent(agentRef.current, 'failed');
      finishRun('FAILED');
    }
  }

  function abort() {
    if (!runningRef.current) return;
    abortedRef.current = true;
    controllerRef.current?.abort();
  }

  function focusBrief() {
    window.scrollTo({ top: 0, behavior: reduced.current ? 'auto' : 'smooth' });
    setTimeout(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    }, 400);
  }

  function runExample() {
    const repo = `https://github.com/${EXAMPLES[exIdx.current % EXAMPLES.length]}`;
    exIdx.current += 1;
    setRepoInput(repo);
    start(repo);
  }

  function runDemo() {
    if (runningRef.current) return;
    cacheRef.current.set('demo/field-notes', demoPayload());
    setRepoInput('demo/field-notes');
    start('demo/field-notes');
  }

  function toggleFilter(id) {
    setFilter((prev) => (prev === id ? '' : id));
  }

  return {
    repoInput,
    setRepoInput,
    inputErr,
    shake,
    running,
    status,
    elapsed,
    callCount,
    quota,
    logs,
    agents,
    filter,
    result,
    briefing,
    inputRef,
    consoleRef,
    dossierRef,
    start,
    abort,
    focusBrief,
    runExample,
    runDemo,
    toggleFilter,
    reduced: reduced.current,
  };
}
