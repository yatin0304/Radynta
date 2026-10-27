"""Test doubles: an in-memory 'website' served through a fake requests.Session."""
from __future__ import annotations


class FakeResp:
    def __init__(self, status: int, body: bytes = b"", headers: dict | None = None, url: str = ""):
        self.status_code = status
        self._body = body
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self.url = url
        self.closed = False

    def iter_content(self, chunk_size: int = 16384):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        self.closed = True


class FakeSession:
    """routes: url -> (status, body:str|bytes, headers|None). Unknown URLs -> 404."""

    def __init__(self, routes: dict):
        self.routes = routes
        self.calls: list[str] = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        status, body, headers = (list(self.routes.get(url, (404, "not found", None))) + [None])[:3]
        if isinstance(body, str):
            body = body.encode("utf-8")
        return FakeResp(status, body, headers or {"Content-Type": "text/html; charset=utf-8"}, url)


def public_resolver(host: str) -> list[str]:
    return ["93.184.216.34"]  # a public address; nothing is actually contacted


def page(title="", desc="", h1="", body="", extra_head="", links=()):
    anchors = "".join(f'<a href="{href}">{text}</a>' for href, text in links)
    return f"""<!doctype html><html lang="en"><head><title>{title}</title>
<meta name="description" content="{desc}"><meta name="viewport" content="width=device-width">{extra_head}</head>
<body><nav>{anchors}</nav><h1>{h1}</h1>{body}</body></html>"""
