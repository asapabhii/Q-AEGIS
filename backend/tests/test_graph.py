"""Unit tests for the knowledge graph path helpers (mocked Neo4j)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.graph.paths import find_document_paths
from app.graph.schemas import GraphNode


class _FakeNode:
    def __init__(self, labels: list[str], props: dict) -> None:
        self.labels = labels
        self._props = props
        self.element_id = props.get("key", "n")

    def __iter__(self):
        return iter(self._props)

    def keys(self):
        return self._props.keys()

    def __getitem__(self, key):
        return self._props[key]

    def get(self, key, default=None):
        return self._props.get(key, default)

    def items(self):
        return self._props.items()

    def values(self):
        return self._props.values()

    def __len__(self):
        return len(self._props)


def test_find_document_paths_builds_summaries() -> None:
    doc_id = uuid4()
    start = _FakeNode(["Document"], {"key": str(doc_id), "title": "x"})
    cloud = _FakeNode(["CloudAsset"], {"key": "cloud-1", "name": "bucket"})
    rel = SimpleNamespace(type="STORED_ON")
    path = SimpleNamespace(nodes=[start, cloud], relationships=[rel])

    session = MagicMock()
    session.run.return_value = [{"path": path}]
    session_cm = MagicMock()
    session_cm.__enter__.return_value = session
    session_cm.__exit__.return_value = False
    driver = MagicMock()
    driver.session.return_value = session_cm
    driver_cm = MagicMock()
    driver_cm.__enter__.return_value = driver
    driver_cm.__exit__.return_value = False

    with patch("app.graph.paths.neo4j_driver", return_value=driver_cm):
        result = find_document_paths(doc_id, max_hops=3)

    assert len(result.paths) == 1
    assert result.paths[0].relationships == ["STORED_ON"]
    assert result.paths[0].hops == 1
    assert isinstance(result.paths[0].nodes[0], GraphNode)


def test_find_document_paths_rejects_bad_hops() -> None:
    with pytest.raises(ValueError):
        find_document_paths(uuid4(), max_hops=0)


def test_driver_kwargs_includes_custom_ca(tmp_path, monkeypatch) -> None:
    from app.config import get_settings
    from app.graph.client import _uri_and_driver_kwargs

    ca = tmp_path / "ca.crt"
    ca.write_text("dummy-ca\n", encoding="utf-8")
    monkeypatch.setenv("QAEGIS_NEO4J_URI", "bolt+s://127.0.0.1:7687")
    monkeypatch.setenv("QAEGIS_NEO4J_USER", "neo4j")
    monkeypatch.setenv("QAEGIS_NEO4J_PASSWORD", "test-password")
    monkeypatch.setenv("QAEGIS_NEO4J_SSL_CA_CERTS", str(ca))
    get_settings.cache_clear()
    try:
        uri, kwargs = _uri_and_driver_kwargs()
    finally:
        get_settings.cache_clear()
    assert uri == "bolt://127.0.0.1:7687"
    assert kwargs["encrypted"] is True
    assert "trusted_certificates" in kwargs
    assert kwargs["auth"] == ("neo4j", "test-password")


def test_driver_kwargs_rejects_missing_ca(monkeypatch) -> None:
    from app.config import get_settings
    from app.graph.client import GraphNotConfiguredError, _uri_and_driver_kwargs

    monkeypatch.setenv("QAEGIS_NEO4J_URI", "bolt+s://127.0.0.1:7687")
    monkeypatch.setenv("QAEGIS_NEO4J_USER", "neo4j")
    monkeypatch.setenv("QAEGIS_NEO4J_PASSWORD", "test-password")
    monkeypatch.setenv("QAEGIS_NEO4J_SSL_CA_CERTS", "C:/missing/ca.crt")
    get_settings.cache_clear()
    try:
        with pytest.raises(GraphNotConfiguredError, match="missing file"):
            _uri_and_driver_kwargs()
    finally:
        get_settings.cache_clear()
