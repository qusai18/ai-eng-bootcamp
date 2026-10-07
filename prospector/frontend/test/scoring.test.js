import test from 'node:test';
import assert from 'node:assert/strict';
import { SAMPLE } from '../js/lexicon.js';
import {
  diagnose,
  extractSignals,
  makeItem,
  planContext,
  planPain,
  planSurvey,
  settleClaims,
  surveyCriteria,
  surveyFullQuery,
} from '../js/scoring.js';

test('sample context pans the expected stack signals', () => {
  const keys = extractSignals(SAMPLE).map(s => s.k);
  for (const key of ['nextjs', 'typescript', 'tailwind', 'prisma', 'postgres', 'gh-actions', 'react']) {
    assert.ok(keys.includes(key), key);
  }
});

test('a slow-test complaint is diagnosed and planned', () => {
  const text = 'my test suite is slow and flaky';
  const dx = diagnose(text);
  assert.equal(dx.id, 'tests');
  const plan = planPain(text);
  assert.equal(plan.mode, 'pain');
  assert.equal(plan.headline, 'diagnosis — SLOW TESTS');
  assert.equal(plan.queries.length, 3);
  assert.match(plan.queries[0].q, /test/);
});

test('survey query keeps qualifiers and applies the star floor', () => {
  const plan = planSurvey('topic:cli language:rust', { sort: 'stars', minStars: 1000 });
  assert.equal(
    plan.queries[0].q,
    'topic:cli language:rust archived:false fork:false pushed:>=2025-01-01 in:name,description stars:>=1000',
  );
  assert.equal(plan.queries[0].sort, 'stars');
  assert.match(plan.subline, /stars:>=1000/);
  assert.deepEqual(surveyCriteria('topic:cli language:rust', { sort: 'stars', minStars: 1000 }), [
    'not archived',
    'not a fork',
    'pushed since 2025-01-01',
    'words matched in name and description',
    'minimum stars 1K',
    'sort by stars',
  ]);
});

test('typed survey qualifiers are left as written', () => {
  assert.equal(
    surveyFullQuery('cli archived:true fork:only', 0),
    'cli archived:true fork:only pushed:>=2025-01-01 in:name,description',
  );
});

test('context assay drafts a topic query per signal', () => {
  const sigs = extractSignals('a FastAPI service with pytest');
  const plan = planContext(sigs);
  assert.ok(plan.queries.some(q => q.q.includes('topic:fastapi')));
  assert.ok(plan.queries.some(q => q.q.includes('topic:pytest')));
});

test('archived repos cannot outrank a fresh claim', () => {
  const now = new Date().toISOString();
  const ctx = { signals: [], terms: ['repo'], painKws: null, pain: null };
  const archived = makeItem({
    full_name: 'old/repo',
    description: 'repo',
    topics: [],
    stargazers_count: 100000,
    pushed_at: now,
    archived: true,
    language: 'Go',
  }, ctx);
  assert.ok(archived.fit <= 18);
  assert.match(archived.why, /ARCHIVED/);
});

test('a later rate limit keeps repos already recovered', () => {
  const plan = planSurvey('ripgrep', { sort: 'best', minStars: 0 });
  const kept = settleClaims([{
    full_name: 'BurntSushi/ripgrep',
    description: 'search',
    topics: ['rust'],
    stargazers_count: 50000,
    pushed_at: new Date().toISOString(),
    archived: false,
    language: 'Rust',
    html_url: 'https://github.com/BurntSushi/ripgrep',
    owner: { login: 'BurntSushi' },
  }], plan, { rateLimited: true });
  assert.equal(kept.source, 'partial');
  assert.equal(kept.list.length, 1);
  assert.equal(kept.list[0].r.full_name, 'BurntSushi/ripgrep');
  assert.equal(kept.list[0].r.ledger, undefined);
});

test('an empty rate-limited survey falls back to the ledger', () => {
  const plan = planPain('my test suite is slow and flaky');
  const fallback = settleClaims([], plan, { rateLimited: true });
  assert.equal(fallback.source, 'ledger');
  assert.ok(fallback.list.length > 0);
  assert.equal(fallback.list[0].r.ledger, true);
});
