import pytest

from radynta.audit.safe_fetch import FetchBlocked, SafeFetcher, is_public_ip, validate_url
from tests.fakes import FakeSession, public_resolver


@pytest.mark.parametrize("ip", [
    "127.0.0.1", "10.0.0.5", "172.16.3.4", "192.168.1.1", "169.254.169.254", "100.64.0.1",
    "0.0.0.0", "::1", "fd00::1", "fe80::1", "::ffff:127.0.0.1", "224.0.0.1", "240.0.0.1",
])
def test_private_and_special_addresses_are_not_public(ip):
    assert not is_public_ip(ip)


def test_public_address_is_public():
    assert is_public_ip("93.184.216.34")


@pytest.mark.parametrize("url", [
    "ftp://example.com/", "file:///etc/passwd", "http://localhost/", "http://foo.localhost/",
    "http://127.0.0.1/", "http://[::1]/", "http://169.254.169.254/latest/meta-data/",
    "http://user:pass@example.com/", "http://example.com:8080/", "http://printer.local/",
])
def test_validate_url_blocks_unsafe_urls(url):
    with pytest.raises(FetchBlocked):
        validate_url(url, resolver=public_resolver)


def test_validate_url_blocks_hostname_resolving_to_private_ip():
    with pytest.raises(FetchBlocked, match="non-public"):
        validate_url("https://evil.example/", resolver=lambda h: ["93.184.216.34", "10.0.0.1"])


def test_redirect_to_private_address_is_blocked():
    session = FakeSession({"https://site.example/": (302, "", {"Location": "http://169.254.169.254/latest/"})})
    res = SafeFetcher(session, resolver=public_resolver).fetch("https://site.example/")
    assert res.error and "blocked" in res.error
    assert res.redirect_chain[0]["status"] == 302
    assert session.calls == ["https://site.example/"]  # metadata endpoint never requested


def test_redirect_chain_recorded_and_followed():
    session = FakeSession({
        "http://site.example/": (301, "", {"Location": "https://site.example/"}),
        "https://site.example/": (200, "<html>ok</html>", None),
    })
    res = SafeFetcher(session, resolver=public_resolver).fetch("http://site.example/")
    assert res.ok and res.final_url == "https://site.example/"
    assert [h["status"] for h in res.redirect_chain] == [301]


def test_redirect_loop_stops():
    session = FakeSession({"https://a.example/": (302, "", {"Location": "https://a.example/"})})
    res = SafeFetcher(session, resolver=public_resolver, max_redirects=3).fetch("https://a.example/")
    assert res.error and "too many redirects" in res.error


def test_oversized_body_is_truncated():
    session = FakeSession({"https://big.example/": (200, "x" * 50_000, None)})
    res = SafeFetcher(session, resolver=public_resolver, max_bytes=10_000).fetch("https://big.example/")
    assert res.truncated and len(res.content) == 10_000


def test_network_exception_is_recorded_not_raised():
    class Boom:
        def get(self, url, **kw):
            raise ConnectionError("refused")
    res = SafeFetcher(Boom(), resolver=public_resolver).fetch("https://down.example/")
    assert res.status_code is None and "refused" in res.error
