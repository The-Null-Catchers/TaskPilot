import ipaddress
import socket
from urllib.parse import urlparse


def validate_webhook_url(url: str, *, production: bool = False) -> str:
    value = url.strip()
    parsed = urlparse(value)
    if parsed.scheme not in ({"https"} if production else {"http", "https"}):
        raise ValueError("Webhook URL must use HTTPS" if production else "Webhook URL must use HTTP or HTTPS")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Webhook URL is invalid")
    if parsed.port is not None and not (1 <= parsed.port <= 65535):
        raise ValueError("Webhook port is invalid")
    _validate_host(parsed.hostname)
    return value


def _validate_host(host: str) -> None:
    normalized = host.strip("[]").lower()
    if normalized in {"localhost", "localhost.localdomain"} or normalized.endswith(".localhost"):
        raise ValueError("Webhook target cannot be local")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, None)}
    except socket.gaierror as exc:
        raise ValueError("Webhook hostname cannot be resolved") from exc
    if not addresses:
        raise ValueError("Webhook hostname cannot be resolved")
    for raw in addresses:
        ip = ipaddress.ip_address(raw)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError("Webhook target resolves to a non-public address")
