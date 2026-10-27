"""Visibility metrics. Denominators are VALID runs only: failed collections are
reported as failures, never silently counted as 'brand not mentioned'."""
from __future__ import annotations

import sqlite3
from collections import Counter

from .. import db


def compute_metrics(responses: list[dict], citations_by_response: dict[int, list[dict]]) -> dict:
    total = len(responses)
    valid = [r for r in responses if r["status"] == "ok"]
    n_valid = len(valid)
    failed = total - n_valid

    def rate(n: int) -> float | None:
        return round(n / n_valid, 4) if n_valid else None

    mentioned = sum(1 for r in valid if r.get("brand_mentioned"))
    ambiguous = sum(1 for r in valid if r.get("brand_mentioned") and r.get("mention_ambiguous"))
    client_cited = sum(1 for r in valid if any(c["is_client_domain"] for c in citations_by_response.get(r["id"], [])))

    comp_counter: Counter[str] = Counter()
    for r in valid:
        for name in {m["name"] for m in (db.loads(r.get("competitor_mentions"), []) or [])}:
            comp_counter[name] += 1
    domain_counter: Counter[str] = Counter()
    for r in valid:
        for dom in {c["domain"] for c in citations_by_response.get(r["id"], [])}:
            domain_counter[dom] += 1

    return {
        "total_runs": total,
        "valid_runs": n_valid,
        "failed_runs": failed,
        "failure_rate": round(failed / total, 4) if total else None,
        "brand_mentions": mentioned,
        "brand_mention_rate": rate(mentioned),
        "ambiguous_mentions": ambiguous,
        "client_citations": client_cited,
        "client_citation_rate": rate(client_cited),
        "competitor_mentions": [
            {"name": n, "count": c, "rate": rate(c)} for n, c in comp_counter.most_common()
        ],
        "cited_domains": [
            {"domain": d, "count": c, "rate": rate(c)} for d, c in domain_counter.most_common(25)
        ],
    }


def compare(current: dict, previous: dict | None) -> dict:
    """Percentage-point deltas between two metric sets (None if not comparable)."""
    out = {}
    for key in ("brand_mention_rate", "client_citation_rate", "failure_rate"):
        cur, prev = current.get(key), (previous or {}).get(key)
        out[key] = round((cur - prev) * 100, 1) if cur is not None and prev is not None else None
    return out


def _responses_and_citations(conn: sqlite3.Connection, client_id: int, batch_ids: list[int]):
    if not batch_ids:
        return [], {}
    marks = ",".join("?" * len(batch_ids))
    responses = [dict(r) for r in db.rows(
        conn, f"SELECT * FROM visibility_responses WHERE client_id=? AND batch_id IN ({marks}) ORDER BY id",
        (client_id, *batch_ids))]
    cits: dict[int, list[dict]] = {}
    if responses:
        ids = [r["id"] for r in responses]
        rmarks = ",".join("?" * len(ids))
        for c in db.rows(conn, f"SELECT * FROM citations WHERE client_id=? AND response_id IN ({rmarks})", (client_id, *ids)):
            cits.setdefault(c["response_id"], []).append(dict(c))
    return responses, cits


def batch_metrics(conn: sqlite3.Connection, client_id: int, batch_id: int) -> dict:
    responses, cits = _responses_and_citations(conn, client_id, [batch_id])
    return compute_metrics(responses, cits)


def latest_batches(conn: sqlite3.Connection, client_id: int) -> list[sqlite3.Row]:
    """Most recent completed batch per platform for the client."""
    return db.rows(conn, """
        SELECT b.* FROM visibility_batches b
        WHERE b.client_id = ? AND b.status = 'completed' AND b.id = (
            SELECT b2.id FROM visibility_batches b2
            WHERE b2.client_id = b.client_id AND b2.platform = b.platform AND b2.status = 'completed'
            ORDER BY b2.started_at DESC, b2.id DESC LIMIT 1)
        ORDER BY b.platform""", (client_id,))


def latest_visibility_summary(conn: sqlite3.Connection, client_id: int) -> dict | None:
    batches = latest_batches(conn, client_id)
    if not batches:
        return None
    responses, cits = _responses_and_citations(conn, client_id, [b["id"] for b in batches])
    summary = compute_metrics(responses, cits)
    summary["batch_ids"] = [b["id"] for b in batches]
    summary["platforms"] = [{"platform": b["platform"], "source": b["source"], "model": b["model"],
                             "collected": b["started_at"][:10]} for b in batches]
    summary["platforms_label"] = ", ".join(b["platform"] for b in batches)
    summary["per_platform"] = {b["platform"]: batch_metrics(conn, client_id, b["id"]) for b in batches}
    return summary


def previous_batch(conn: sqlite3.Connection, client_id: int, batch: sqlite3.Row) -> sqlite3.Row | None:
    return db.one(conn, """SELECT * FROM visibility_batches WHERE client_id=? AND platform=? AND status='completed'
                           AND (started_at < ? OR (started_at = ? AND id < ?)) ORDER BY started_at DESC, id DESC LIMIT 1""",
                  (client_id, batch["platform"], batch["started_at"], batch["started_at"], batch["id"]))
