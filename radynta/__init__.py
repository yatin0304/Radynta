"""RADYNTA — logistics AEO agency website + internal AI visibility monitor."""
from __future__ import annotations

from pathlib import Path

from flask import Flask, g, has_request_context, redirect, render_template, request

from . import db as dbmod
from .config import Settings, load_settings
from .security import csrf_token, form_timer_token, verify_csrf

__version__ = "0.1.0"


def get_db():
    from flask import current_app

    if "db" not in g:
        g.db = dbmod.connect(current_app.config["SETTINGS"].database_path)
    return g.db


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or load_settings()
    app = Flask(__name__, instance_path=str(Path(settings.database_path).parent.resolve()) if str(settings.database_path) != ":memory:" else None)
    app.config.update(
        SETTINGS=settings,
        SECRET_KEY=settings.secret_key,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=settings.is_production,
        MAX_CONTENT_LENGTH=256 * 1024,
        TRUST_PROXY=settings.is_production,
        TESTING=settings.env == "test",
    )
    if settings.is_production:
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    with app.app_context():
        conn = get_db()
        dbmod.init_schema(conn)

    @app.teardown_appcontext
    def _close_db(_exc):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    @app.before_request
    def _canonical_host_redirect():
        host = (request.host or "").split(":")[0].lower()
        if host in settings.redirect_hosts and host != settings.canonical_host:
            qs = request.query_string.decode("utf-8", "ignore")
            target = f"https://{settings.canonical_host}{request.path}" + (f"?{qs}" if qs else "")
            return redirect(target, code=301)
        return None

    app.before_request(verify_csrf)

    @app.after_request
    def _security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; script-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'",
        )
        if settings.is_production:
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.path.startswith("/monitor"):
            resp.headers["Cache-Control"] = "no-store"
            resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        return resp

    app.jinja_env.globals.update(csrf_token=csrf_token, form_timer_token=form_timer_token)

    @app.context_processor
    def _inject():
        path = request.path if has_request_context() else "/"
        return {
            "settings": settings,
            "canonical_url": settings.site_url + path,
            "current_path": path,
        }

    from .monitor.routes import bp as monitor_bp
    from .site.routes import bp as site_bp

    app.register_blueprint(site_bp)
    app.register_blueprint(monitor_bp, url_prefix="/monitor")

    @app.errorhandler(404)
    def _not_found(_e):
        return render_template("site/404.html", page={"title": "Page not found", "description": "", "noindex": True}), 404

    @app.errorhandler(400)
    def _bad_request(e):
        return render_template("site/error.html", page={"title": "Request could not be processed", "noindex": True},
                               message=getattr(e, "description", "Bad request")), 400

    @app.errorhandler(429)
    def _too_many(_e):
        return render_template("site/error.html", page={"title": "Too many requests", "noindex": True},
                               message="Too many submissions from your network. Please wait a few minutes and try again."), 429

    from .cli import register_cli

    register_cli(app)
    return app
