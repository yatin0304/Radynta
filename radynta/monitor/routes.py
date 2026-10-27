"""Internal AI Visibility Monitor (login required)."""
from __future__ import annotations

import threading
from datetime import datetime, timezone

from flask import (Blueprint, Response, abort, current_app, flash, g, redirect, render_template, request, session,
                   url_for)
from werkzeug.security import check_password_hash

from .. import db as dbmod
from .. import get_db
from ..audit.pipeline import run_site_audit, score_and_store
from ..reports.report_builder import build_report, export_csv
from ..security import login_required, rate_limited
from ..visibility.metrics import batch_metrics, compare, previous_batch

bp = Blueprint("monitor", __name__, template_folder="../templates")

EXPORT_KINDS = ("findings", "recommendations", "pages", "visibility")


@bp.before_request
def _load_user():
    uid = session.get("user_id")
    if uid:
        user = dbmod.one(get_db(), "SELECT id, email FROM users WHERE id=?", (uid,))
        if user is None:
            session.clear()
        else:
            g.user_email = user["email"]


def _client_or_404(slug):
    c = dbmod.client_by_slug(get_db(), slug)
    if c is None:
        abort(404)
    return c


def _owned_or_404(table, row_id, client_id):
    row = dbmod.owned(get_db(), table, row_id, client_id)
    if row is None:
        abort(404)
    return row


# --------------------------------------------------------------- auth ---

@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if rate_limited("login", limit=10, window=900):
            abort(429)
        email = (request.form.get("email") or "").strip().lower()
        user = dbmod.one(get_db(), "SELECT * FROM users WHERE email=?", (email,))
        if user and check_password_hash(user["password_hash"], request.form.get("password") or ""):
            session.clear()
            session["user_id"] = user["id"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/monitor") and "//" not in nxt else url_for("monitor.dashboard"))
        error = "Email or password is incorrect."
    has_users = dbmod.one(get_db(), "SELECT 1 FROM users LIMIT 1") is not None
    return render_template("monitor/login.html", error=error, has_users=has_users), (401 if error else 200)


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("monitor.login"))


# ----------------------------------------------------------- dashboard ---

@bp.get("/")
@login_required
def dashboard():
    conn = get_db()
    clients = []
    for c in dbmod.rows(conn, "SELECT * FROM clients ORDER BY is_sample, name"):
        audit = dbmod.one(conn, "SELECT * FROM site_audits WHERE client_id=? ORDER BY id DESC LIMIT 1", (c["id"],))
        score = (dbmod.loads(audit["score_json"], {}) or {}) if audit else {}
        batch = dbmod.one(conn, "SELECT * FROM visibility_batches WHERE client_id=? AND status='completed' ORDER BY started_at DESC, id DESC LIMIT 1", (c["id"],))
        clients.append({"c": c, "audit": audit, "score": score.get("normalized"), "measured": score.get("measured_possible"),
                        "batch": batch, "metrics": batch_metrics(conn, c["id"], batch["id"]) if batch else None,
                        "prompts": dbmod.one(conn, "SELECT COUNT(*) n FROM prompts WHERE client_id=? AND active=1", (c["id"],))["n"]})
    new_enquiries = dbmod.one(conn, "SELECT COUNT(*) n FROM enquiries WHERE status='new'")["n"]
    s = current_app.config["SETTINGS"]
    return render_template("monitor/dashboard.html", clients=clients, new_enquiries=new_enquiries,
                           providers={"Perplexity API": bool(s.perplexity_api_key),
                                      "OpenAI API (web search)": bool(s.openai_api_key and s.openai_model)},
                           email_configured=s.email_configured)


@bp.get("/enquiries")
@login_required
def enquiries():
    status = request.args.get("status")
    sql, params = "SELECT * FROM enquiries", []
    if status:
        sql += " WHERE status=?"
        params.append(status)
    items = dbmod.rows(get_db(), sql + " ORDER BY created_at DESC LIMIT 500", params)
    return render_template("monitor/enquiries.html", items=items, status=status,
                           email_configured=current_app.config["SETTINGS"].email_configured)


@bp.post("/enquiries/<int:eid>")
@login_required
def enquiry_update(eid):
    status = request.form.get("status")
    if status not in ("new", "contacted", "qualified", "closed", "spam"):
        abort(400)
    conn = get_db()
    conn.execute("UPDATE enquiries SET status=?, internal_notes=? WHERE id=?",
                 (status, (request.form.get("internal_notes") or "")[:4000], eid))
    conn.commit()
    return redirect(url_for("monitor.enquiries"))


# -------------------------------------------------------------- clients ---

@bp.get("/clients/<slug>")
@login_required
def client(slug):
    c = _client_or_404(slug)
    conn = get_db()
    cfg = dbmod.client_config(conn, c["id"])
    audits = [dict(a) | {"score": (dbmod.loads(a["score_json"], {}) or {}).get("normalized")}
              for a in dbmod.rows(conn, "SELECT * FROM site_audits WHERE client_id=? ORDER BY id DESC", (c["id"],))]
    batches = []
    for b in dbmod.rows(conn, "SELECT * FROM visibility_batches WHERE client_id=? ORDER BY started_at DESC, id DESC", (c["id"],)):
        m = batch_metrics(conn, c["id"], b["id"])
        prev = previous_batch(conn, c["id"], b) if b["status"] == "completed" else None
        batches.append({"b": b, "m": m, "delta": compare(m, batch_metrics(conn, c["id"], prev["id"])) if prev else None})
    prompts = dbmod.rows(conn, "SELECT * FROM prompts WHERE client_id=? ORDER BY active DESC, id", (c["id"],))
    return render_template("monitor/client.html", c=c, cfg=cfg, audits=audits, batches=batches, prompts=prompts)


def _audit_worker(app, client_id, audit_url, max_pages):
    with app.app_context():
        conn = dbmod.connect(app.config["SETTINGS"].database_path)
        try:
            run_site_audit(conn, app.config["SETTINGS"], client_id, start_url=audit_url, max_pages=max_pages)
        except Exception:  # failure is recorded on the audit row by run_site_audit
            app.logger.exception("audit failed for client %s", client_id)
        finally:
            conn.close()


@bp.post("/clients/<slug>/audit")
@login_required
def start_audit(slug):
    c = _client_or_404(slug)
    running = dbmod.one(get_db(), "SELECT id FROM site_audits WHERE client_id=? AND status='running'", (c["id"],))
    if running:
        flash("An audit is already running for this client.")
    else:
        try:
            max_pages = min(int(request.form.get("max_pages") or current_app.config["SETTINGS"].audit_max_pages), 200)
        except ValueError:
            max_pages = current_app.config["SETTINGS"].audit_max_pages
        app = current_app._get_current_object()
        threading.Thread(target=_audit_worker, args=(app, c["id"], c["website_url"], max_pages), daemon=True).start()
        flash("Audit started. Refresh this page in a minute to see progress.")
    return redirect(url_for("monitor.client", slug=slug))


@bp.get("/clients/<slug>/audits/<int:aid>")
@login_required
def audit(slug, aid):
    c = _client_or_404(slug)
    _owned_or_404("site_audits", aid, c["id"])
    rep = build_report(get_db(), c["id"], aid)
    rejected = dbmod.rows(get_db(), "SELECT * FROM recommendations WHERE audit_id=? AND client_id=? AND review_status='rejected'", (aid, c["id"]))
    return render_template("monitor/audit.html", c=c, rep=rep, rejected=rejected, export_kinds=EXPORT_KINDS)


@bp.post("/clients/<slug>/recommendations/<int:rid>")
@login_required
def review_recommendation(slug, rid):
    c = _client_or_404(slug)
    rec = _owned_or_404("recommendations", rid, c["id"])
    status = request.form.get("review_status")
    if status not in ("draft", "approved", "rejected"):
        abort(400)
    conn = get_db()
    conn.execute("UPDATE recommendations SET review_status=? WHERE id=? AND client_id=?", (status, rid, c["id"]))
    if status != "approved":
        conn.execute("UPDATE site_audits SET approved=0, approved_by=NULL, approved_at=NULL WHERE id=?", (rec["audit_id"],))
    conn.commit()
    return redirect(url_for("monitor.audit", slug=slug, aid=rec["audit_id"]) + f"#rec-{rid}")


@bp.post("/clients/<slug>/audits/<int:aid>/approve")
@login_required
def approve_audit(slug, aid):
    c = _client_or_404(slug)
    _owned_or_404("site_audits", aid, c["id"])
    conn = get_db()
    drafts = dbmod.one(conn, "SELECT COUNT(*) n FROM recommendations WHERE audit_id=? AND review_status='draft'", (aid,))["n"]
    if drafts:
        flash(f"Review all recommendations first — {drafts} still in draft.")
    else:
        conn.execute("UPDATE site_audits SET approved=1, approved_by=?, approved_at=? WHERE id=? AND client_id=?",
                     (g.get("user_email"), datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), aid, c["id"]))
        conn.commit()
        flash("Report approved for client delivery.")
    return redirect(url_for("monitor.audit", slug=slug, aid=aid))


@bp.post("/clients/<slug>/audits/<int:aid>/rescore")
@login_required
def rescore(slug, aid):
    c = _client_or_404(slug)
    _owned_or_404("site_audits", aid, c["id"])
    score_and_store(get_db(), aid)
    flash("Score recalculated with the latest AI visibility data.")
    return redirect(url_for("monitor.audit", slug=slug, aid=aid))


@bp.get("/clients/<slug>/audits/<int:aid>/report")
@login_required
def report(slug, aid):
    c = _client_or_404(slug)
    _owned_or_404("site_audits", aid, c["id"])
    html = render_template("reports/audit_report.html", rep=build_report(get_db(), c["id"], aid))
    resp = Response(html, mimetype="text/html")
    # The report embeds its own CSS so the exported file is self-contained.
    resp.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'none'"
    if request.args.get("download"):
        resp.headers["Content-Disposition"] = f'attachment; filename="radynta-audit-{c["slug"]}-{aid}.html"'
    return resp


@bp.get("/clients/<slug>/audits/<int:aid>/export/<kind>.csv")
@login_required
def export(slug, aid, kind):
    c = _client_or_404(slug)
    _owned_or_404("site_audits", aid, c["id"])
    if kind not in EXPORT_KINDS:
        abort(404)
    body = "﻿" + export_csv(get_db(), c["id"], aid, kind)  # BOM so Excel opens UTF-8 correctly
    return Response(body, mimetype="text/csv", headers={
        "Content-Disposition": f'attachment; filename="radynta-{c["slug"]}-audit{aid}-{kind}.csv"'})


@bp.get("/clients/<slug>/batches/<int:bid>")
@login_required
def batch(slug, bid):
    c = _client_or_404(slug)
    b = _owned_or_404("visibility_batches", bid, c["id"])
    conn = get_db()
    responses = dbmod.rows(conn, "SELECT * FROM visibility_responses WHERE batch_id=? AND client_id=? ORDER BY id", (bid, c["id"]))
    cits: dict[int, list] = {}
    for ci in dbmod.rows(conn, "SELECT * FROM citations WHERE client_id=? AND response_id IN (SELECT id FROM visibility_responses WHERE batch_id=?)", (c["id"], bid)):
        cits.setdefault(ci["response_id"], []).append(ci)
    return render_template("monitor/batch.html", c=c, b=b, responses=responses, cits=cits,
                           m=batch_metrics(conn, c["id"], bid), loads=dbmod.loads)
