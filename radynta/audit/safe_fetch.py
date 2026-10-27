"""SSRF-resistant HTTP fetching for auditing untrusted, user-supplied URLs.

Protections:
* only http/https, only ports 80/443, no credentials in URLs
* every hostname is resolved and *all* resolved addresses must be public
  (blocks localhost, RFC1918, link-local incl. 169.254.169.254 cloud metadata,
  CGNAT, multicast, reserved, IPv6 ULA/link-local, IPv4-mapped variants)
* redirects are followed manually and every hop is re-validated
* response bodies are streamed and capped at max_bytes
* connect/read timeouts on every request

Known residual risk: DNS rebinding between our check and the socket connect
(TOCTOU). Mitigate in production by running the crawler on a host whose
egress firewall blocks private ranges.
"""
from __future__ import annotations

import ipaddress
import socket
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol
from urllib.parse import urljoin, urlsplit

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {None, 80, 443}
REDIRECT_CODES = {301, 302, 303, 307, 308}

Resolver = Callable[[str], list[str]]


class FetchBlocked(Exception):
    """The URL is not permitted (scheme, port, private address, ...)."""


def default_resolver(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return sorted({info[4][0] for info in infos})


def is_public_ip(ip_text: str) -> bool:
    ip = ipaddress.ip_address(ip_text.split("%")[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return bool(ip.is_global) and not ip.is_multicast and not ip.is_reserved


def validate_url(url: str, resolver: Resolver = default_resolver) -> str:
    """Return the hostname if url is safe to fetch, else raise FetchBlocked."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise FetchBlocked(f"malformed URL: {url!r}") from exc
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise FetchBlocked(f"scheme not allowed: {parts.scheme!r}")
    if parts.username or parts.password:
        raise FetchBlocked("credentials in URL are not allowed")
    if port not in ALLOWED_PORTS:
        raise FetchBlocked(f"port not allowed: {port}")
    host = (parts.hostname or "").strip(".").lower()
    if not host:
        raise FetchBlocked("URL has no hostname")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise FetchBlocked(f"host not allowed: {host}")

    # Literal IPs are checked directly; names are resolved.
    try:
        ipaddress.ip_address(host)
        addresses = [host]
    except ValueError:
        try:
            addresses = resolver(host)
        except (socket.gaierror, OSError) as exc:
            raise FetchBlocked(f"DNS resolution failed for {host}: {exc}") from exc
    if not addresses:
        raise FetchBlocked(f"no addresses for {host}")
    for addr in addresses:
        if not is_public_ip(addr):
            raise FetchBlocked(f"{host} resolves to non-public address {addr}")
    return host


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int | None
    headers: dict[str, str] = field(default_factory=dict)
    content: bytes = b""
    redirect_chain: list[dict] = field(default_factory=list)
    truncated: bool = False
    elapsed_ms: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and 200 <= self.status_code < 300

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";")[0].strip().lower()

    def text(self) -> str:
        charset = "utf-8"
        for piece in self.headers.get("content-type", "").split(";")[1:]:
            if piece.strip().lower().startswith("charset="):
                charset = piece.split("=", 1)[1].strip().strip('"') or "utf-8"
        try:
            return self.content.decode(charset, errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")


class HttpSession(Protocol):  # what we need from requests.Session (eases testing)
    def get(self, url: str, **kwargs): ...


class SafeFetcher:
    def __init__(
        self,
        session: HttpSession | None = None,
        *,
        user_agent: str = "RADYNTA-AuditBot/0.1",
        timeout: float = 10.0,
        max_bytes: int = 2_000_000,
        max_redirects: int = 5,
        resolver: Resolver = default_resolver,
    ) -> None:
        if session is None:
            import requests  # local import keeps tests independent of network stack

            session = requests.Session()
        self.session = session
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.resolver = resolver

    def fetch(self, url: str) -> FetchResult:
        started = time.monotonic()
        chain: list[dict] = []
        current = url
        result = FetchResult(url=url, final_url=url, status_code=None)
        for _hop in range(self.max_redirects + 1):
            try:
                validate_url(current, self.resolver)
            except FetchBlocked as exc:
                result.error = f"blocked: {exc}"
                break
            try:
                resp = self.session.get(
                    current,
                    allow_redirects=False,
                    stream=True,
                    timeout=(min(5.0, self.timeout), self.timeout),
                    headers={"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.5"},
                )
            except Exception as exc:  # requests raises many subclasses; record, don't crash the crawl
                result.error = f"request failed: {type(exc).__name__}: {exc}"
                break
            try:
                status = int(resp.status_code)
                headers = {k.lower(): v for k, v in resp.headers.items()}
                if status in REDIRECT_CODES and headers.get("location"):
                    nxt = urljoin(current, headers["location"])
                    chain.append({"url": current, "status": status, "location": nxt})
                    current = nxt
                    continue
                body, truncated = self._read_capped(resp)
                result = FetchResult(
                    url=url, final_url=current, status_code=status, headers=headers,
                    content=body, redirect_chain=chain, truncated=truncated,
                )
                break
            finally:
                close = getattr(resp, "close", None)
                if close:
                    close()
        else:
            result.error = f"too many redirects (> {self.max_redirects})"
        result.redirect_chain = chain
        if result.final_url == url and chain:
            result.final_url = current
        result.elapsed_ms = int((time.monotonic() - started) * 1000)
        return result

    def _read_capped(self, resp) -> tuple[bytes, bool]:
        buf = bytearray()
        for chunk in resp.iter_content(chunk_size=16_384):
            if not chunk:
                continue
            buf.extend(chunk)
            if len(buf) > self.max_bytes:
                return bytes(buf[: self.max_bytes]), True
        return bytes(buf), False
