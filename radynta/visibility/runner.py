"""Collect AI answers for a client's prompt library and store raw + parsed results.

Two collection paths:
* API providers (Perplexity, OpenAI) via run_api_batch
* Manual capture: a RADYNTA analyst asks the questions in the consumer apps
  (ChatGPT, Gemini, Google AI Overviews, ...) and records the answers in a CSV,
  imported with import_manual_csv. This is the ToS-safe way to measure
  consumer-facing answers; we never scrape those apps.
"""
from __future__ import annotations

import csv
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from .. import db
from .metrics import batch_metrics
from .providers import Provider, ProviderError
from .response_parser import parse_response


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def store_response(conn: sqlite3.Connection, client: dict, batch_id: int, *, prompt_text: str, prompt_id: int | None,
                   platform: str, model: str | None, market: str | None, collected_at: str,
                   text: str | None, citations: list[str], raw_payload: str | None = None,
                   error: str | None = None) -> int:
    ok = error is None and bool((text or "").strip())
    if not ok and error is None:
        error = "empty response"
    parsed = parse_response(text or "", citations, client) if ok else None
    rid = db.insert(conn, "visibility_responses", {
        "batch_id": batch_id, "client_id": client["id"], "prompt_id": prompt_id, "prompt_text": prompt_text,
        "platform": platform, "model": model, "market": market, "collected_at": collected_at,
        "status": "ok" if ok else "error", "raw_response": text, "raw_payload": raw_payload, "error": error,
        "brand_mentioned": (1 if parsed.brand.mentioned else 0) if parsed else None,
        "mention_context": parsed.brand.context if parsed else None,
        "mention_ambiguous": 1 if (parsed and parsed.brand.ambiguous) else 0,
        "competitor_mentions": db.dumps(parsed.competitor_mentions if parsed else []),
    })
    if parsed:
        for c in parsed.citations:
            db.insert(conn, "citations", {
                "response_id": rid, "client_id": client["id"], "url": c.url, "domain": c.domain, "origin": c.origin,
                "is_client_domain": 1 if c.is_client_domain else 0, "competitor_id": c.competitor_id,
            })
    return rid


def _finish(conn, client_id: int, batch_id: int) -> dict:
    metrics = batch_metrics(conn, client_id, batch_id)
    status = "completed" if metrics["valid_runs"] else "failed"
    conn.execute("UPDATE visibility_batches SET status=?, finished_at=? WHERE id=?", (status, _now(), batch_id))
    for key in ("brand_mention_rate", "client_citation_rate", "failure_rate"):
        db.insert(conn, "tracked_metrics", {"client_id": client_id, "batch_id": batch_id, "metric": key,
                                            "value": metrics[key], "denominator": metrics["valid_runs"] if key != "failure_rate" else metrics["total_runs"]})
    conn.commit()
    return metrics


def run_api_batch(conn: sqlite3.Connection, client_id: int, provider: Provider, *, market: str | None = None,
                  delay: float = 2.0, limit: int | None = None, sleep=time.sleep) -> tuple[int, dict]:
    client = db.client_config(conn, client_id)
    prompts = db.rows(conn, "SELECT * FROM prompts WHERE client_id=? AND active=1 ORDER BY id", (client_id,))
    if limit:
        prompts = prompts[:limit]
    if not prompts:
        raise ValueError(f"client {client['slug']} has no active prompts; import some first")
    batch_id = db.insert(conn, "visibility_batches", {"client_id": client_id, "platform": provider.platform,
                                                       "source": "api", "model": provider.model, "market": market})
    conn.commit()
    for i, p in enumerate(prompts):
        if i and delay:
            sleep(delay)
        collected = _now()
        try:
            res = provider.collect(p["text"], market=market or p["geography"])
        except ProviderError as exc:
            store_response(conn, client, batch_id, prompt_text=p["text"], prompt_id=p["id"], platform=provider.platform,
                           model=provider.model, market=market, collected_at=collected, text=None, citations=[],
                           error=str(exc))
        else:
            store_response(conn, client, batch_id, prompt_text=p["text"], prompt_id=p["id"], platform=provider.platform,
                           model=res.model, market=market, collected_at=collected, text=res.text,
                           citations=res.citations, raw_payload=res.raw_payload)
        conn.commit()
    return batch_id, _finish(conn, client_id, batch_id)


MANUAL_COLUMNS = ["prompt", "platform", "model", "collected_at", "market", "response_text", "citation_urls", "notes"]


def import_manual_csv(conn: sqlite3.Connection, client_id: int, path: Path, *, sample: bool = False) -> list[tuple[int, dict]]:
    """Import manually captured answers. One batch is created per platform in the file."""
    client = db.client_config(conn, client_id)
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = {"prompt", "platform", "response_text"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")
        rows_by_platform: dict[str, list[dict]] = {}
        for row in reader:
            if not (row.get("prompt") or "").strip():
                continue
            platform = (row.get("platform") or "").strip().lower()
            if not platform:
                raise ValueError("every row needs a platform (e.g. chatgpt-web, gemini-web, google-ai-overview)")
            rows_by_platform.setdefault(platform, []).append(row)

    prompt_ids = {r["text"]: r["id"] for r in db.rows(conn, "SELECT id, text FROM prompts WHERE client_id=?", (client_id,))}
    results = []
    for platform, items in rows_by_platform.items():
        batch_id = db.insert(conn, "visibility_batches", {
            "client_id": client_id, "platform": platform, "source": "sample" if sample else "manual",
            "model": (items[0].get("model") or "").strip() or None, "market": (items[0].get("market") or "").strip() or None,
            "notes": f"Imported from {Path(path).name}",
            # date the answers were collected, not the import date
            "started_at": min(((r.get("collected_at") or "").strip() for r in items if (r.get("collected_at") or "").strip()), default=_now()),
        })
        for row in items:
            text = (row.get("response_text") or "").strip()
            urls = [u for u in re.split(r"[\s;,]+", row.get("citation_urls") or "") if u.startswith(("http://", "https://"))]
            store_response(conn, client, batch_id, prompt_text=row["prompt"].strip(),
                           prompt_id=prompt_ids.get(row["prompt"].strip()), platform=platform,
                           model=(row.get("model") or "").strip() or None, market=(row.get("market") or "").strip() or None,
                           collected_at=(row.get("collected_at") or "").strip() or _now(), text=text, citations=urls,
                           error=None if text else "no response text recorded")
        conn.commit()
        results.append((batch_id, _finish(conn, client_id, batch_id)))
    return results
