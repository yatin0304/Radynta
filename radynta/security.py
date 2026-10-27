"""CSRF protection, login guard, spam protection and simple rate limiting."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import abort, current_app, g, redirect, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

# ------------------------------------------------------------------ CSRF ---

def csrf_token() -> str:
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def verify_csrf() -> None:
    if request.method != "POST":
        return
    sent = request.form.get("csrf_token", "")
    expected = session.get("_csrf", "")
    if not expected or not hmac.compare_digest(sent, expected):
        abort(400, description="Your session expired or the form was tampered with. Please reload the page and try again.")


# ----------------------------------------------------------------- login ---

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("monitor.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


# --------------------------------------------------- form spam protection ---

def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="form-timer")


def form_timer_token() -> str:
    return _serializer().dumps({"t": time.time()})


def check_spam(form, min_seconds: float = 3.0, max_age: int = 7200) -> str | None:
    """Return a reason string if the submission looks automated, else None."""
    if form.get("company_website"):          # honeypot: hidden from humans
        return "honeypot"
    token = form.get("form_ts", "")
    try:
        data = _serializer().loads(token, max_age=max_age)
    except SignatureExpired:
        return "expired"
    except BadSignature:
        return "bad-token"
    if time.time() - float(data.get("t", 0)) < min_seconds:
        return "too-fast"
    return None


# ------------------------------------------------------------ rate limit ---

class RateLimiter:
    """In-memory sliding window. Per-process only: fine for a single small server.
    Use a shared store (e.g. Redis) if you run multiple workers/instances."""

    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def client_key(scope: str) -> str:
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip() \
        if current_app.config.get("TRUST_PROXY") else (request.remote_addr or "?")
    digest = hashlib.sha256(f"{scope}:{ip}".encode()).hexdigest()[:24]  # don't keep raw IPs in memory keys
    return digest


def rate_limited(scope: str, limit: int, window: int) -> bool:
    return not limiter.allow(client_key(scope), limit, window)


def current_user_email() -> str | None:
    return g.get("user_email")
