"""Test-only child startup guard: no sockets and no HTML/PDF parser imports."""

import builtins
import http.client
import os
import socket
from pathlib import Path

import urllib.request

_FORBIDDEN = frozenset({
    "pdfplumber", "pdfminer", "pypdf", "PyPDF2", "fitz", "pypdfium2",
})
_original_import = builtins.__import__


def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    """Refuse parser modules so a removed crawler cannot silently return."""
    if name.split(".", 1)[0] in _FORBIDDEN:
        raise ImportError("forbidden parser import in admission child")
    return _original_import(name, globals, locals, fromlist, level)


def _blocked(*args, **kwargs):
    """Fail closed for any socket or HTTP connect attempt."""
    raise OSError("network disabled in admission child")


builtins.__import__ = _guarded_import
socket.socket.connect = _blocked
socket.socket.connect_ex = _blocked
socket.create_connection = _blocked
socket.getaddrinfo = _blocked
http.client.HTTPConnection.connect = _blocked
http.client.HTTPSConnection.connect = _blocked
urllib.request.urlopen = _blocked

_events = os.environ.get("ADMISSION_NETWORK_GUARD_EVENTS")
if _events:
    Path(_events).write_text("guarded\n", encoding="utf-8")
