"""Connector interface: discover, fetch, normalize, upsert."""

from __future__ import annotations

from typing import Protocol


class Connector(Protocol):
    name: str

    def discover(self) -> list[str]:
        """Return public listing URLs this pass may read."""

    def fetch(self, url: str) -> str:
        """Return the raw public document for one listing."""

    def normalize(self, raw: str, url: str) -> dict | None:
        """Map a document to title, company, city, text and source url."""

    def upsert(self, item: dict) -> str:
        """Insert or update the canonical job. Return created or updated."""
