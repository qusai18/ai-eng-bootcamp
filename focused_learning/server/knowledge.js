import http from 'http';

const TARGET_PORT = Number(process.env.KNOWLEDGE_PORT) || 10001;

export function mountKnowledge(app) {
  app.use('/api/knowledge', (req, res) => {
    const headers = { ...req.headers, host: `127.0.0.1:${TARGET_PORT}` };
    const proxy = http.request(
      {
        hostname: '127.0.0.1',
        port: TARGET_PORT,
        path: req.originalUrl,
        method: req.method,
        headers,
      },
      (upstream) => {
        res.writeHead(upstream.statusCode || 502, upstream.headers);
        upstream.pipe(res);
      },
    );
    proxy.on('error', () => {
      if (!res.headersSent) {
        res.status(503).json({ error: 'Knowledge service is not running' });
      }
    });
    req.pipe(proxy);
  });
}
