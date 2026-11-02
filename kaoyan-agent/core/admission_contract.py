"""Trusted local admission-link registry and exact public result contract."""

import json
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, field_validator

from schemas import AdmissionLinksQuery, StrictModel

TOOL_NAME = "get_admission_links"
SOURCE_FILE = Path(__file__).resolve().parents[2] / "config/admission-sources.json"
MAX_ENTRY_URLS = 20


class AdmissionSource(StrictModel):
    """A maintainer-registered school with fixed, ordered official entry URLs."""

    code: str = Field(min_length=2, max_length=8, pattern=r"^[a-z]{2,8}$")
    name: str = Field(min_length=1, max_length=255)
    hosts: list[str] = Field(min_length=1, max_length=20)
    entries: list[str] = Field(min_length=1, max_length=MAX_ENTRY_URLS)
    year: int = Field(ge=2000, le=2100)

    @field_validator("hosts")
    @classmethod
    def exact_hosts(cls, value: list[str]) -> list[str]:
        """Keep only lowercase DNS names without schemes, ports or wildcards."""
        if any(
            not host
            or host != host.lower()
            or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for character in host)
            for host in value
        ):
            raise ValueError("ADMISSION_HOST_INVALID")
        if len(set(value)) != len(value):
            raise ValueError("ADMISSION_HOST_DUPLICATE")
        return value

    def validate_url(self, url: str) -> None:
        """Require HTTPS, a registered exact host, and no credentials or fragment."""
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in self.hosts
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or parsed.fragment
        ):
            raise ValueError("ADMISSION_URL_REJECTED")


class AdmissionLinksResult(StrictModel):
    """The complete public link result; no status, evidence or comparison fields."""

    schoolCode: str = Field(min_length=2, max_length=8, pattern=r"^[a-z]{2,8}$")
    schoolName: str = Field(min_length=1, max_length=255)
    registeredYear: int = Field(ge=2000, le=2100)
    entryUrls: list[str] = Field(min_length=1, max_length=MAX_ENTRY_URLS)


def load_sources(path: Path = SOURCE_FILE) -> dict[str, AdmissionSource]:
    """Load the trusted registry and reject duplicates, malformed entries or unknown fields."""
    rows = [AdmissionSource.model_validate(item) for item in json.loads(path.read_text("utf-8"))]
    if not rows or len({row.code for row in rows}) != len(rows):
        raise ValueError("ADMISSION_SOURCES_INVALID")
    if len({row.name for row in rows}) != len(rows):
        raise ValueError("ADMISSION_SOURCES_INVALID")
    for row in rows:
        for url in row.entries:
            row.validate_url(url)
    return {row.code: row for row in rows}


def links_for(source: AdmissionSource) -> AdmissionLinksResult:
    """Project one trusted source into the exact public result without copying other fields."""
    return AdmissionLinksResult(
        schoolCode=source.code,
        schoolName=source.name,
        registeredYear=source.year,
        entryUrls=list(source.entries),
    )


class AdmissionLinksRegistry:
    """Request-independent read-only registry used by the child and client validators."""

    def __init__(self, path: Path = SOURCE_FILE) -> None:
        """Load and validate the local configuration once; perform no network access."""
        self.sources = load_sources(path)

    def get(self, query: AdmissionLinksQuery) -> AdmissionLinksResult:
        """Return one registered school or reject an unknown code without substituting another."""
        source = self.sources.get(query.schoolCode)
        if source is None:
            raise ValueError("ADMISSION_SOURCE_UNKNOWN")
        return links_for(source)

    def catalog(self) -> list[AdmissionLinksResult]:
        """Return every registered school in stable configuration order."""
        return [links_for(source) for source in self.sources.values()]
