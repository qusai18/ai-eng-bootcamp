import { spawn } from 'child_process';
import fs from 'fs';
import net from 'net';
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

const knowledgePort = Number(process.env.KNOWLEDGE_PORT) || 10001;
let child = null;
let stopping = false;
let restartTimer = null;
let restartDelay = 1000;

function startKnowledge() {
  child = spawn(
    pythonBin(),
    ['-m', 'uvicorn', 'knowledge.app:app', '--host', '127.0.0.1', '--port', String(knowledgePort)],
    {
      cwd: appRoot,
      stdio: 'inherit',
      env: {
        ...process.env,
        PYTHONIOENCODING: 'utf-8',
        PYTHONUTF8: '1',
        OMP_NUM_THREADS: '1',
        MKL_NUM_THREADS: '1',
        TOKENIZERS_PARALLELISM: 'false',
      },
    },
  );
  child.on('exit', (code, signal) => {
    child = null;
    if (stopping) return;
    console.error(`knowledge service exited (${signal || code}); restarting`);
    restartTimer = setTimeout(startKnowledge, restartDelay);
    restartDelay = Math.min(restartDelay * 2, 15000);
  });
}

function portOpen(port) {
  return new Promise((resolve) => {
    const socket = net.connect(port, '127.0.0.1');
    const done = (open) => {
      socket.removeAllListeners();
      socket.destroy();
      resolve(open);
    };
    socket.on('connect', () => done(true));
    socket.on('error', () => done(false));
  });
}

async function waitForKnowledge() {
  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    if (await portOpen(knowledgePort)) {
      restartDelay = 1000;
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  console.error('knowledge service did not open its port; Ask will retry after it starts');
  return false;
}

function stop() {
  stopping = true;
  clearTimeout(restartTimer);
  if (child && !child.killed) child.kill();
}
process.on('SIGINT', () => { stop(); process.exit(0); });
process.on('SIGTERM', () => { stop(); process.exit(0); });

startKnowledge();
await waitForKnowledge();
await import('./index.js');
