from radynta.audit.safe_fetch import SafeFetcher
from radynta.audit.scoring import score_audit
from radynta.audit.recommendations import findings_from_scorecard, recommendation_for
from radynta.audit.website_audit import SiteCrawler, parse_page
from tests.fakes import FakeSession, page, public_resolver

ORG = '<script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","name":"Acme"}</script>'


def test_parse_page_extracts_core_facts():
    html = page(
        title="FTL Transport Mumbai to Pune | Acme", desc="d" * 80, h1="FTL transport",
        extra_head='<link rel="canonical" href="/ftl/"><meta name="robots" content="noindex, follow">' + ORG,
        body='<h2>Coverage</h2><h2>Is GPS tracking included?</h2><p>Call <a href="tel:+919876543210">+91 98765 43210</a></p>'
             '<a href="https://wa.me/919876543210">WhatsApp</a><form><input name="name"><input name="phone"></form>'
             '<form role="search"><input name="q"><input type="submit"></form><img src="a.png">'
             '<p>Plot 4, MIDC Road, Bhiwandi 421302. GSTIN 27ABCDE1234F1Z5. Get a quote today.</p>',
        links=[("/about/", "About us"), ("https://other.example/x", "x"), ("#top", "top")],
    )
    d = parse_page("https://acme.example/ftl/", html, "acme.example")
    assert d["title"].startswith("FTL Transport")
    assert d["noindex"] is True
    assert d["canonical"] == "https://acme.example/ftl/"
    assert d["h1"] == ["FTL transport"] and d["h2_count"] == 2
    assert d["question_headings"] == ["Is GPS tracking included?"]
    assert "Organization" in d["schema_types"]
    assert d["tel_links"] == 1 and d["whatsapp_links"] == 1
    assert d["forms"] == [2]  # search form excluded
    assert d["internal_links"] == ["https://acme.example/about/"]
    assert d["external_link_count"] == 1
    assert d["images_missing_alt"] == 1
    assert d["gstin"] == ["27ABCDE1234F1Z5"]
    assert d["address_signal"] is True
    assert "get a quote" in d["cta_matches"]


def test_invalid_json_ld_counted():
    d = parse_page("https://a.example/", page(extra_head='<script type="application/ld+json">{bad json</script>'), "a.example")
    assert d["schema_errors"] == 1


def _site():
    good = "Our trucks cover Maharashtra. " * 60
    return {
        "https://acme.example/robots.txt": (200, "User-agent: *\nDisallow: /private/\nSitemap: https://acme.example/sitemap.xml", {"Content-Type": "text/plain"}),
        "https://acme.example/sitemap.xml": (200, "<urlset><url><loc>https://acme.example/</loc></url><url><loc>https://acme.example/part-load/</loc></url></urlset>", {"Content-Type": "application/xml"}),
        "https://acme.example/": (200, page("Acme Logistics | Road Transport Maharashtra", "x" * 90, "Road transport across Maharashtra", good,
                                             links=[("/part-load/", "Part load"), ("/private/x", "p"), ("/missing/", "m"), ("/login/", "Login")])),
        "https://acme.example/part-load/": (200, page("Part Load Transport | Acme", "y" * 90, "Part load transport", good)),
    }


def test_crawler_respects_robots_limits_and_skips_private_areas():
    session = FakeSession(_site())
    crawler = SiteCrawler(SafeFetcher(session, resolver=public_resolver), max_pages=10, delay=0, sleep=lambda s: None)
    result = crawler.crawl("https://acme.example/")
    urls = [p.url for p in result.pages]
    assert "https://acme.example/private/x" not in session.calls       # robots disallow
    assert "https://acme.example/login/" not in session.calls           # private area skipped
    assert "https://acme.example/missing/" in urls                      # broken link discovered
    assert result.sitemap_url_count == 2 and result.robots_status == 200 and result.https


def test_crawler_page_limit_and_delay():
    sleeps = []
    session = FakeSession(_site())
    crawler = SiteCrawler(SafeFetcher(session, resolver=public_resolver), max_pages=1, delay=1.5, sleep=sleeps.append)
    result = crawler.crawl("acme.example")
    assert len(result.pages) == 1
    assert sleeps and all(s == 1.5 for s in sleeps)
    assert result.discovered_not_crawled >= 1


def test_scoring_end_to_end_with_unmeasured_dimensions():
    session = FakeSession(_site())
    crawl = SiteCrawler(SafeFetcher(session, resolver=public_resolver), max_pages=10, delay=0, sleep=lambda s: None).crawl("https://acme.example/")
    pages = [{"url": p.url, "final_url": p.final_url, "status_code": p.status_code, "data": p.data, "error": p.error} for p in crawl.pages]
    site = {"start_url": crawl.start_url, "site_host": crawl.site_host, "https": crawl.https, "robots_status": 200,
            "robots_blocks_all": False, "sitemap_url": crawl.sitemap_url, "sitemap_status": 200, "sitemap_url_count": 2}
    client = {"services": ["part load", "full truckload"], "geographies": ["Maharashtra", "Gujarat"]}
    card = score_audit(site, pages, client, visibility=None)

    assert card["dimensions"]["ai_visibility"]["measured"] is False
    assert card["measured_possible"] == 75          # 100 minus unmeasured AI visibility (25)
    assert 0 <= card["normalized"] <= 100
    s1 = next(c for c in card["dimensions"]["relevance"]["checks"] if c["code"] == "S1")
    assert "full truckload: not found" in s1["evidence"]
    t9 = next(c for c in card["dimensions"]["technical"]["checks"] if c["code"] == "T9")
    assert t9["awarded"] < 2                         # /missing/ is a 404

    findings = findings_from_scorecard(card)
    assert any(f["code"] == "A1" and f["severity"] == "info" for f in findings)
    rec = recommendation_for(next(f for f in findings if f["code"] == "V1"))
    assert rec["priority"] in {"P1", "P2", "P3"} and rec["hypothesis"].startswith("If")
    assert all("guarantee" not in (recommendation_for(f) or {}).get("hypothesis", "").replace("No outcome is guaranteed", "")
               .replace("does not guarantee", "") for f in findings)


def test_visibility_scored_only_from_valid_runs():
    vis = {"valid_runs": 4, "brand_mention_rate": 0.5, "client_citation_rate": 0.25, "platforms_label": "perplexity-api"}
    card = score_audit({"start_url": "https://a.example/"}, [], {}, vis)
    dim = card["dimensions"]["ai_visibility"]
    assert dim["awarded"] == 7.5 + 2.5 and dim["possible"] == 25


def test_canonical_pointing_inner_pages_to_homepage_is_flagged():
    canon_home = '<link rel="canonical" href="https://acme.example/">'
    pages = [
        {"url": "https://acme.example/", "final_url": "https://acme.example/", "status_code": 200,
         "data": parse_page("https://acme.example/", page("Home title here", extra_head=canon_home), "acme.example")},
        {"url": "https://acme.example/ftl/", "final_url": "https://acme.example/ftl/", "status_code": 200,
         "data": parse_page("https://acme.example/ftl/", page("FTL title here", extra_head=canon_home), "acme.example")},
    ]
    card = score_audit({"start_url": "https://acme.example/", "site_host": "acme.example"}, pages, {})
    t8 = next(c for c in card["dimensions"]["technical"]["checks"] if c["code"] == "T8")
    assert t8["awarded"] == 0.5 and "HOMEPAGE as canonical" in t8["evidence"]
    assert t8["urls"] == ["https://acme.example/ftl/"]
