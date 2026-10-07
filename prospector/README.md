# GitBytes

A field instrument for GitHub repository recommendations. Search, Ideation, and Painpoint still score results in the browser. GitHub calls go through the API, which holds an optional token, retries once on a server error, and caches repeats for a short time.

## Local

```bash
cd prospector/backend
python -m pip install -r requirements-dev.txt
python app.py
```

Open http://localhost:8000. The API also serves the frontend.

Copy `.env.example` to `.env` and set `GITHUB_TOKEN` if you want authenticated rate limits. The token stays on the server.

```bash
cd prospector/backend && python -m pytest
cd prospector/frontend && node --test
```

## Docker

From `prospector/`:

```bash
docker compose up --build
```

The site is on http://localhost:8080. The web container proxies `/api` and `/health` to the API.
