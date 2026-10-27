"""Command-line workflow: `flask --app radynta <command>`."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import click
from flask import Flask, render_template
from werkzeug.security import generate_password_hash

from . import db as dbmod
from .config import BASE_DIR


def _conn(app: Flask):
    return dbmod.connect(app.config["SETTINGS"].database_path)


def _client(conn, slug: str):
    c = dbmod.client_by_slug(conn, slug)
    if c is None:
        raise click.ClickException(f"No client with slug {slug!r}. List clients with: flask --app radynta list-clients")
    return c


def _slugify(text: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def upsert_client(conn, data: dict, *, is_sample: bool = False) -> int:
    if "_comment" in data:
        raise click.ClickException("This looks like the unedited template (it still has a _comment field). Fill in real values first.")
    required = ["slug", "name", "brand_name", "website_url", "primary_domain"]
    missing = [k for k in required if not str(data.get(k) or "").strip()]
    if missing:
        raise click.ClickException(f"client JSON missing: {', '.join(missing)}")
    slug = _slugify(data["slug"])
    domain = data["primary_domain"].lower().removeprefix("www.").strip("/")
    values = {
        "name": data["name"], "brand_name": data["brand_name"],
        "brand_aliases": dbmod.dumps(data.get("brand_aliases", [])), "website_url": data["website_url"],
        "primary_domain": domain, "extra_domains": dbmod.dumps([d.lower().removeprefix("www.") for d in data.get("extra_domains", [])]),
        "segment": data.get("segment"), "services": dbmod.dumps(data.get("services", [])),
        "geographies": dbmod.dumps(data.get("geographies", [])), "notes": data.get("notes"),
        "is_sample": 1 if is_sample else 0,
    }
    existing = dbmod.client_by_slug(conn, slug)
    if existing:
        conn.execute(f"UPDATE clients SET {', '.join(k + '=?' for k in values)} WHERE id=?", (*values.values(), existing["id"]))
        cid = existing["id"]
    else:
        cid = dbmod.insert(conn, "clients", {"slug": slug, **values})
    if "competitors" in data:
        conn.execute("DELETE FROM competitors WHERE client_id=?", (cid,))
        for comp in data["competitors"]:
            dbmod.insert(conn, "competitors", {"client_id": cid, "name": comp["name"],
                                               "aliases": dbmod.dumps(comp.get("aliases", [])),
                                               "domain": (comp.get("domain") or "").lower().removeprefix("www.") or None})
    for p in data.get("prompts", []):
        add_prompt(conn, cid, p)
    conn.commit()
    return cid


def add_prompt(conn, client_id: int, p: dict) -> bool:
    text = (p.get("text") or "").strip()
    if not text:
        return False
    cur = conn.execute(
        "INSERT OR IGNORE INTO prompts (client_id, text, geography, service_category, target_customer) VALUES (?,?,?,?,?)",
        (client_id, text[:500], (p.get("geography") or "").strip() or None, (p.get("service_category") or "").strip() or None,
         (p.get("target_customer") or "").strip() or None))
    return cur.rowcount > 0


def import_prompts_csv(conn, client_id: int, path: Path) -> int:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if "text" not in (reader.fieldnames or []):
            raise click.ClickException("prompts CSV needs a 'text' column (optional: geography, service_category, target_customer)")
        n = sum(1 for row in reader if add_prompt(conn, client_id, row))
    conn.commit()
    return n


def export_report_files(app: Flask, conn, client_id: int, audit_id: int, out_dir: Path) -> list[Path]:
    from .reports.report_builder import build_report, export_csv

    client = dbmod.client_by_id(conn, client_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"radynta-audit-{client['slug']}-{audit_id}"
    with app.test_request_context():
        html = render_template("reports/audit_report.html", rep=build_report(conn, client_id, audit_id))
    paths = [out_dir / f"{stem}.html"]
    paths[0].write_text(html, encoding="utf-8")
    for kind in ("findings", "recommendations", "pages", "visibility"):
        p = out_dir / f"{stem}-{kind}.csv"
        p.write_text("﻿" + export_csv(conn, client_id, audit_id, kind), encoding="utf-8")
        paths.append(p)
    for p in paths:
        dbmod.insert(conn, "report_exports", {"client_id": client_id, "audit_id": audit_id,
                                              "kind": p.suffix.lstrip(".") + ("" if p.suffix == ".html" else "_" + p.stem.rsplit("-", 1)[-1]),
                                              "path": str(p)})
    conn.commit()
    return paths


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db():
        """Create database tables (safe to re-run)."""
        conn = _conn(app)
        dbmod.init_schema(conn)
        click.echo(f"Database ready at {app.config['SETTINGS'].database_path}")

    @app.cli.command("create-user")
    @click.argument("email")
    @click.password_option(confirmation_prompt=True)
    def create_user(email, password):
        """Create (or reset the password of) a monitor user."""
        if len(password) < 12:
            raise click.ClickException("Use a password of at least 12 characters.")
        conn = _conn(app)
        email = email.strip().lower()
        h = generate_password_hash(password)
        if dbmod.one(conn, "SELECT 1 FROM users WHERE email=?", (email,)):
            conn.execute("UPDATE users SET password_hash=? WHERE email=?", (h, email))
            click.echo(f"Password updated for {email}")
        else:
            dbmod.insert(conn, "users", {"email": email, "password_hash": h})
            click.echo(f"User {email} created")
        conn.commit()

    @app.cli.command("add-client")
    @click.argument("json_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
    def add_client(json_path):
        """Create or update a client from a JSON file (see data/sample_client.json)."""
        data = json.loads(json_path.read_text(encoding="utf-8"))
        conn = _conn(app)
        cid = upsert_client(conn, data)
        if data.get("prompts_csv"):
            p = Path(data["prompts_csv"])
            p = p if p.is_absolute() else BASE_DIR / p
            click.echo(f"Imported {import_prompts_csv(conn, cid, p)} prompts from {p.name}")
        click.echo(f"Client '{_slugify(data['slug'])}' saved (id {cid}).")

    @app.cli.command("list-clients")
    def list_clients():
        for c in dbmod.rows(_conn(app), "SELECT slug, name, primary_domain, is_sample FROM clients ORDER BY name"):
            click.echo(f"{c['slug']:<30} {c['name']:<40} {c['primary_domain']}{'  [SAMPLE]' if c['is_sample'] else ''}")

    @app.cli.command("import-prompts")
    @click.argument("slug")
    @click.argument("csv_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
    def import_prompts(slug, csv_path):
        """Add buyer questions from a CSV (columns: text, geography, service_category, target_customer)."""
        conn = _conn(app)
        n = import_prompts_csv(conn, _client(conn, slug)["id"], csv_path)
        click.echo(f"Added {n} new prompts (duplicates skipped).")

    @app.cli.command("run-audit")
    @click.argument("slug")
    @click.option("--url", help="Start URL (defaults to the client's website_url)")
    @click.option("--max-pages", type=click.IntRange(1, 200))
    def run_audit(slug, url, max_pages):
        """Crawl the client's public website and score it."""
        from .audit.pipeline import run_site_audit

        conn = _conn(app)
        c = _client(conn, slug)
        if c["is_sample"]:
            raise click.ClickException("Sample clients use synthetic data; run `seed-sample` instead.")
        click.echo(f"Auditing {url or c['website_url']} (polite crawl; this can take a minute)…")
        try:
            aid = run_site_audit(conn, app.config["SETTINGS"], c["id"], start_url=url, max_pages=max_pages)
        except Exception as exc:
            raise click.ClickException(f"Audit failed: {exc}") from exc
        a = dbmod.one(conn, "SELECT * FROM site_audits WHERE id=?", (aid,))
        score = dbmod.loads(a["score_json"], {})
        click.echo(f"Audit #{aid}: {a['pages_crawled']} pages, diagnostic {score.get('normalized')}/100 "
                   f"({score.get('awarded')} of {score.get('measured_possible')} measured points).")
        click.echo("Review recommendations in the monitor before exporting a client report.")

    @app.cli.command("run-visibility")
    @click.argument("slug")
    @click.option("--provider", type=click.Choice(["perplexity", "openai"]), required=True)
    @click.option("--limit", type=int, help="Only run the first N prompts (useful for a cheap test)")
    @click.option("--market", help="Market label stored with results, e.g. 'India'")
    def run_visibility(slug, provider, limit, market):
        """Collect AI answers for the client's active prompts through an official API."""
        from .visibility.providers import ProviderNotConfigured, get_provider
        from .visibility.runner import run_api_batch

        conn = _conn(app)
        c = _client(conn, slug)
        try:
            prov = get_provider(provider, app.config["SETTINGS"])
        except ProviderNotConfigured as exc:
            raise click.ClickException(str(exc)) from exc
        bid, m = run_api_batch(conn, c["id"], prov, market=market, limit=limit,
                               delay=app.config["SETTINGS"].visibility_request_delay)
        click.echo(f"Batch #{bid}: {m['valid_runs']} valid / {m['total_runs']} total ({m['failed_runs']} failed).")
        if m["valid_runs"]:
            click.echo(f"Brand mention rate {m['brand_mention_rate']:.0%}; client citation rate {m['client_citation_rate']:.0%}.")
        click.echo("Re-score the latest audit to include this data: flask --app radynta rescore-audit " + slug)

    @app.cli.command("check-provider")
    @click.argument("name", type=click.Choice(["perplexity", "openai"]))
    @click.option("--live", is_flag=True, help="Also send ONE real test question (uses API credit)")
    def check_provider(name, live):
        """Validate provider configuration, optionally with one live request."""
        from .visibility.providers import ProviderError, ProviderNotConfigured, get_provider

        try:
            prov = get_provider(name, app.config["SETTINGS"])
        except ProviderNotConfigured as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"{prov.platform}: configuration present (model {prov.model}).")
        if live:
            try:
                res = prov.collect("Which freight forwarders handle sea freight exports from India to the UAE?")
            except ProviderError as exc:
                raise click.ClickException(f"Live request failed: {exc}") from exc
            click.echo(f"OK — {len(res.text)} characters, {len(res.citations)} citations, model {res.model}.")

    @app.cli.command("import-responses")
    @click.argument("slug")
    @click.argument("csv_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
    def import_responses(slug, csv_path):
        """Import manually captured AI answers (see data/manual_responses_template.csv)."""
        from .visibility.runner import import_manual_csv

        conn = _conn(app)
        c = _client(conn, slug)
        try:
            results = import_manual_csv(conn, c["id"], csv_path)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        for bid, m in results:
            click.echo(f"Batch #{bid}: {m['valid_runs']} valid / {m['total_runs']} total.")

    @app.cli.command("rescore-audit")
    @click.argument("slug")
    @click.option("--audit-id", type=int, help="Defaults to the latest completed audit")
    def rescore_audit(slug, audit_id):
        """Recalculate score/findings using the latest AI visibility data."""
        from .audit.pipeline import score_and_store

        conn = _conn(app)
        c = _client(conn, slug)
        a = dbmod.owned(conn, "site_audits", audit_id, c["id"]) if audit_id else dbmod.one(
            conn, "SELECT * FROM site_audits WHERE client_id=? AND status='completed' ORDER BY id DESC LIMIT 1", (c["id"],))
        if not a:
            raise click.ClickException("No completed audit found.")
        card = score_and_store(conn, a["id"])
        click.echo(f"Audit #{a['id']} re-scored: {card['normalized']}/100 ({card['awarded']} of {card['measured_possible']}).")

    @app.cli.command("export-report")
    @click.argument("slug")
    @click.option("--audit-id", type=int)
    @click.option("--out", "out_dir", type=click.Path(file_okay=False, path_type=Path), default=BASE_DIR / "reports")
    @click.option("--allow-draft", is_flag=True, help="Export even if the report has not been approved")
    def export_report(slug, audit_id, out_dir, allow_draft):
        """Write the HTML report and CSV exports to the reports/ folder."""
        conn = _conn(app)
        c = _client(conn, slug)
        a = dbmod.owned(conn, "site_audits", audit_id, c["id"]) if audit_id else dbmod.one(
            conn, "SELECT * FROM site_audits WHERE client_id=? AND status='completed' ORDER BY id DESC LIMIT 1", (c["id"],))
        if not a:
            raise click.ClickException("No completed audit found.")
        if not a["approved"] and not allow_draft:
            raise click.ClickException("Report not approved yet. Review it in the monitor, or pass --allow-draft (it will be watermarked DRAFT).")
        for p in export_report_files(app, conn, c["id"], a["id"], out_dir):
            click.echo(f"wrote {p}")

    @app.cli.command("seed-sample")
    @click.option("--out", "out_dir", type=click.Path(file_okay=False, path_type=Path), default=BASE_DIR / "docs" / "sample-report")
    def seed_sample(out_dir):
        """Create the clearly labelled SYNTHETIC sample client, audit and report."""
        from .audit.pipeline import run_site_audit
        from .audit.safe_fetch import SafeFetcher
        from .sample_data import SAMPLE_CLIENT, SAMPLE_RESPONSES_CSV, InMemorySession, sample_resolver
        from .visibility.runner import import_manual_csv

        conn = _conn(app)
        existing = dbmod.client_by_slug(conn, SAMPLE_CLIENT["slug"])
        if existing:
            conn.execute("DELETE FROM clients WHERE id=?", (existing["id"],))
            conn.commit()
        cid = upsert_client(conn, SAMPLE_CLIENT, is_sample=True)
        import_manual_csv(conn, cid, BASE_DIR / SAMPLE_RESPONSES_CSV, sample=True)
        fetcher = SafeFetcher(InMemorySession(), resolver=sample_resolver)
        aid = run_site_audit(conn, app.config["SETTINGS"], cid, fetcher=fetcher, sleep=lambda s: None)
        conn.execute("UPDATE site_audits SET is_sample=1 WHERE id=?", (aid,))
        conn.commit()
        paths = export_report_files(app, conn, cid, aid, out_dir)
        click.echo(f"Sample client '{SAMPLE_CLIENT['slug']}' with audit #{aid} created (SYNTHETIC DATA).")
        for p in paths:
            click.echo(f"wrote {p}")
