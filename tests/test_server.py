"""FastAPI server tests — error responses for /map and /expand."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from kdm.llm import (
    Endpoint,
    KDMConfig,
    LLMConnectionError,
    MAP_MAKER_KEY_MISSING,
    MapGenerationError,
)
from kdm.server import app
from tests.conftest import sample_map

client = TestClient(app)

MAP_BODY = {
    "domain": "test",
    "target_outcome": "test outcome",
    "depth": 2,
    "perspective": "engineer",
}


@pytest.fixture
def configured_config() -> KDMConfig:
    return KDMConfig(
        map_maker=Endpoint(
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            model="gpt-4o-mini",
        ),
        expander=Endpoint(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            model="qwen2.5:7b-instruct",
        ),
    )


def test_map_generation_error_returns_422_with_raw_output(configured_config):
    with (
        patch("kdm.server.config", configured_config),
        patch("kdm.server.generate_validated") as mock_gen,
    ):
        mock_gen.side_effect = MapGenerationError(
            "attempt 3: stages must contain 3–5 items",
            '{"domain": "bad"}' * 300,
        )
        resp = client.post("/map", json=MAP_BODY)

    assert resp.status_code == 422
    body = resp.json()
    assert body["detail"] == "attempt 3: stages must contain 3–5 items"
    assert "raw_output" in body
    assert len(body["raw_output"]) <= 2000


def test_llm_connection_error_returns_503(configured_config):
    with (
        patch("kdm.server.config", configured_config),
        patch("kdm.server.generate_validated") as mock_gen,
    ):
        mock_gen.side_effect = LLMConnectionError(
            "Không kết nối được LLM tại https://api.openai.com/v1: 401 Unauthorized. "
            "Kiểm tra api_key, base_url và trạng thái dịch vụ LLM."
        )
        resp = client.post("/map", json=MAP_BODY)

    assert resp.status_code == 503
    assert "401" in resp.json()["detail"]


def test_empty_api_key_returns_503():
    empty_key_config = KDMConfig(
        map_maker=Endpoint(
            base_url="https://api.openai.com/v1",
            api_key="",
            model="gpt-4o-mini",
        ),
        expander=Endpoint(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            model="qwen2.5:7b-instruct",
        ),
    )
    with patch("kdm.server.config", empty_key_config):
        resp = client.post("/map", json=MAP_BODY)

    assert resp.status_code == 503
    assert resp.json()["detail"] == MAP_MAKER_KEY_MISSING
    assert resp.headers["content-type"].startswith("application/json")


def test_expand_map_generation_error_returns_422(configured_config):
    kdmap = sample_map()
    with (
        patch("kdm.server.config", configured_config),
        patch("kdm.server.generate_validated") as mock_gen,
    ):
        mock_gen.side_effect = MapGenerationError("validation failed", "raw chunk")
        resp = client.post("/expand", json={"map": kdmap.model_dump(), "node_id": "owner"})

    assert resp.status_code == 422
    body = resp.json()
    assert body["detail"] == "validation failed"
    assert body["raw_output"] == "raw chunk"


def test_expand_llm_connection_error_returns_503(configured_config):
    kdmap = sample_map()
    with (
        patch("kdm.server.config", configured_config),
        patch("kdm.server.generate_validated") as mock_gen,
    ):
        mock_gen.side_effect = LLMConnectionError("Ollama offline")
        resp = client.post("/expand", json={"map": kdmap.model_dump(), "node_id": "owner"})

    assert resp.status_code == 503
    assert resp.json()["detail"] == "Ollama offline"
