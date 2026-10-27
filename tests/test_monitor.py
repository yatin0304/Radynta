import pytest

from radynta import db as dbmod
from radynta.audit.pipeline import run_site_audit
from radynta.audit.safe_fetch import SafeFetcher
from radynta.cli import upsert_client
from radynta.sample_data import SAMPLE_CLIENT, InMemorySession, sample_resolver
from radynta.visibility.runner import import_manual_csv, run_api_batch
from radynta.visibility.providers import ProviderError, ProviderNotConfigured, ProviderResult, get_provider
from radynta.config import BASE_DIR, Settings
from tests.conftest import csrf_from


def _seed(app, conn, slug="sample-roadlines", domain=None):
    data = dict(SAMPLE_CLIENT, slug=slug)
    if domain:
        data["primary_domain"] = domain
    cid = upsert_client(conn, data, is_sample=True)
    import_manual_csv(conn, cid, BASE_DIR / "data/sample_responses.csv", sample=True)
    aid = run_site_audit(conn, app.config["SETTINGS"], cid, fetcher=SafeFetcher(InMemorySession(), resolver=sample_resolver), sleep=lambda s: None)
    return cid, aid


def test_monitor_requires_login(client):
    for path in ("/monitor/", "/monitor/enquiries", "/monitor/clients/x"):
        r = client.get(path)
        assert r.status_code == 302 and "/monitor/login" in r.headers["Location"]


def test_bad_login_rejected(client, conn):
    page = client.get("/monitor/login").get_data(as_text=True)
    r = client.post("/monitor/login", data={"email": "nobody@x.com", "password": "nope", "csrf_token": csrf_from(page)})
    assert r.status_code == 401


def test_monitor_pages_and_noindex(app, logged_in, conn):
    cid, aid = _seed(app, conn)
    for path in ("/monitor/", "/monitor/enquiries", "/monitor/clients/sample-roadlines", f"/monitor/clients/sample-roadlines/audits/{aid}"):
        r = logged_in.get(path)
        assert r.status_code == 200, path
        assert r.headers["X-Robots-Tag"] == "noindex, nofollow"
    batch = conn.execute("SELECT id FROM visibility_batches WHERE client_id=? LIMIT 1", (cid,)).fetchone()["id"]
    assert logged_in.get(f"/monitor/clients/sample-roadlines/batches/{batch}").status_code == 200


def test_report_and_csv_exports(app, logged_in, conn):
    _, aid = _seed(app, conn)
    html = logged_in.get(f"/monitor/clients/sample-roadlines/audits/{aid}/report").get_data(as_text=True)
    for section in ["1. Client details", "2. Scope and methodology", "3. Platforms and questions", "4. AI visibility findings",
                    "5. Citation and competitor analysis", "6. Technical website findings", "7. Logistics service and route",
                    "8. Conversion-readiness", "9. Prioritised recommendations", "10. Measurement limitations", "11. Suggested 30-day"]:
        assert section in html
    assert "SAMPLE REPORT" in html and "DRAFT" in html
    assert "not an official score" in html
    csv_text = logged_in.get(f"/monitor/clients/sample-roadlines/audits/{aid}/export/visibility.csv").get_data(as_text=True)
    assert "prompt" in csv_text.splitlines()[0] and "error" in csv_text  # failed sample row present, not hidden
    assert logged_in.get(f"/monitor/clients/sample-roadlines/audits/{aid}/export/bogus.csv").status_code == 404


def test_client_separation_in_urls(app, logged_in, conn):
    _, aid_a = _seed(app, conn, slug="client-a", domain="a.example")
    _seed(app, conn, slug="client-b", domain="b.example")
    # client A's audit must not be reachable through client B's URL space
    for path in (f"/monitor/clients/client-b/audits/{aid_a}", f"/monitor/clients/client-b/audits/{aid_a}/report",
                 f"/monitor/clients/client-b/audits/{aid_a}/export/findings.csv"):
        assert logged_in.get(path).status_code == 404, path
    rec = conn.execute("SELECT id FROM recommendations WHERE audit_id=?", (aid_a,)).fetchone()["id"]
    page = logged_in.get("/monitor/").get_data(as_text=True)
    r = logged_in.post(f"/monitor/clients/client-b/recommendations/{rec}", data={"review_status": "approved", "csrf_token": csrf_from(page)})
    assert r.status_code == 404
    assert conn.execute("SELECT review_status FROM recommendations WHERE id=?", (rec,)).fetchone()[0] == "draft"


def test_report_data_scoped_to_client(app, conn):
    from radynta.reports.report_builder import build_report
    cid_a, aid_a = _seed(app, conn, slug="client-a", domain="a.example")
    cid_b, _ = _seed(app, conn, slug="client-b", domain="b.example")
    with pytest.raises(LookupError):
        build_report(conn, cid_b, aid_a)
    rep = build_report(conn, cid_a, aid_a)
    assert all(r["client_id"] == cid_a for r in rep["responses"] + rep["recommendations"] + rep["findings"])


def test_approval_requires_all_recommendations_reviewed(app, logged_in, conn):
    _, aid = _seed(app, conn)
    token = csrf_from(logged_in.get(f"/monitor/clients/sample-roadlines/audits/{aid}").get_data(as_text=True))
    logged_in.post(f"/monitor/clients/sample-roadlines/audits/{aid}/approve", data={"csrf_token": token})
    assert conn.execute("SELECT approved FROM site_audits WHERE id=?", (aid,)).fetchone()[0] == 0
    for (rid,) in conn.execute("SELECT id FROM recommendations WHERE audit_id=?", (aid,)).fetchall():
        logged_in.post(f"/monitor/clients/sample-roadlines/recommendations/{rid}", data={"review_status": "approved", "csrf_token": token})
    logged_in.post(f"/monitor/clients/sample-roadlines/audits/{aid}/approve", data={"csrf_token": token})
    assert conn.execute("SELECT approved FROM site_audits WHERE id=?", (aid,)).fetchone()[0] == 1
    html = logged_in.get(f"/monitor/clients/sample-roadlines/audits/{aid}/report").get_data(as_text=True)
    assert "DRAFT — not yet reviewed" not in html


def test_rescore_keeps_reviewed_recommendations(app, conn):
    from radynta.audit.pipeline import score_and_store
    _, aid = _seed(app, conn)
    rid, title = conn.execute("SELECT id, title FROM recommendations WHERE audit_id=? LIMIT 1", (aid,)).fetchone()
    conn.execute("UPDATE recommendations SET review_status='approved' WHERE id=?", (rid,))
    conn.commit()
    score_and_store(conn, aid)
    titles = [r[0] for r in conn.execute("SELECT title FROM recommendations WHERE audit_id=?", (aid,))]
    assert titles.count(title) == 1
    assert conn.execute("SELECT review_status FROM recommendations WHERE id=?", (rid,)).fetchone()[0] == "approved"


# --------------------------------------------------- providers & runner ---

def test_missing_credentials_give_explicit_error_and_no_data():
    with pytest.raises(ProviderNotConfigured, match="PERPLEXITY_API_KEY"):
        get_provider("perplexity", Settings())
    with pytest.raises(ProviderNotConfigured, match="OPENAI_MODEL"):
        get_provider("openai", Settings(openai_api_key="sk-test"))


class _FakeHTTP:
    def __init__(self, payloads):
        self.payloads = list(payloads)

    def post(self, url, **kw):
        status, body = self.payloads.pop(0)

        class R:
            status_code = status
            text = str(body)

            def json(self_inner):
                return body
        return R()


def test_perplexity_parsing_and_failed_run_handling(app, conn, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    cid = upsert_client(conn, dict(SAMPLE_CLIENT, slug="pp"), is_sample=True)
    ok = {"model": "sonar", "choices": [{"message": {"content": "Sample Roadlines runs FTL Mumbai–Pune."}}],
          "citations": ["https://www.sample-roadlines.example/services/"], "search_results": [{"url": "https://directory.example/x"}]}
    http = _FakeHTTP([(200, ok), (401, {"error": "bad key"})] + [(500, "err")] * 3 + [(200, ok)] * 5)
    prov = get_provider("perplexity", Settings(perplexity_api_key="k"), session=http)
    bid, m = run_api_batch(conn, cid, prov, delay=0, sleep=lambda s: None)
    assert m["total_runs"] == 5 and m["failed_runs"] == 2 and m["valid_runs"] == 3
    assert m["brand_mention_rate"] == 1.0 and m["client_citation_rate"] == 1.0   # denominators = valid runs
    errs = [r["error"] for r in conn.execute("SELECT error FROM visibility_responses WHERE status='error'")]
    assert any("authentication failed" in e for e in errs) and any("HTTP 500" in e for e in errs)
    origins = {r[0] for r in conn.execute("SELECT origin FROM citations WHERE client_id=?", (cid,))}
    assert origins == {"provider"}


def test_openai_parsing():
    payload = {"model": "m", "output": [{"type": "web_search_call"}, {"type": "message", "content": [
        {"type": "output_text", "text": "Try Example Freight Carriers.", "annotations": [{"type": "url_citation", "url": "https://example-freight.example/"}]}]}]}
    prov = get_provider("openai", Settings(openai_api_key="k", openai_model="m"), session=_FakeHTTP([(200, payload)]))
    res = prov.collect("q")
    assert res.text == "Try Example Freight Carriers." and res.citations == ["https://example-freight.example/"]


def test_provider_unexpected_shape_raises():
    prov = get_provider("perplexity", Settings(perplexity_api_key="k"), session=_FakeHTTP([(200, {"nope": 1})]))
    with pytest.raises(ProviderError):
        prov.collect("q")


def test_manual_import_requires_columns(app, conn, tmp_path):
    cid = upsert_client(conn, dict(SAMPLE_CLIENT, slug="mi"), is_sample=True)
    bad = tmp_path / "bad.csv"
    bad.write_text("question,answer\nx,y\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required columns"):
        import_manual_csv(conn, cid, bad)
