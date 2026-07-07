"""Offline tests for kdm.llm — mocked HTTP, no API key required."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kdm.llm import (
    Endpoint,
    KDMConfig,
    MapGenerationError,
    UniversalClient,
    _extract_json,
    generate_validated,
    load_config,
)
from tests.conftest import sample_map


def _chat_response(content: str) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return resp


class SequenceClient:
    """Fake UniversalClient that returns canned chat responses in order."""

    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls = 0
        self.messages_history: list[list[dict[str, str]]] = []

    def chat(self, messages: list[dict[str, str]], json_mode: bool = True) -> str:
        self.messages_history.append(messages)
        if self.calls >= len(self.responses):
            raise IndexError("no more mocked responses")
        raw = self.responses[self.calls]
        self.calls += 1
        return raw


def test_load_config_defaults_when_missing(tmp_path):
    missing = tmp_path / "missing.json"
    cfg = load_config(missing)

    assert cfg.map_maker.base_url == "http://localhost:11434/v1"
    assert cfg.map_maker.model == "qwen2.5:7b-instruct"
    assert cfg.expander.model == "qwen2.5:7b-instruct"
    assert cfg.dcc_url == "http://localhost:8788"


def test_load_config_from_file(tmp_path):
    data = {
        "map_maker": {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-test",
            "model": "gpt-4o",
        },
        "expander": {
            "base_url": "http://localhost:11434/v1",
            "api_key": "ollama",
            "model": "qwen2.5:7b",
        },
        "dcc_url": "http://localhost:9999",
    }
    path = tmp_path / "kdm_config.json"
    path.write_text(json.dumps(data))

    cfg = load_config(path)
    assert cfg.map_maker.model == "gpt-4o"
    assert cfg.map_maker.api_key == "sk-test"
    assert cfg.dcc_url == "http://localhost:9999"


def test_extract_json_plain_and_fenced():
    payload = {"mode": "build", "domain": "x"}
    assert _extract_json(json.dumps(payload)) == payload
    fenced = f"```json\n{json.dumps(payload)}\n```"
    assert _extract_json(fenced) == payload


def test_universal_client_chat_sends_json_mode_and_auth():
    endpoint = Endpoint(
        base_url="https://api.example.com/v1",
        api_key="secret",
        model="test-model",
    )
    client = UniversalClient(endpoint, timeout=10.0)
    messages = [{"role": "user", "content": "hello"}]

    with patch("kdm.llm.httpx.Client") as client_cls:
        http = MagicMock()
        client_cls.return_value.__enter__.return_value = http
        http.post.return_value = _chat_response('{"ok": true}')

        result = client.chat(messages, json_mode=True)

    assert result == '{"ok": true}'
    http.post.assert_called_once()
    call_kwargs = http.post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer secret"
    assert call_kwargs["json"]["response_format"] == {"type": "json_object"}
    assert call_kwargs["json"]["model"] == "test-model"


def test_universal_client_chat_without_api_key():
    endpoint = Endpoint(base_url="http://localhost:11434/v1", api_key="", model="local")
    client = UniversalClient(endpoint)

    with patch("kdm.llm.httpx.Client") as client_cls:
        http = MagicMock()
        client_cls.return_value.__enter__.return_value = http
        http.post.return_value = _chat_response("plain text")

        result = client.chat([{"role": "user", "content": "ping"}], json_mode=False)

    assert result == "plain text"
    headers = http.post.call_args.kwargs["headers"]
    assert "Authorization" not in headers
    assert "response_format" not in http.post.call_args.kwargs["json"]


def test_universal_client_ping_reachable():
    endpoint = Endpoint(base_url="http://localhost:11434/v1", api_key="ollama", model="m")
    client = UniversalClient(endpoint)

    with patch("kdm.llm.httpx.AsyncClient") as client_cls:
        http = AsyncMock()
        resp = MagicMock()
        resp.status_code = 200
        http.get.return_value = resp
        client_cls.return_value.__aenter__.return_value = http

        assert asyncio.run(client.ping()) is True
        http.get.assert_awaited_once()


def test_universal_client_ping_unreachable_on_error():
    endpoint = Endpoint(base_url="http://bad-host/v1", api_key="", model="m")
    client = UniversalClient(endpoint)

    with patch("kdm.llm.httpx.AsyncClient") as client_cls:
        http = AsyncMock()
        http.get.side_effect = OSError("connection refused")
        client_cls.return_value.__aenter__.return_value = http

        assert asyncio.run(client.ping()) is False


def test_generate_validated_success():
    kdmap = sample_map()
    client = SequenceClient([json.dumps(kdmap.model_dump(mode="json"))])

    result, raw_err, errors = generate_validated(
        client,
        "make map",
        domain=kdmap.domain,
        target_outcome=kdmap.target_outcome,
    )

    assert raw_err is None
    assert errors == []
    assert result is not None
    assert result.domain == kdmap.domain
    assert len(result.nodes) == len(kdmap.nodes)
    assert client.calls == 1


def test_generate_validated_injects_domain_and_target_outcome():
    kdmap = sample_map()
    data = kdmap.model_dump(mode="json")
    data.pop("domain")
    data.pop("target_outcome")
    client = SequenceClient([json.dumps(data)])

    result, raw_err, errors = generate_validated(
        client,
        "make map",
        domain="Injected domain",
        target_outcome="Injected outcome",
    )

    assert raw_err is None
    assert errors == []
    assert result is not None
    assert result.domain == "Injected domain"
    assert result.target_outcome == "Injected outcome"


def test_generate_validated_retries_then_succeeds():
    kdmap = sample_map()
    client = SequenceClient(
        [
            "not-json",
            json.dumps(kdmap.model_dump(mode="json")),
        ]
    )

    result, raw_err, errors = generate_validated(
        client,
        "make map",
        max_retries=2,
        domain=kdmap.domain,
        target_outcome=kdmap.target_outcome,
    )

    assert result is not None
    assert raw_err is None
    assert len(errors) == 1
    assert "attempt 1" in errors[0]
    assert client.calls == 2
    # Retry should append assistant + correction user message
    final_messages = client.messages_history[-1]
    roles = [m["role"] for m in final_messages]
    assert roles.count("assistant") == 1
    assert roles.count("user") == 2


def test_generate_validated_fails_after_max_retries():
    last_response = '{"domain": "only"}'
    client = SequenceClient(["{bad", "{still bad", last_response])

    with pytest.raises(MapGenerationError) as exc_info:
        generate_validated(client, "make map", max_retries=2)

    assert exc_info.value.last_error
    assert exc_info.value.raw_output == last_response
    assert client.calls == 3


def test_generate_validated_retries_on_schema_validation_error():
    kdmap = sample_map()
    bad = kdmap.model_dump(mode="json")
    bad["stages"] = bad["stages"][:1]  # violates 3–5 stages rule
    good = kdmap.model_dump(mode="json")
    client = SequenceClient([json.dumps(bad), json.dumps(good)])

    result, raw_err, errors = generate_validated(
        client,
        "make map",
        max_retries=1,
        domain=kdmap.domain,
        target_outcome=kdmap.target_outcome,
    )

    assert result is not None
    assert raw_err is None
    assert len(errors) == 1
    assert "3–5" in errors[0]
    assert client.calls == 2
