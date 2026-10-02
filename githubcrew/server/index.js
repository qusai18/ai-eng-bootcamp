import dotenv from 'dotenv';
import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(__dirname, '..');

dotenv.config({ path: path.join(appRoot, '.env') });
dotenv.config({ path: path.resolve(appRoot, '..', '.env') });

function openAiKey() {
  let key = (process.env.OPENAI_API_KEY || '').trim();
  if ((key.startsWith('"') && key.endsWith('"')) || (key.startsWith("'") && key.endsWith("'"))) {
    key = key.slice(1, -1);
  }
  return key;
}

const app = express();
app.disable('x-powered-by');
app.use(express.json({ limit: '32kb' }));

app.get('/health', (_req, res) => {
  res.json({ ok: true, briefing: Boolean(openAiKey()) });
});

app.post('/api/briefing', async (req, res) => {
  const key = openAiKey();
  if (!key) {
    res.status(503).json({ error: 'OPENAI_API_KEY is not configured' });
    return;
  }

  const body = req.body || {};
  const payload = {
    repo: String(body.repo || '').slice(0, 200),
    score: body.score,
    tier: body.tier,
    scores: body.scores,
    signals: Array.isArray(body.signals) ? body.signals.slice(0, 8) : [],
    recs: Array.isArray(body.recs) ? body.recs.slice(0, 8) : [],
    rmf: body.rmf,
    ai: body.ai,
  };

  try {
    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${key}`,
        'Content-Type': 'application/json',
      },
      signal: AbortSignal.timeout(20000),
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        temperature: 0.3,
        max_tokens: 220,
        messages: [
          {
            role: 'system',
            content: 'You are the Warden of GitHub Crew. Write a 3-sentence executive briefing of a repository assessment for a technical reader. Use only the numbers and findings provided. Do not invent metrics, do not give legal advice, and do not mention that you are an AI model.',
          },
          { role: 'user', content: JSON.stringify(payload) },
        ],
      }),
    });

    if (!response.ok) {
      res.status(502).json({ error: 'Briefing model request failed' });
      return;
    }

    const data = await response.json();
    const briefing = data?.choices?.[0]?.message?.content?.trim();
    if (!briefing) {
      res.status(502).json({ error: 'Empty briefing' });
      return;
    }
    res.json({ briefing });
  } catch {
    res.status(502).json({ error: 'Briefing model request failed' });
  }
});

const dist = path.join(appRoot, 'dist');
app.use(express.static(dist));
app.use((_req, res) => {
  res.sendFile(path.join(dist, 'index.html'));
});

const port = Number(process.env.PORT) || 10000;
app.listen(port, '0.0.0.0', () => {
  console.log(`github-crew listening on ${port} (openai ${openAiKey() ? 'configured' : 'missing'})`);
});
