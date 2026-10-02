import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { loadEnv, openAiConfigured } from './env.js';
import { mountGithub } from './github.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(__dirname, '..');

loadEnv();

const app = express();
app.disable('x-powered-by');

app.get('/health', (_req, res) => {
  res.json({ ok: true, openai: openAiConfigured() });
});

mountGithub(app);

const dist = path.join(appRoot, 'dist');
app.use(express.static(dist));
app.get('*', (_req, res) => {
  res.sendFile(path.join(dist, 'index.html'));
});

const port = Number(process.env.PORT) || 10000;
app.listen(port, '0.0.0.0', () => {
  console.log(`focused-learning listening on ${port} (openai ${openAiConfigured() ? 'configured' : 'missing'})`);
});
