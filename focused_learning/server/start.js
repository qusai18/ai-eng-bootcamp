import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { loadEnv } from './env.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(__dirname, '..');

loadEnv();

function pythonBin() {
  if (process.env.PYTHON) return process.env.PYTHON;
  const candidates = [
    path.join(appRoot, '.venv', 'Scripts', 'python.exe'),
    path.join(appRoot, '.venv', 'bin', 'python'),
  ];
  return candidates.find((file) => fs.existsSync(file)) || 'python';
}

const child = spawn(
  pythonBin(),
  ['-m', 'uvicorn', 'knowledge.app:app', '--host', '127.0.0.1', '--port', String(process.env.KNOWLEDGE_PORT || 10001)],
  {
    cwd: appRoot,
    stdio: 'inherit',
    env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' },
  },
);

child.on('exit', (code, signal) => {
  if (signal) return;
  console.error(`knowledge service exited (${code})`);
});

function stop() {
  if (!child.killed) child.kill();
}
process.on('SIGINT', () => { stop(); process.exit(0); });
process.on('SIGTERM', () => { stop(); process.exit(0); });

await import('./index.js');
