from radynta.visibility.metrics import compare, compute_metrics


def _r(i, status="ok", mentioned=0, ambiguous=0, comps="[]"):
    return {"id": i, "status": status, "brand_mentioned": mentioned if status == "ok" else None,
            "mention_ambiguous": ambiguous, "competitor_mentions": comps}


def test_failed_runs_excluded_from_denominator():
    responses = [_r(1, mentioned=1), _r(2, mentioned=0), _r(3, status="error"), _r(4, status="error")]
    m = compute_metrics(responses, {})
    assert m["valid_runs"] == 2 and m["failed_runs"] == 2
    assert m["brand_mention_rate"] == 0.5          # 1 of 2 valid, NOT 1 of 4
    assert m["failure_rate"] == 0.5


def test_no_valid_runs_gives_none_not_zero():
    m = compute_metrics([_r(1, status="error")], {})
    assert m["brand_mention_rate"] is None and m["client_citation_rate"] is None


def test_citation_and_competitor_frequencies():
    responses = [_r(1, comps='[{"name":"Rival"}]'), _r(2, comps='[{"name":"Rival"},{"name":"Other"}]'), _r(3)]
    cits = {1: [{"domain": "a.com", "is_client_domain": 1}, {"domain": "a.com", "is_client_domain": 1}],
            2: [{"domain": "b.com", "is_client_domain": 0}]}
    m = compute_metrics(responses, cits)
    assert m["client_citation_rate"] == round(1 / 3, 4)
    assert m["competitor_mentions"][0] == {"name": "Rival", "count": 2, "rate": round(2 / 3, 4)}
    assert {"domain": "a.com", "count": 1, "rate": round(1 / 3, 4)} in m["cited_domains"]  # counted per response


def test_compare_reports_percentage_point_change():
    assert compare({"brand_mention_rate": 0.5, "client_citation_rate": None, "failure_rate": 0.1},
                   {"brand_mention_rate": 0.25, "client_citation_rate": 0.1, "failure_rate": 0.1}) == {
        "brand_mention_rate": 25.0, "client_citation_rate": None, "failure_rate": 0.0}
    assert compare({"brand_mention_rate": 0.5}, None)["brand_mention_rate"] is None
