"""
Maryiam Daily Jobs — local server
Pulls remote BA roles from public aggregators, scores them against strategy.json,
serves a daily apply board. Does not auto-submit applications on LinkedIn/Indeed/etc.
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DATA = ROOT / "data"
CACHE = DATA / "cache"
APPS_FILE = DATA / "applications.json"
DAILY_FILE = DATA / "daily_batch.json"
STRATEGY_FILE = ROOT / "strategy.json"

USER_AGENT = "MaryiamDailyJobs/1.0 (+local; strategy-aligned BA search)"
PORT = 8791


def ensure_dirs() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    if not APPS_FILE.exists():
        APPS_FILE.write_text("[]", encoding="utf-8")


def load_strategy() -> dict:
    return json.loads(STRATEGY_FILE.read_text(encoding="utf-8"))


def load_apps() -> list[dict]:
    try:
        return json.loads(APPS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def save_apps(apps: list[dict]) -> None:
    APPS_FILE.write_text(json.dumps(apps, indent=2), encoding="utf-8")


def http_get_json(url: str, timeout: int = 20) -> dict | list | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"[fetch] fail {url}: {exc}")
        return None


def http_get_text(url: str, timeout: int = 12) -> tuple[int | None, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(180_000)
            charset = "utf-8"
            ctype = resp.headers.get_content_charset()
            if ctype:
                charset = ctype
            return resp.status, raw.decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read(80_000).decode("utf-8", errors="replace")
        except Exception:
            pass
        return exc.code, body
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"[link-check] fail {url}: {exc}")
        return None, ""


DEAD_JOB_PHRASES = (
    "no longer available",
    "this job is no longer available",
    "sorry this job is no longer available",
    "sorry, this job is no longer available",
    "job is no longer available",
    "this position is no longer available",
    "position has been filled",
    "job has expired",
    "job posting has expired",
    "this job has expired",
    "listing has been removed",
    "job has been removed",
    "this job is closed",
    "job not found",
    "page not found",
    "we can't find this job",
    "we cannot find this job",
    "this job posting is no longer",
    "opening is closed",
    "requisition is closed",
    "no longer accepting applications",
)


BOARD_HOSTS = (
    ("linkedin.com", "LinkedIn"),
    ("indeed.com", "Indeed"),
    ("dice.com", "Dice"),
    ("monster.com", "Monster"),
    ("careerbuilder.com", "CareerBuilder"),
    ("remotive.com", "Remotive"),
    ("arbeitnow.com", "Arbeitnow"),
    ("glassdoor.com", "Glassdoor"),
    ("ziprecruiter.com", "ZipRecruiter"),
    ("greenhouse.io", "Greenhouse"),
    ("lever.co", "Lever"),
    ("myworkdayjobs.com", "Workday"),
    ("workday.com", "Workday"),
    ("icims.com", "iCIMS"),
    ("jobvite.com", "Jobvite"),
    ("smartrecruiters.com", "SmartRecruiters"),
    ("ashbyhq.com", "Ashby"),
    ("boards.eu.greenhouse.io", "Greenhouse"),
)


def detect_board(url: str, fallback: str = "Other") -> str:
    try:
        host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return fallback
    for needle, label in BOARD_HOSTS:
        if host == needle or host.endswith("." + needle) or needle in host:
            return label
    return fallback or "Other"


def load_url_status() -> dict:
    path = CACHE / "url_status.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_url_status(status: dict) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "url_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")


def is_listing_url(url: str) -> bool:
    """True for search/list pages (not a single job posting)."""
    lower = url.lower()
    if any(x in lower for x in ("/jobs?", "/jobs/search", "/job-search", "keywords=", "q=business")):
        # Dice job-detail and CareerBuilder job-details are real postings
        if "/job-detail/" in lower or "/job-details/" in lower or "/viewjob" in lower:
            return False
        if re.search(r"/jobs/\d+", lower) or "/remote-jobs/view/" in lower:
            return False
        return True
    return False


def check_job_alive(url: str, status_cache: dict, force: bool = False) -> tuple[bool, str, str]:
    """Returns (include, reason, link_status).
    Drop only when clearly dead. Keep unverified when bots are blocked.
    """
    if not url.startswith("http"):
        return False, "invalid url", "dead"
    if is_listing_url(url):
        return False, "search page, not a job posting", "dead"

    cached = status_cache.get(url)
    if cached and not force:
        age_h = (time.time() - float(cached.get("ts", 0))) / 3600
        if age_h < 24:
            status = cached.get("status") or ("verified" if cached.get("alive") else "dead")
            include = status != "dead"
            return include, cached.get("reason", ""), status

    code, body = http_get_text(url)
    text = re.sub(r"\s+", " ", body.lower())
    reason = "ok"
    status = "verified"

    if code is None:
        # Network flake — keep but mark unverified so the pool isn't emptied
        status, reason = "unverified", "unreachable (kept unverified)"
    elif code in (404, 410):
        status, reason = "dead", f"http {code}"
    elif code == 403 or code == 429:
        status, reason = "unverified", f"http {code} bot block (kept unverified)"
    elif code >= 500:
        status, reason = "unverified", f"http {code} (kept unverified)"
    elif code >= 400:
        status, reason = "dead", f"http {code}"
    else:
        for phrase in DEAD_JOB_PHRASES:
            if phrase in text:
                status, reason = "dead", f"dead: {phrase}"
                break

    status_cache[url] = {
        "alive": status != "dead",
        "status": status,
        "reason": reason,
        "ts": time.time(),
        "code": code,
    }
    return status != "dead", reason, status


def normalize_job(
    *,
    job_id: str,
    title: str,
    company: str,
    url: str,
    source: str,
    location: str = "Remote",
    description: str = "",
    salary: str = "",
    posted: str = "",
) -> dict:
    board = detect_board(url, fallback=source)
    return {
        "id": job_id,
        "title": (title or "").strip(),
        "company": (company or "Unknown").strip(),
        "url": url.strip(),
        "source": source,
        "board": board,
        "location": (location or "Remote").strip(),
        "description": (description or "")[:2500],
        "salary": salary or "",
        "posted": posted or "",
    }


ALLOWED_BOARD_HOSTS = (
    "indeed.com",
    "dice.com",
    "linkedin.com",
    "monster.com",
    "careerbuilder.com",
)


def is_allowed_board_url(url: str) -> bool:
    try:
        host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return False
    return any(host == h or host.endswith("." + h) for h in ALLOWED_BOARD_HOSTS)


def load_board_scrape() -> list[dict]:
    path = CACHE / "board_jobs.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    jobs = []
    for j in data.get("jobs") or []:
        url = (j.get("url") or "").strip()
        if not is_allowed_board_url(url):
            continue
        jobs.append(
            normalize_job(
                job_id=j.get("id") or f"board-{abs(hash(url))}",
                title=j.get("title", ""),
                company=j.get("company", ""),
                url=url,
                source=j.get("board") or j.get("source") or detect_board(url),
                location=j.get("location") or "Remote, USA",
                description=j.get("description") or j.get("snippet") or "",
                salary=j.get("salary") or "",
                posted=j.get("posted") or "",
            )
        )
    return jobs


def run_board_scrape() -> list[dict]:
    """Playwright scrape of Indeed/Dice/LinkedIn/Monster/CareerBuilder only."""
    try:
        from scrape_boards import scrape_with_playwright, OUT

        jobs = scrape_with_playwright()
        payload = {
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
            "query": "business analyst",
            "filters": {"remote": True, "usa": True, "boards": list(ALLOWED_BOARD_HOSTS)},
            "count": len(jobs),
            "jobs": jobs,
        }
        CACHE.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"[scrape] saved {len(jobs)} board jobs")
        return load_board_scrape()
    except Exception as exc:
        print(f"[scrape] failed: {exc}")
        return load_board_scrape()


def seed_jobs() -> list[dict]:
    return []


def score_job(job: dict, strategy: dict) -> tuple[int, list[str], bool]:
    search = strategy["search"]
    text = f"{job.get('title','')} {job.get('company','')} {job.get('location','')} {job.get('description','')}".lower()
    title = (job.get("title") or "").lower()
    reasons: list[str] = []
    score = 0

    hard_exclude = list(search["excludeKeywords"]) + [
        "account executive",
        "sales executive",
        "software engineer",
        "full-stack",
        "fullstack",
        "devops",
        "data scientist",
        "machine learning engineer",
        "nurse ",
        "registered nurse",
    ]
    for bad in hard_exclude:
        if bad.lower() in text:
            return -100, [f"Excluded: {bad}"], True

    remote_hit = any(k in text for k in ("remote", "work from home", "wfh", "telecommute"))
    board_name = (job.get("board") or job.get("source") or "")
    from_remote_board = board_name in ("Indeed", "Dice", "LinkedIn", "Monster", "CareerBuilder")
    if remote_hit or "remote" in (job.get("location") or "").lower():
        score += 35
        reasons.append("Remote signal")
    elif from_remote_board:
        # Scraped from Remote-filtered board search (USA)
        score += 30
        reasons.append("Remote USA board search")
    else:
        score -= 40
        reasons.append("No clear remote signal")

    title_hits = [
        "business analyst",
        "functional analyst",
        "systems analyst",
        "requirements analyst",
        "it business analyst",
        "business systems analyst",
        "process analyst",
    ]
    ba_title = any(t in title for t in title_hits)
    if ba_title:
        score += 40
        reasons.append("Title match")
    elif "analyst" in title and "business" in text:
        score += 18
        reasons.append("Analyst + business context")
    elif "analyst" in title:
        score += 8
        reasons.append("Analyst title")
    else:
        # Non-analyst roles should almost never make the board
        score -= 50
        reasons.append("Not an analyst role")

    for kw in search["boostKeywords"]:
        if kw.lower() in text:
            score += 4
    if any(k in text for k in ("uat", "user acceptance", "requirements", "user stories", "agile", "brd")):
        score += 12
        reasons.append("BA delivery keywords")

    soft_hits = [k for k in search["softExcludeKeywords"] if k.lower() in text]
    if soft_hits and "fully remote" not in text and "100% remote" not in text:
        score -= 20
        reasons.append(f"Hybrid/local caution: {soft_hits[0]}")

    if "servicenow" in text and "business analyst" in title:
        score -= 5
        reasons.append("ServiceNow stretch")

    # Hard require BA-core titles (not generic "Analyst II", CX analyst, etc.)
    if not ba_title:
        return score, reasons[:6], True
    if any(t in title for t in ("deal desk", "sales compensation", "revenue operations", "analyst relations")):
        return score, reasons[:6], True

    return score, reasons[:6], False


def dedupe(jobs: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out = []
    for j in jobs:
        key = re.sub(r"\W+", "", f"{j['title']}{j['company']}".lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(j)
    return out


def applied_ids(apps: list[dict]) -> set[str]:
    return {a["jobId"] for a in apps if a.get("status") in ("applied", "skipped", "interviewing", "offer")}


def collect_jobs(strategy: dict, force: bool = False) -> list[dict]:
    today = date.today().isoformat()
    cache_file = CACHE / f"jobs-{today}.json"
    if cache_file.exists() and not force:
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if cached.get("jobs"):
                return cached["jobs"]
        except json.JSONDecodeError:
            pass

    # Only Indeed / Dice / LinkedIn / Monster / CareerBuilder
    if force or not (CACHE / "board_jobs.json").exists():
        collected = run_board_scrape()
    else:
        collected = load_board_scrape()
        # Refresh scrape if cache older than ~18 hours
        try:
            meta = json.loads((CACHE / "board_jobs.json").read_text(encoding="utf-8"))
            fetched = meta.get("fetchedAt") or ""
            if fetched:
                age_h = (
                    datetime.now(timezone.utc)
                    - datetime.fromisoformat(fetched.replace("Z", "+00:00"))
                ).total_seconds() / 3600
                if age_h > 18:
                    collected = run_board_scrape()
        except Exception:
            pass

    collected = [j for j in collected if is_allowed_board_url(j.get("url", ""))]
    collected = dedupe(collected)

    scored = []
    for j in collected:
        # Force USA + remote context for scoring text
        loc = (j.get("location") or "").lower()
        if any(x in loc for x in ("india", "uk", "canada", "poland", "philippines", "mexico")) and "united states" not in loc and "usa" not in loc and "u.s" not in loc:
            continue
        s, reasons, excluded = score_job(j, strategy)
        if excluded or s < 40:
            continue
        # Remote required
        blob = f"{j.get('title','')} {j.get('location','')} {j.get('description','')}".lower()
        if "remote" not in blob and "work from home" not in blob and "wfh" not in blob:
            # Board search was remote-filtered — still require explicit remote in location/title when possible
            if "remote" not in loc:
                s -= 15
                reasons = list(reasons) + ["Remote assumed from board filter"]
        j = dict(j)
        j["board"] = detect_board(j["url"], fallback=j.get("source", "Other"))
        if j["board"] not in ("Indeed", "Dice", "LinkedIn", "Monster", "CareerBuilder"):
            continue
        j["score"] = s
        j["reasons"] = reasons[:6]
        scored.append(j)

    scored.sort(key=lambda x: (-x["score"], x["title"]))

    status_cache = load_url_status()
    live: list[dict] = []
    dropped = 0
    for j in scored[:60]:
        include, reason, link_status = check_job_alive(j["url"], status_cache, force=force)
        if not include:
            dropped += 1
            print(f"[link-check] drop {j['title'][:50]} ({j['board']}): {reason}")
            continue
        # Re-confirm host after redirects is still allowed — check original URL host
        if not is_allowed_board_url(j["url"]):
            dropped += 1
            continue
        j["linkStatus"] = link_status
        live.append(j)
    save_url_status(status_cache)

    live.sort(key=lambda x: (-x["score"], x["title"]))
    cache_file.write_text(
        json.dumps(
            {
                "fetchedAt": datetime.now(timezone.utc).isoformat(),
                "jobs": live,
                "droppedDead": dropped,
                "boardsOnly": list(ALLOWED_BOARD_HOSTS),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return live


def build_daily_batch(strategy: dict, force: bool = False) -> dict:
    today = date.today().isoformat()
    if DAILY_FILE.exists() and not force:
        try:
            existing = json.loads(DAILY_FILE.read_text(encoding="utf-8"))
            if existing.get("date") == today and existing.get("jobs"):
                return existing
        except json.JSONDecodeError:
            pass

    apps = load_apps()
    done = applied_ids(apps)
    all_jobs = collect_jobs(strategy, force=force)
    available = [j for j in all_jobs if j["id"] not in done]
    size = int(strategy["search"].get("dailyBatchSize", 20))
    # Diversify across boards (Indeed/Dice/LinkedIn/Monster/CareerBuilder)
    by_board: dict[str, list] = {}
    for j in available:
        by_board.setdefault(j.get("board") or "Other", []).append(j)
    batch: list[dict] = []
    order = ("Indeed", "Dice", "LinkedIn", "Monster", "CareerBuilder")
    while len(batch) < size and any(by_board.values()):
        progressed = False
        for board in order:
            bucket = by_board.get(board) or []
            if not bucket:
                continue
            batch.append(bucket.pop(0))
            progressed = True
            if len(batch) >= size:
                break
        if not progressed:
            break
    if not batch:
        batch = all_jobs[:size]
    batch.sort(key=lambda x: -x["score"])

    payload = {
        "date": today,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "jobs": batch,
        "poolSize": len(all_jobs),
        "remaining": len(available),
        "boardsInPool": sorted({j.get("board") for j in all_jobs if j.get("board")}),
    }
    DAILY_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def board_links(strategy: dict) -> list[dict]:
    """Board chips: always business analyst + Remote (exact URLs from strategy)."""
    links = []
    primary = strategy["search"]["queries"][0]
    q_plus = urllib.parse.quote_plus(primary)  # business+analyst
    q_pct = urllib.parse.quote(primary)  # business%20analyst
    for key, board in strategy["boards"].items():
        url = board.get("url") or board.get("searchUrl", "")
        if "{query}" in url:
            # LinkedIn prefers %20; most boards prefer +
            repl = q_pct if key == "linkedin" else q_plus
            url = url.format(query=repl)
        links.append({"id": key, "label": board["label"], "url": url})
    return links


def kpis(strategy: dict, apps: list[dict]) -> dict:
    applied = [a for a in apps if a.get("status") == "applied"]
    interviewing = [a for a in apps if a.get("status") == "interviewing"]
    today = date.today().isoformat()
    applied_today = [a for a in applied if (a.get("at") or "").startswith(today)]
    return {
        "appliedTotal": len(applied),
        "appliedToday": len(applied_today),
        "interviewing": len(interviewing),
        "targetTotal": strategy["search"]["totalApplyTarget"],
        "targetWeekly": strategy["search"]["weeklyApplyTarget"],
        "dailyBatchSize": strategy["search"]["dailyBatchSize"],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"[http] {self.address_string()} {fmt % args}")

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code: int, payload: dict | list) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        strategy = load_strategy()

        if path == "/api/health":
            return self._json(200, {"ok": True, "date": date.today().isoformat()})

        if path == "/api/strategy":
            return self._json(200, strategy)

        if path == "/api/board-links":
            return self._json(200, {"boards": board_links(strategy)})

        if path == "/api/cover-blurb":
            return self._json(200, {"blurb": strategy["coverBlurb"]})

        if path == "/api/applications":
            return self._json(200, {"applications": load_apps()})

        if path == "/api/kpis":
            return self._json(200, kpis(strategy, load_apps()))

        if path == "/api/jobs/daily":
            force = qs.get("force", ["0"])[0] in ("1", "true", "yes")
            batch = build_daily_batch(strategy, force=force)
            apps = load_apps()
            status_by_id = {a["jobId"]: a.get("status") for a in apps}
            for j in batch["jobs"]:
                j["applicationStatus"] = status_by_id.get(j["id"])
            batch["kpis"] = kpis(strategy, apps)
            batch["boards"] = board_links(strategy)
            batch["coverBlurb"] = strategy["coverBlurb"]
            batch["candidate"] = strategy["candidate"]
            return self._json(200, batch)

        if path == "/" or path.startswith("/static/") or path in ("/app.js", "/styles.css"):
            return self._serve_static(path)

        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "invalid json"})

        strategy = load_strategy()

        if parsed.path == "/api/jobs/refresh":
            batch = build_daily_batch(strategy, force=True)
            return self._json(200, batch)

        if parsed.path == "/api/applications":
            job_id = body.get("jobId")
            status = body.get("status") or "applied"
            if not job_id:
                return self._json(400, {"error": "jobId required"})
            apps = load_apps()
            apps = [a for a in apps if a.get("jobId") != job_id]
            record = {
                "jobId": job_id,
                "status": status,
                "title": body.get("title", ""),
                "company": body.get("company", ""),
                "url": body.get("url", ""),
                "source": body.get("source", ""),
                "at": datetime.now(timezone.utc).isoformat(),
                "note": body.get("note", ""),
            }
            apps.insert(0, record)
            save_apps(apps)
            return self._json(200, {"ok": True, "application": record, "kpis": kpis(strategy, apps)})

        self._json(404, {"error": "not found"})

    def _serve_static(self, path: str) -> None:
        if path == "/":
            file_path = STATIC / "index.html"
        elif path.startswith("/static/"):
            file_path = STATIC / path[len("/static/") :]
        else:
            file_path = STATIC / path.lstrip("/")

        file_path = file_path.resolve()
        if not str(file_path).startswith(str(STATIC.resolve())) or not file_path.is_file():
            return self._json(404, {"error": "file not found"})

        data = file_path.read_bytes()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
        }.get(file_path.suffix, "application/octet-stream")
        self._bytes(200, data, ctype)


def main() -> None:
    ensure_dirs()
    strategy = load_strategy()
    print(f"Building first daily batch for {strategy['candidate']['name']}...")
    # Warm cache in background so first page load is fast
    threading.Thread(target=lambda: build_daily_batch(strategy, force=False), daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Maryiam Daily Jobs -> http://127.0.0.1:{PORT}/")
    print("Apply opens the employer/board URL. Tracking stays local in data/applications.json")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    main()
