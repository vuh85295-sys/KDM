"""LLM client + validated generation with 3-layer safety net."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError, model_validator

from kdm.prompts import build_compiler_system_prompt
from kdm.schema import KDMap


class LLMConnectionError(Exception):
    """LLM endpoint unreachable or misconfigured."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class MapGenerationError(Exception):
    """LLM responded but output failed validation after retries."""

    def __init__(self, last_error: str, raw_output: str | None = None):
        self.last_error = last_error
        self.raw_output = raw_output or ""
        super().__init__(last_error)


MAP_MAKER_KEY_MISSING = (
    "Chưa cấu hình map_maker.api_key trong kdm_config.json. "
    "Điền key rồi restart server."
)


def ensure_map_maker_configured(endpoint: Endpoint) -> None:
    if not endpoint.api_key.strip():
        raise LLMConnectionError(MAP_MAKER_KEY_MISSING)


class Endpoint(BaseModel):
    base_url: str
    api_key: str = ""
    model: str


class DCCConfig(BaseModel):
    base_url: str = "http://localhost:8788"


class KDMConfig(BaseModel):
    map_maker: Endpoint
    expander: Endpoint
    dcc: DCCConfig = Field(default_factory=DCCConfig)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_dcc_url(cls, data: Any) -> Any:
        if isinstance(data, dict) and "dcc_url" in data and "dcc" not in data:
            data = {**data, "dcc": {"base_url": data["dcc_url"]}}
        return data

    @property
    def dcc_url(self) -> str:
        """Legacy accessor — prefer config.dcc.base_url."""
        return self.dcc.base_url


def load_config(path: str | Path = "kdm_config.json") -> KDMConfig:
    p = Path(path)
    if not p.exists():
        return KDMConfig(
            map_maker=Endpoint(
                base_url="http://localhost:11434/v1",
                api_key="ollama",
                model="qwen2.5:7b-instruct",
            ),
            expander=Endpoint(
                base_url="http://localhost:11434/v1",
                api_key="ollama",
                model="qwen2.5:7b-instruct",
            ),
        )
    return KDMConfig.model_validate_json(p.read_text())


class UniversalClient:
    """OpenAI-compatible chat client (Ollama / OpenAI / Anthropic proxy)."""

    def __init__(self, endpoint: Endpoint, timeout: float = 300.0):
        self.endpoint = endpoint
        self.timeout = timeout

    def chat(self, messages: list[dict[str, str]], json_mode: bool = True) -> str:
        url = self.endpoint.base_url.rstrip("/") + "/chat/completions"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.endpoint.api_key:
            headers["Authorization"] = f"Bearer {self.endpoint.api_key}"

        payload: dict[str, Any] = {
            "model": self.endpoint.model,
            "messages": messages,
            "temperature": 0.4,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMConnectionError(
                f"Không kết nối được LLM tại {self.endpoint.base_url}: {exc}. "
                "Kiểm tra api_key, base_url và trạng thái dịch vụ LLM."
            ) from exc

        content = data["choices"][0]["message"]["content"]
        return content if isinstance(content, str) else json.dumps(content)

    async def ping(self) -> bool:
        try:
            url = self.endpoint.base_url.rstrip("/") + "/models"
            headers = {}
            if self.endpoint.api_key:
                headers["Authorization"] = f"Bearer {self.endpoint.api_key}"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=headers)
                return resp.status_code < 500
        except Exception:
            return False


def _extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()

    start = text.find("{")
    if start < 0:
        raise json.JSONDecodeError("No JSON object found", text, 0)

    decoder = json.JSONDecoder()
    obj, _end = decoder.raw_decode(text[start:])
    if not isinstance(obj, dict):
        raise json.JSONDecodeError("Expected JSON object", text, start)
    return obj


def generate_validated(
    client: UniversalClient,
    user_prompt: str,
    *,
    max_retries: int = 2,
    domain: str | None = None,
    target_outcome: str | None = None,
) -> tuple[KDMap | None, str | None, list[str]]:
    """
    3-layer safety net:
    1. Parse + pydantic validate
    2. Retry with validation errors
    3. Return None + raw on final failure
    """
    system = build_compiler_system_prompt()
    errors: list[str] = []
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]

    raw = ""
    for attempt in range(max_retries + 1):
        try:
            raw = client.chat(messages, json_mode=True)
            data = _extract_json(raw)
            if domain and "domain" not in data:
                data["domain"] = domain
            if target_outcome and "target_outcome" not in data:
                data["target_outcome"] = target_outcome
            kdmap = KDMap.model_validate(data)
            return kdmap, None, errors
        except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
            msg = str(exc)
            errors.append(f"attempt {attempt + 1}: {msg}")
            if attempt < max_retries:
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": (
                        "JSON không hợp lệ. Sửa và trả lại CHỈ JSON object hợp schema.\n"
                        f"Validation error: {msg}"
                    ),
                })

    last_error = errors[-1] if errors else "JSON validation failed after retries"
    raise MapGenerationError(last_error, raw)
