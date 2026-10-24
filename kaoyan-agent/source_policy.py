"""Shared, explicit source policy. Never infer trust from corpus contents."""
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_SOURCE_POLICY = Path(__file__).resolve().parent.parent / "config/reference-hosts.json"
HOST_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*", re.ASCII)


class ReferenceSourcePolicy:
    def __init__(self, path=None):
        path = Path(path if path is not None else os.environ.get("RAG_SOURCE_POLICY_FILE", DEFAULT_SOURCE_POLICY))
        try:
            if not path.is_absolute():
                raise ValueError()
            value = json.loads(path.read_text(encoding="utf-8"))
            hosts = value.get("allowedHosts") if isinstance(value, dict) else None
            if (set(value) != {"allowedHosts"} or not isinstance(hosts, list) or not hosts
                    or any(not isinstance(host, str) or len(host) > 253
                           or not HOST_PATTERN.fullmatch(host.lower()) for host in hosts)):
                raise ValueError()
            self.allowed_hosts = frozenset(host.lower() for host in hosts)
        except (OSError, ValueError, TypeError, UnicodeError):
            raise ValueError("SOURCE_POLICY_INVALID") from None

    def validate_url(self, value):
        try:
            parsed = urlsplit(value)
            # Accessing port also rejects malformed and out-of-range ports.
            port = parsed.port
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                    or parsed.password is not None or port == 0
                    or any(c.isspace() or ord(c) < 32 for c in value)):
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError("INVALID_SOURCE_URL") from None
        if parsed.hostname.lower() not in self.allowed_hosts:
            raise ValueError("SOURCE_HOST_NOT_ALLOWED")
