"""Constrained public-web fetcher for explicitly supplied research resources."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class UnsafeResourceURL(ValueError):
    """The supplied URL is outside the public-web boundary."""


def validate_public_https_url(url: str) -> None:
    """Allow only public HTTPS hosts, resolving every hostname before a request."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise UnsafeResourceURL("only public HTTPS URLs are supported")
    if not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeResourceURL("URL must include a plain public hostname")
    try:
        port = parsed.port
    except ValueError as exc:
        raise UnsafeResourceURL("URL has an invalid port") from exc
    if port not in {None, 443}:
        raise UnsafeResourceURL("URL must use the default HTTPS port")

    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeResourceURL("URL hostname could not be resolved") from exc
    if not addresses:
        raise UnsafeResourceURL("URL hostname did not resolve to an address")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise UnsafeResourceURL("URL must not resolve to a private or reserved address")


class _PublicRedirectHandler(HTTPRedirectHandler):
    max_redirections = 3

    def redirect_request(
        self,
        request: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request | None:
        # Redirect targets are new, untrusted network destinations. Validate
        # each before urllib has an opportunity to request it.
        validate_public_https_url(newurl)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def open_public_https(request: Request, *, timeout: int) -> Any:
    """Open a validated request and revalidate every redirect destination."""
    validate_public_https_url(request.full_url)
    # Do not inherit proxy settings from the machine. A configured local proxy
    # would otherwise undermine this public-network-only fetch boundary.
    return build_opener(ProxyHandler({}), _PublicRedirectHandler()).open(request, timeout=timeout)
