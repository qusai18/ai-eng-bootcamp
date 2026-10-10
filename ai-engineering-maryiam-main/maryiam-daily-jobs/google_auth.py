"""
Sign in to Indeed, Dice, Monster, and CareerBuilder with Yusuf's Google account.

Credentials come from GOOGLE_USERNAME and GOOGLE_PASSWORD (Render env, or the
gitignored repo-root .env). The password is never written to logs.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from env_local import google_credentials

LOGIN_PAGES = (
    {
        "board": "Indeed",
        "url": "https://secure.indeed.com/account/login",
    },
    {
        "board": "Dice",
        "url": "https://www.dice.com/dashboard/login",
    },
    {
        "board": "Monster",
        "url": "https://www.monster.com/profile/sign-in",
    },
    {
        "board": "CareerBuilder",
        "url": "https://www.careerbuilder.com/user/login",
    },
)

CHALLENGE = re.compile(
    r"verify it.?s you|2-step|two-step|check your phone|enter the code|captcha|unusual activity|couldn.?t sign you in",
    re.I,
)


def _click_google(page) -> bool:
    for label in ("Continue with Google", "Sign in with Google", "Log in with Google", "Google"):
        try:
            page.get_by_role("button", name=re.compile(rf"^{label}$", re.I)).first.click(timeout=4000)
            return True
        except Exception:
            pass
        try:
            page.get_by_role("link", name=re.compile(label, re.I)).first.click(timeout=2500)
            return True
        except Exception:
            pass
    try:
        clicked = page.evaluate(
            """() => {
              const nodes = [...document.querySelectorAll('button, a, [role="button"]')];
              const hit = nodes.find(el => /google/i.test(el.innerText || el.getAttribute('aria-label') || ''));
              if (!hit) return false;
              hit.click();
              return true;
            }"""
        )
        return bool(clicked)
    except Exception:
        return False


def _google_password_step(page, username: str, password: str) -> str:
    """Complete accounts.google.com email + password. Returns ok, challenge, or failed."""
    page.wait_for_timeout(1500)
    if "accounts.google.com" not in (page.url or ""):
        try:
            page.wait_for_url(re.compile(r"accounts\.google\.com"), timeout=12000)
        except Exception:
            return "failed"

    try:
        email = page.locator('input[type="email"]')
        if email.count() and email.first.is_visible():
            email.first.fill(username)
            page.locator("#identifierNext").click(timeout=5000)
            page.wait_for_timeout(1500)
    except Exception:
        return "failed"

    body = ""
    try:
        body = page.inner_text("body")
    except Exception:
        body = ""
    if CHALLENGE.search(body):
        return "challenge"

    try:
        passwd = page.locator('input[type="password"]')
        passwd.first.wait_for(state="visible", timeout=10000)
        passwd.first.fill(password)
        page.locator("#passwordNext").click(timeout=5000)
    except Exception:
        try:
            body = page.inner_text("body")
        except Exception:
            body = ""
        if CHALLENGE.search(body):
            return "challenge"
        return "failed"

    page.wait_for_timeout(2500)
    try:
        body = page.inner_text("body")
    except Exception:
        body = ""
    if CHALLENGE.search(body) or "challenge" in (page.url or ""):
        return "challenge"
    if "accounts.google.com" in (page.url or "") and "signin" in (page.url or ""):
        return "failed"
    return "ok"


def sign_in_board(page, board: str, login_url: str, username: str, password: str) -> dict:
    started = datetime.now(timezone.utc).isoformat()
    result = {"board": board, "status": "failed", "at": started, "detail": ""}
    try:
        page.goto(login_url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1200)
        for label in ("Accept all", "Accept All Cookies", "Accept All", "Agree", "Got it"):
            try:
                page.get_by_role("button", name=re.compile(label, re.I)).first.click(timeout=1200)
            except Exception:
                pass
        if not _click_google(page):
            result["detail"] = "Google button not found"
            return result
        status = _google_password_step(page, username, password)
        result["status"] = status
        if status == "ok":
            result["detail"] = "Signed in with Google"
        elif status == "challenge":
            result["detail"] = "Google asked for an extra check (2-step or captcha). Sign-in stopped."
        else:
            result["detail"] = "Google sign-in did not finish"
    except Exception as exc:
        result["detail"] = f"Sign-in error: {type(exc).__name__}"
    return result


def authenticate_boards(page) -> list[dict]:
    username, password = google_credentials()
    if not username or not password:
        return [
            {
                "board": spec["board"],
                "status": "missing_credentials",
                "at": datetime.now(timezone.utc).isoformat(),
                "detail": "GOOGLE_USERNAME or GOOGLE_PASSWORD is not set",
            }
            for spec in LOGIN_PAGES
        ]
    results = []
    for spec in LOGIN_PAGES:
        print(f"[auth] {spec['board']}: Google sign-in", flush=True)
        results.append(sign_in_board(page, spec["board"], spec["url"], username, password))
        print(f"[auth] {spec['board']}: {results[-1]['status']}", flush=True)
    return results
