import dotenv from 'dotenv';
import os from 'os';
import path from 'path';
import { fileURLToPath } from 'url';

const appRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

export function loadEnv() {
  const files = [
    path.join(os.homedir(), '.env'),
    path.resolve(appRoot, '..', '.env'),
    path.join(appRoot, '.env'),
  ];
  for (const file of files) dotenv.config({ path: file });
}

export function openAiConfigured() {
  return Boolean(process.env.OPENAI_API_KEY);
}
