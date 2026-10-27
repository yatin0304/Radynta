"""Assemble audit report data and CSV exports. All queries are scoped by client_id."""
from __future__ import annotations

import csv
import io
import sqlite3
from datetime import datetime

from .. import db
from ..visibility.metrics import compare, previous_batch, batch_metrics

STANDARD_LIMITATIONS = [
    "The diagnostic score is RADYNTA’s internal framework for prioritising work. It is not an official score or ranking from Google, OpenAI, Perplexity, Microsoft or any other platform.",
    "AI answers vary between runs, users, locations and over time. Visibility results are a sample collected on the dates shown, not a permanent measurement.",
    "API-collected answers may differ from what users see in consumer apps. The collection method for each platform is listed in the scope section.",
    "Rates use valid responses as the denominator. Failed collections are reported separately and are never counted as ‘not mentioned’.",
    "The website crawl covered public pages only, within a fixed page limit. Pages behind logins, forms or JavaScript-only rendering may not have been assessed.",
    "Expected outcomes are hypotheses. No ranking, citation or enquiry increase is guaranteed.",
]


def _plan(recs: list[dict]) -> list[dict]:
    p1 = [r for r in recs if r["priority"] == "P1"]
    p2 = [r for r in recs if r["priority"] == "P2"]
    p3 = [r for r in recs if r["priority"] == "P3"]
    half = (len(p1) + 1) // 2
    weeks = [
        {"week": "Week 1", "focus": "Fix the highest-impact blockers", "items": [r["title"] for r in p1[:half]]},
        {"week": "Week 2", "focus": "Complete remaining priority fixes", "items": [r["title"] for r in p1[half:]]},
        {"week": "Week 3", "focus": "Improve relevance and content", "items": [r["title"] for r in p2]},
        {"week": "Week 4", "focus": "Polish and re-measure", "items": [r["title"] for r in p3]
         + ["Re-run the website audit and the same AI visibility questions to compare against this baseline"]},
    ]
    return weeks


def build_report(conn: sqlite3.Connection, client_id: int, audit_id: int) -> dict:
    audit = db.owned(conn, "site_audits", audit_id, client_id)
    if audit is None:
        raise LookupError("audit not found for this client")
    client = db.client_config(conn, client_id)
    score = db.loads(audit["score_json"], {}) or {}
    vis = score.get("visibility_summary")
    findings = [dict(f) | {"urls": db.loads(f["urls"], [])} for f in db.rows(
        conn, "SELECT * FROM audit_findings WHERE audit_id=? AND client_id=? ORDER BY CASE severity "
              "WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END, code", (audit_id, client_id))]
    recs = [dict(r) for r in db.rows(
        conn, "SELECT * FROM recommendations WHERE audit_id=? AND client_id=? AND review_status != 'rejected' "
              "ORDER BY priority, id", (audit_id, client_id))]
    pages = [dict(p) | {"data": db.loads(p["data"], {})} for p in db.rows(
        conn, "SELECT * FROM page_checks WHERE audit_id=? AND client_id=? ORDER BY id", (audit_id, client_id))]
    prompts = db.rows(conn, "SELECT * FROM prompts WHERE client_id=? AND active=1 ORDER BY id", (client_id,))

    batches = []
    if vis and vis.get("batch_ids"):
        for bid in vis["batch_ids"]:
            b = db.owned(conn, "visibility_batches", bid, client_id)
            if not b:
                continue
            m = batch_metrics(conn, client_id, bid)
            prev = previous_batch(conn, client_id, b)
            batches.append({"batch": dict(b), "metrics": m,
                            "delta": compare(m, batch_metrics(conn, client_id, prev["id"])) if prev else None,
                            "previous_date": prev["started_at"][:10] if prev else None})
        responses = [dict(r) for r in db.rows(
            conn, f"SELECT * FROM visibility_responses WHERE client_id=? AND batch_id IN ({','.join('?' * len(vis['batch_ids']))}) "
                  "ORDER BY platform, id", (client_id, *vis["batch_ids"]))]
    else:
        responses = []

    limitations = list(STANDARD_LIMITATIONS)
    for dim in score.get("dimensions", {}).values():
        if not dim["measured"]:
            limitations.append(f"{dim['label']} was not measured in this audit and is excluded from the score.")
        for c in dim["checks"]:
            if c["measured"] and c.get("limitation"):
                limitations.append(f"{c['code']} {c['label']}: {c['limitation']}")
    limitations += [f"Crawl note: {n}" for n in db.loads(audit["crawl_notes"], [])][:10]
    if any(r["mention_ambiguous"] for r in responses if r["status"] == "ok"):
        limitations.append("Some brand matches were flagged as ambiguous (short or generic name) and should be confirmed by a reviewer.")

    previous_audit = db.one(conn, "SELECT id, score_json, started_at FROM site_audits WHERE client_id=? AND status='completed' "
                                  "AND id < ? ORDER BY id DESC LIMIT 1", (client_id, audit_id))
    prev_score = (db.loads(previous_audit["score_json"], {}) or {}).get("normalized") if previous_audit else None

    return {
        "client": client,
        "audit": dict(audit),
        "score": score,
        "findings": findings,
        "recommendations": recs,
        "draft_count": sum(1 for r in recs if r["review_status"] == "draft"),
        "is_draft": not audit["approved"],
        "is_sample": bool(audit["is_sample"] or client["is_sample"]),
        "pages": pages,
        "prompts": [dict(p) for p in prompts],
        "visibility": vis,
        "batches": batches,
        "responses": responses,
        "plan": _plan(recs),
        "limitations": limitations,
        "previous_score": prev_score,
        "previous_audit_date": previous_audit["started_at"][:10] if previous_audit else None,
        "generated_at": datetime.now().strftime("%d %b %Y"),
    }


def _csv(header: list[str], rows: list[list]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow(["" if v is None else v for v in r])
    return buf.getvalue()


def export_csv(conn: sqlite3.Connection, client_id: int, audit_id: int, kind: str) -> str:
    rep = build_report(conn, client_id, audit_id)
    if kind == "findings":
        return _csv(["severity", "dimension", "code", "title", "evidence", "example_urls", "status"],
                    [[f["severity"], f["dimension"], f["code"], f["title"], f["evidence"], " ".join(f["urls"]), f["status"]]
                     for f in rep["findings"]])
    if kind == "recommendations":
        return _csv(["priority", "title", "finding", "evidence", "business_relevance", "action", "effort", "expected_outcome_hypothesis", "review_status"],
                    [[r["priority"], r["title"], r["finding"], r["evidence"], r["business_relevance"], r["action"], r["effort"], r["hypothesis"], r["review_status"]]
                     for r in rep["recommendations"]])
    if kind == "pages":
        return _csv(["url", "final_url", "status", "title", "meta_description", "h1_count", "canonical", "noindex", "word_count", "schema_types", "error"],
                    [[p["url"], p["final_url"], p["status_code"], p["data"].get("title"), p["data"].get("meta_description"),
                      len(p["data"].get("h1", [])), p["data"].get("canonical"), p["data"].get("noindex"), p["data"].get("word_count"),
                      " ".join(p["data"].get("schema_types", [])), p["error"]] for p in rep["pages"]])
    if kind == "visibility":
        cits: dict[int, list[str]] = {}
        for c in db.rows(conn, "SELECT response_id, url FROM citations WHERE client_id=?", (client_id,)):
            cits.setdefault(c["response_id"], []).append(c["url"])
        return _csv(["platform", "model", "collected_at", "prompt", "status", "brand_mentioned", "ambiguous", "mention_context",
                     "competitors_mentioned", "citation_urls", "error"],
                    [[r["platform"], r["model"], r["collected_at"], r["prompt_text"], r["status"],
                      {1: "yes", 0: "no"}.get(r["brand_mentioned"], "n/a"), "yes" if r["mention_ambiguous"] else "",
                      r["mention_context"], "; ".join(m["name"] for m in db.loads(r["competitor_mentions"], [])),
                      " ".join(cits.get(r["id"], [])), r["error"]] for r in rep["responses"]])
    raise ValueError(f"unknown export kind {kind!r}")
