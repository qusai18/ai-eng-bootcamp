"""
Scrape remote USA Business Analyst jobs from:
Indeed, Dice, LinkedIn, Monster, CareerBuilder only.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "data" / "cache"
OUT = CACHE / "board_jobs.json"

ALLOWED_HOSTS = (
    "indeed.com",
    "dice.com",
    "linkedin.com",
    "monster.com",
    "careerbuilder.com",
)

SEARCHES = [
    {
        "board": "Indeed",
        "url": "https://www.indeed.com/jobs?q=business+analyst&l=Remote&fromage=7&sort=date",
    },
    {
        "board": "Dice",
        "url": "https://www.dice.com/jobs?q=business+analyst&location=Remote&countryCode=US&radius=30&radiusUnit=mi&page=1&pageSize=20&filters.workplaceTypes=Remote&language=en",
    },
    {
        "board": "LinkedIn",
        "url": "https://www.linkedin.com/jobs/search/?keywords=business%20analyst&location=United%20States&f_WT=2&f_TPR=r604800",
    },
    {
        "board": "Monster",
        "url": "https://www.monster.com/jobs/search?q=business+analyst&where=Remote&page=1",
    },
    {
        "board": "CareerBuilder",
        "url": "https://www.careerbuilder.com/jobs?keywords=business+analyst&location=Remote",
    },
]

ANALYST_TITLE = re.compile(
    r"business\s+analyst|functional\s+analyst|systems?\s+analyst|requirements\s+analyst|"
    r"business\s+systems\s+analyst|data\s+analyst|bi\s+analyst|"
    r"qa\s+analyst|quality\s+assurance\s+analyst|quality\s+analyst",
    re.I,
)
BA_TITLE = ANALYST_TITLE
REMOTE_OK = re.compile(r"remote|work from home|wfh|telecommut", re.I)
NON_USA = re.compile(
    r"\b(india|bangalore|hyderabad|pune|chennai|toronto|canada|uk|united kingdom|london|poland|romania|philippines|mexico city)\b",
    re.I,
)


def allowed_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return False
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


def normalize_indeed(url: str) -> str:
    """Prefer stable viewjob links when jk is present."""
    try:
        p = urlparse(url)
        if "indeed.com" not in p.netloc:
            return url
        qs = parse_qs(p.query)
        jk = (qs.get("jk") or qs.get("vjk") or [None])[0]
        if jk:
            return f"https://www.indeed.com/viewjob?jk={jk}"
        if "/viewjob" in p.path:
            return url.split("&")[0] if "?" in url else url
    except Exception:
        pass
    return url.split("#")[0]


def clean_job(raw: dict) -> dict | None:
    title = (raw.get("title") or "").strip()
    company = (raw.get("company") or "").strip() or "Unknown"
    url = (raw.get("url") or "").strip()
    location = (raw.get("location") or "").strip()
    board = raw.get("board") or ""
    if not title or not url:
        return None
    if not allowed_url(url):
        return None
    if not ANALYST_TITLE.search(title):
        return None
    blob = f"{title} {location} {raw.get('snippet') or ''}"
    if NON_USA.search(location) and not re.search(r"\b(USA|United States|U\.S\.|US-)\b", location, re.I):
        # location clearly foreign
        if not re.search(r"\b(remote\s*[-,]?\s*usa|usa\s*[-,]?\s*remote|united states)\b", blob, re.I):
            return None
    if location and not REMOTE_OK.search(blob) and "remote" not in location.lower():
        # still allow if board search was remote-filtered
        if board not in ("Indeed", "Dice", "Monster", "CareerBuilder", "LinkedIn"):
            return None
    url = normalize_indeed(url)
    if not url.startswith("http"):
        return None
    return {
        "id": f"{board.lower()}-{abs(hash(url + title))}",
        "title": title,
        "company": company,
        "url": url,
        "source": board,
        "board": board,
        "location": location or "Remote, USA",
        "description": (raw.get("snippet") or "")[:2000],
        "salary": raw.get("salary") or "",
        "posted": raw.get("posted") or "",
    }


def load_searches() -> list[dict]:
    """Prefer strategy.json so Indeed, Dice, Monster, and CareerBuilder are all searched."""
    path = ROOT / "strategy.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        searches = [s for s in (data.get("searches") or []) if s.get("board") != "LinkedIn" and s.get("url")]
        if searches:
            return searches
    except (OSError, json.JSONDecodeError):
        pass
    return [s for s in SEARCHES if s.get("board") != "LinkedIn"]


def scrape_with_playwright() -> list[dict]:
    from playwright.sync_api import sync_playwright

    from google_auth import authenticate_boards

    collected: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            geolocation={"longitude": -76.86, "latitude": 39.27},  # MD
            permissions=["geolocation"],
        )
        page = context.new_page()
        page.set_default_timeout(12000)
        page.set_default_navigation_timeout(30000)
        searches = load_searches()
        print(f"[scrape] {len(searches)} searches across Indeed, Dice, Monster, CareerBuilder", flush=True)

        for spec in searches:
            board = spec["board"]
            url = spec["url"]
            print(f"[scrape] {board}: {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(2500)
                for label in ("Accept all", "Accept All Cookies", "Accept All", "Agree", "Got it", "Reject all", "Allow all"):
                    try:
                        page.get_by_role("button", name=re.compile(label, re.I)).first.click(timeout=1500)
                        page.wait_for_timeout(600)
                    except Exception:
                        pass
                # Extra wait for JS job cards
                try:
                    if board == "Indeed":
                        page.wait_for_selector("a[data-jk], h2.jobTitle a, .job_seen_beacon", timeout=12000)
                    elif board == "Dice":
                        page.wait_for_selector("a[href*='/job-detail/']", timeout=12000)
                    elif board == "LinkedIn":
                        page.wait_for_selector("a.base-card__full-link, a[href*='/jobs/view/']", timeout=12000)
                    elif board == "Monster":
                        page.wait_for_selector("a[href*='job-openings'], [class*='JobCard']", timeout=12000)
                    elif board == "CareerBuilder":
                        page.wait_for_selector("a[href*='/job/'], a[href*='job-details']", timeout=12000)
                except Exception:
                    page.wait_for_timeout(4000)
                page.mouse.wheel(0, 2400)
                page.wait_for_timeout(1500)

                jobs = page.evaluate(
                    """(board) => {
                      const out = [];
                      const push = (title, company, href, location, salary, snippet) => {
                        if (!title || !href) return;
                        out.push({
                          board,
                          title: title.trim(),
                          company: (company || '').trim(),
                          url: href,
                          location: (location || '').trim(),
                          salary: (salary || '').trim(),
                          snippet: (snippet || '').trim().slice(0, 500),
                        });
                      };

                      if (board === 'Indeed') {
                        const cards = document.querySelectorAll('[data-jk], .job_seen_beacon, .cardOutline, li.css-5lfssg, .resultContent');
                        cards.forEach(card => {
                          const jk = card.getAttribute('data-jk') || card.querySelector('[data-jk]')?.getAttribute('data-jk');
                          const a = card.querySelector('h2.jobTitle a, a.jcs-JobTitle, a[id^="sj_"], a[id^="job_"]') || card.querySelector('a[href*="jk="]');
                          const title = (a?.innerText || a?.getAttribute('aria-label') || card.querySelector('h2')?.innerText || '').replace(/^new\\s+/i,'').trim();
                          const company = card.querySelector('[data-testid="company-name"], .companyName, span[data-testid="company-name"]')?.innerText || '';
                          const location = card.querySelector('[data-testid="text-location"], .companyLocation')?.innerText || 'Remote';
                          const salary = card.querySelector('.salary-snippet-container, .estimated-salary')?.innerText || '';
                          let href = a?.href || '';
                          if (jk) href = 'https://www.indeed.com/viewjob?jk=' + jk;
                          push(title, company, href, location, salary, card.innerText || '');
                        });
                        // fallback: any viewjob / jk links
                        if (out.length === 0) {
                          document.querySelectorAll('a[href*="jk="], a[data-jk]').forEach(a => {
                            const jk = a.getAttribute('data-jk') || new URL(a.href, location.origin).searchParams.get('jk');
                            const title = (a.innerText || a.getAttribute('aria-label') || '').trim();
                            if (!jk || !title) return;
                            push(title, '', 'https://www.indeed.com/viewjob?jk=' + jk, 'Remote', '', '');
                          });
                        }
                      }

                      if (board === 'Dice') {
                        document.querySelectorAll('a[href*="/job-detail/"]').forEach(a => {
                          const card = a.closest('[data-cy="search-card"], article, li, div') || a.parentElement;
                          const title = (a.innerText || '').trim();
                          let company = '';
                          const companyEl = card?.querySelector('[data-cy="companyName"], a[href*="/company-profile/"], a[href*="/company/"]');
                          company = companyEl?.innerText || '';
                          const location = (card?.innerText || '').match(/Remote[^\\n]{0,40}/)?.[0] || 'Remote';
                          push(title, company, a.href, location, '', card?.innerText || '');
                        });
                      }

                      if (board === 'LinkedIn') {
                        document.querySelectorAll('a.base-card__full-link, a[href*="/jobs/view/"]').forEach(a => {
                          const card = a.closest('li, div.base-card, div.job-search-card') || a.parentElement;
                          const title = (card?.querySelector('h3, .base-search-card__title')?.innerText || a.innerText || '').trim();
                          const company = (card?.querySelector('h4, .base-search-card__subtitle, .base-search-card__subtitle a')?.innerText || '').trim();
                          const location = (card?.querySelector('.job-search-card__location, .base-search-card__metadata')?.innerText || 'United States').trim();
                          let href = a.href.split('?')[0];
                          push(title, company, href, location, '', '');
                        });
                      }

                      if (board === 'Monster') {
                        document.querySelectorAll('a[href*="job-openings"], a[href*="/job/"], a[data-testid*="jobTitle"], a[data-testid*="JobTitle"]').forEach(a => {
                          const card = a.closest('article, li, div') || a.parentElement;
                          const title = (a.innerText || card?.querySelector('h2, h3')?.innerText || '').trim();
                          const company = (card?.querySelector('[data-testid="company"], [class*="Company"]')?.innerText || '').trim();
                          const location = (card?.innerText || '').match(/Remote[^\\n]{0,40}/)?.[0] || 'Remote';
                          if (title.length < 4) return;
                          push(title, company, a.href, location, '', card?.innerText || '');
                        });
                      }

                      if (board === 'CareerBuilder') {
                        document.querySelectorAll('a[href*="careerbuilder.com"]').forEach(a => {
                          const href = a.href;
                          if (!/careerbuilder\\.com\\/(job\\/|jobs\\/|job-details)/i.test(href)) return;
                          if (/\\/jobs\\?/.test(href)) return;
                          const title = (a.innerText || '').trim();
                          if (title.length < 8 || title.length > 160) return;
                          const card = a.closest('li, article, div') || a.parentElement;
                          const company = (card?.querySelector('[class*="company"]')?.innerText || '').trim();
                          const location = (card?.innerText || '').match(/Remote[^\\n]{0,40}/)?.[0] || 'Remote';
                          push(title, company, href, location, '', card?.innerText || '');
                        });
                      }

                      if (out.length === 0) {
                        const hrefOk = (href) => {
                          if (board === 'Indeed') return /indeed\\.com\\/(viewjob|rc\\/clk)|[?&]jk=/.test(href);
                          if (board === 'Dice') return /job-detail\\//.test(href);
                          if (board === 'Monster') return /job-opening|\\/job\\//i.test(href);
                          if (board === 'CareerBuilder') return /\\/job\\/|job-details/i.test(href);
                          return false;
                        };
                        document.querySelectorAll('a[href]').forEach(a => {
                          const href = a.href || '';
                          if (!hrefOk(href)) return;
                          const title = (a.innerText || a.getAttribute('aria-label') || '').trim();
                          if (title.length < 4 || title.length > 180) return;
                          const card = a.closest('article, li, div');
                          push(title, '', href, '', '', card?.innerText || '');
                        });
                      }

                      const seen = new Set();
                      return out.filter(j => {
                        const u = (j.url || '').split('#')[0];
                        if (!u || seen.has(u + j.title)) return false;
                        seen.add(u + j.title);
                        return true;
                      });
                    }""",
                    board,
                )
                print(f"[scrape] {board}: raw {len(jobs)}")
                for j in jobs:
                    cleaned = clean_job(j)
                    if cleaned:
                        collected.append(cleaned)
            except Exception as exc:
                print(f"[scrape] {board} failed: {exc}")
            time.sleep(1.2)

        # Sign-in runs after the listings are collected so a stuck Google
        # page cannot hide Indeed, Monster, or CareerBuilder.
        try:
            page.set_default_timeout(8000)
            page.set_default_navigation_timeout(15000)
            auth_results = authenticate_boards(page)
            CACHE.mkdir(parents=True, exist_ok=True)
            (CACHE / "auth_status.json").write_text(
                json.dumps({"checkedAt": datetime.now(timezone.utc).isoformat(), "boards": auth_results}, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            print(f"[auth] skipped: {type(exc).__name__}", flush=True)

        browser.close()

    # dedupe
    seen = set()
    unique = []
    for j in collected:
        key = re.sub(r"\W+", "", f"{j['title']}{j['company']}{j['board']}".lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(j)
    return unique


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    jobs = scrape_with_playwright()
    payload = {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "query": "business analyst",
        "filters": {"remote": True, "usa": True, "boards": list(ALLOWED_HOSTS)},
        "count": len(jobs),
        "jobs": jobs,
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[scrape] wrote {len(jobs)} jobs -> {OUT}")
    for j in jobs[:12]:
        print(f"  [{j['board']}] {j['title']} @ {j['company']}")


if __name__ == "__main__":
    main()
