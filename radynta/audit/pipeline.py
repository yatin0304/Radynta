"""Run a website audit for a client and persist everything needed for the report."""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone

from .. import db
from ..config import Settings
from ..visibility.metrics import latest_visibility_summary
from .recommendations import findings_from_scorecard, recommendation_for
from .safe_fetch import SafeFetcher
from .scoring import score_audit
from .website_audit import SiteCrawler


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def run_site_audit(conn: sqlite3.Connection, settings: Settings, client_id: int, *,
                   start_url: str | None = None, max_pages: int | None = None,
                   fetcher: SafeFetcher | None = None, sleep=time.sleep) -> int:
    client = db.client_config(conn, client_id)
    url = start_url or client["website_url"]
    audit_id = db.insert(conn, "site_audits", {"client_id": client_id, "start_url": url})
    conn.commit()
    try:
        fetcher = fetcher or SafeFetcher(
            user_agent=settings.audit_user_agent, timeout=settings.audit_timeout, max_bytes=settings.audit_max_bytes
        )
        crawler = SiteCrawler(fetcher, max_pages=max_pages or settings.audit_max_pages,
                              delay=settings.audit_request_delay, user_agent=settings.audit_user_agent, sleep=sleep)
        crawl = crawler.crawl(url)
        for p in crawl.pages:
            db.insert(conn, "page_checks", {
                "audit_id": audit_id, "client_id": client_id, "url": p.url, "final_url": p.final_url,
                "status_code": p.status_code, "redirect_chain": db.dumps(p.redirect_chain),
                "data": db.dumps(p.data), "error": p.error,
            })
        conn.execute(
            """UPDATE site_audits SET pages_crawled=?, robots_status=?, robots_txt=?, sitemap_url=?,
               sitemap_status=?, sitemap_url_count=?, crawl_notes=? WHERE id=?""",
            (len(crawl.pages), crawl.robots_status, crawl.robots_txt, crawl.sitemap_url, crawl.sitemap_status,
             crawl.sitemap_url_count, db.dumps(crawl.notes), audit_id),
        )
        site_meta = {
            "start_url": crawl.start_url, "site_host": crawl.site_host, "https": crawl.https,
            "robots_status": crawl.robots_status, "robots_blocks_all": crawl.robots_blocks_all,
            "sitemap_url": crawl.sitemap_url, "sitemap_status": crawl.sitemap_status,
            "sitemap_url_count": crawl.sitemap_url_count,
        }
        conn.execute("UPDATE site_audits SET score_json=? WHERE id=?", (db.dumps({"site": site_meta}), audit_id))
        score_and_store(conn, audit_id)
        conn.execute("UPDATE site_audits SET status='completed', finished_at=? WHERE id=?", (now_iso(), audit_id))
        conn.commit()
    except Exception as exc:
        conn.rollback()
        conn.execute("UPDATE site_audits SET status='failed', error=?, finished_at=? WHERE id=?",
                     (f"{type(exc).__name__}: {exc}", now_iso(), audit_id))
        conn.commit()
        raise
    return audit_id


def score_and_store(conn: sqlite3.Connection, audit_id: int) -> dict:
    """(Re)compute score, findings and draft recommendations from stored page data.

    Safe to call again after new AI visibility data is collected. Existing draft
    recommendations are replaced; approved/rejected ones are kept.
    """
    audit = db.one(conn, "SELECT * FROM site_audits WHERE id=?", (audit_id,))
    client_id = audit["client_id"]
    client = db.client_config(conn, client_id)
    stored = db.loads(audit["score_json"], {}) or {}
    site_meta = stored.get("site") or {"start_url": audit["start_url"]}
    pages = [
        {"url": r["url"], "final_url": r["final_url"] or r["url"], "status_code": r["status_code"],
         "data": db.loads(r["data"], {}), "error": r["error"]}
        for r in db.rows(conn, "SELECT * FROM page_checks WHERE audit_id=? AND client_id=? ORDER BY id", (audit_id, client_id))
    ]
    visibility = latest_visibility_summary(conn, client_id)
    scorecard = score_audit(site_meta, pages, client, visibility)
    scorecard["site"] = site_meta
    scorecard["visibility_summary"] = visibility
    conn.execute("UPDATE site_audits SET score_json=? WHERE id=?", (db.dumps(scorecard), audit_id))

    reviewed = {r["title"] for r in db.rows(
        conn, "SELECT title FROM recommendations WHERE audit_id=? AND review_status != 'draft'", (audit_id,))}
    conn.execute("DELETE FROM recommendations WHERE audit_id=? AND review_status='draft'", (audit_id,))
    conn.execute("DELETE FROM audit_findings WHERE audit_id=? AND id NOT IN "
                 "(SELECT finding_id FROM recommendations WHERE audit_id=? AND finding_id IS NOT NULL)", (audit_id, audit_id))
    kept_codes = {r["code"] for r in db.rows(conn, "SELECT code FROM audit_findings WHERE audit_id=?", (audit_id,))}
    for f in findings_from_scorecard(scorecard):
        if f["code"] in kept_codes:
            continue
        fid = db.insert(conn, "audit_findings", {
            "audit_id": audit_id, "client_id": client_id, "dimension": f["dimension"], "code": f["code"],
            "severity": f["severity"], "title": f["title"], "evidence": f["evidence"], "urls": db.dumps(f["urls"]),
        })
        rec = recommendation_for(f)
        if rec and rec["title"] not in reviewed:
            db.insert(conn, "recommendations", {"audit_id": audit_id, "client_id": client_id, "finding_id": fid, **rec})

    conn.execute("DELETE FROM tracked_metrics WHERE audit_id=?", (audit_id,))
    db.insert(conn, "tracked_metrics", {"client_id": client_id, "audit_id": audit_id, "metric": "diagnostic_score",
                                        "value": scorecard["normalized"], "denominator": scorecard["measured_possible"]})
    for key, dim in scorecard["dimensions"].items():
        if dim["measured"]:
            db.insert(conn, "tracked_metrics", {"client_id": client_id, "audit_id": audit_id, "metric": f"dim_{key}",
                                                "value": dim["awarded"], "denominator": dim["possible"]})
    conn.commit()
    return scorecard
