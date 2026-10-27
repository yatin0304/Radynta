from radynta.visibility.response_parser import detect_mention, domain_of, extract_urls, parse_response

CLIENT = {
    "brand_name": "Konkan Roadlines", "brand_aliases": ["Konkan Roadlines Pvt Ltd", "KRL"],
    "primary_domain": "konkanroadlines.example", "extra_domains": ["konkanroadlines.in"],
    "competitors": [
        {"id": 1, "name": "Deccan Freight Movers", "aliases": [], "domain": "deccanfreight.example"},
        {"id": 2, "name": "Sahyadri Cargo", "aliases": ["Sahyadri"], "domain": None},
    ],
}


def test_extract_urls_handles_markdown_and_trailing_punctuation():
    text = "See [site](https://www.konkanroadlines.example/ftl) and https://deccanfreight.example/about). Also (https://x.example/a_(b))."
    urls = extract_urls(text)
    assert "https://www.konkanroadlines.example/ftl" in urls
    assert "https://deccanfreight.example/about" in urls
    assert "https://x.example/a_(b)" in urls


def test_domain_of_strips_www_and_lowercases():
    assert domain_of("https://WWW.Example.COM/path") == "example.com"
    assert domain_of("not a url") == ""


def test_mention_is_word_bounded_and_case_insensitive():
    assert detect_mention("Try konkan roadlines for FTL.", ["Konkan Roadlines"]).mentioned
    assert not detect_mention("KonkanRoadlinesX is unrelated", ["Konkan Roadlines"]).mentioned


def test_short_alias_flagged_ambiguous():
    m = detect_mention("Providers include KRL and others.", ["KRL"])
    assert m.mentioned and m.ambiguous and "shorter than 4" in m.reason


def test_generic_alias_flagged_ambiguous():
    m = detect_mention("Many offer express cargo services", ["Express Cargo"])
    assert m.mentioned and m.ambiguous


def test_longest_alias_preferred_and_context_captured():
    m = detect_mention("We recommend Konkan Roadlines Pvt Ltd for Mumbai–Pune.", ["KRL", "Konkan Roadlines", "Konkan Roadlines Pvt Ltd"])
    assert m.matched == "Konkan Roadlines Pvt Ltd" and not m.ambiguous
    assert "Mumbai" in m.context


def test_mention_vs_citation_are_distinct():
    # brand mentioned, but its site is NOT cited
    r = parse_response("Konkan Roadlines is a known option.", ["https://justdial.example/listing"], CLIENT)
    assert r.brand.mentioned and not r.client_cited
    # brand not mentioned by name, but its site IS cited
    r = parse_response("Several carriers serve this lane.", ["https://konkanroadlines.in/routes"], CLIENT)
    assert not r.brand.mentioned and r.client_cited


def test_competitor_mentions_and_competitor_citations():
    r = parse_response("Options: Deccan Freight Movers and Sahyadri. Source https://deccanfreight.example/x", [], CLIENT)
    names = {m["name"] for m in r.competitor_mentions}
    assert names == {"Deccan Freight Movers", "Sahyadri Cargo"}
    assert any(c.competitor_id == 1 and c.origin == "text" for c in r.citations)


def test_provider_and_text_citations_deduplicated():
    url = "https://konkanroadlines.example/"
    r = parse_response(f"Visit {url}", [url], CLIENT)
    assert len(r.citations) == 1 and r.citations[0].origin == "provider"
