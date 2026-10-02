const ALLOWED_HOSTS = new Set(['api.github.com', 'raw.githubusercontent.com']);
const MAX_BYTES = 20 * 1024 * 1024;

function allowedGithubUrl(value) {
  let url;
  try {
    url = new URL(value);
  } catch {
    return null;
  }
  if (url.protocol !== 'https:' || !ALLOWED_HOSTS.has(url.hostname)) return null;
  return url;
}

export function mountGithub(app) {
  app.get('/api/github', async (req, res) => {
    const target = allowedGithubUrl(req.query.url);
    if (!target) {
      res.status(400).json({ error: 'Only GitHub API and raw content URLs are allowed' });
      return;
    }

    const headers = {
      Accept: target.hostname === 'api.github.com' ? 'application/vnd.github+json' : 'text/plain',
      'User-Agent': 'focused-learning',
      'X-GitHub-Api-Version': '2022-11-28',
    };
    const token = process.env.GITHUB_TOKEN || process.env.GH_TOKEN || '';
    if (token) headers.Authorization = `Bearer ${token}`;

    try {
      const response = await fetch(target, {
        headers,
        signal: AbortSignal.timeout(30000),
      });
      const remaining = response.headers.get('x-ratelimit-remaining');
      if (remaining != null) res.set('x-ratelimit-remaining', remaining);
      const type = response.headers.get('content-type');
      if (type) res.set('content-type', type);
      const body = Buffer.from(await response.arrayBuffer());
      if (body.length > MAX_BYTES) {
        res.status(413).json({ error: 'GitHub response too large' });
        return;
      }
      res.status(response.status).send(body);
    } catch {
      res.status(502).json({ error: 'GitHub request failed' });
    }
  });
}
