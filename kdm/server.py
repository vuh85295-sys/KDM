"""KDM FastAPI server."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from kdm.capsule import ApprovedDecision, MemoryCapsule, export_capsule, make_topic_slug
from kdm.compiler import kdm_to_mermaid
from kdm.llm import (
    KDMConfig,
    LLMConnectionError,
    MapGenerationError,
    UniversalClient,
    ensure_map_maker_configured,
    generate_validated,
    load_config,
)
from kdm.prompts import build_compiler_user_prompt, build_expand_user_prompt
from kdm.schema import KDMap

logger = logging.getLogger("kdm")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
CONFIG_PATH = Path(__file__).resolve().parent.parent / "kdm_config.json"

app = FastAPI(title="KDM", version="1.0.0")
config: KDMConfig = load_config(CONFIG_PATH)


class MapRequest(BaseModel):
    domain: str
    target_outcome: str
    depth: int = Field(default=3, ge=1, le=5)
    perspective: str = "engineer"


class ExpandRequest(BaseModel):
    map: KDMap
    node_id: str


class ExportCapsuleRequest(BaseModel):
    map: KDMap
    approved_decisions: list[ApprovedDecision] = Field(default_factory=list)


class ExportDCCRequest(ExportCapsuleRequest):
    topic_id: str | None = None


def _map_generation_response(exc: MapGenerationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.last_error,
            "raw_output": exc.raw_output[:2000],
        },
    )


@app.on_event("startup")
def reload_config() -> None:
    global config
    config = load_config(CONFIG_PATH)
    if not config.map_maker.api_key.strip():
        logger.warning(
            "map_maker.api_key trống — POST /map sẽ trả 503 cho đến khi cấu hình key."
        )


@app.get("/health")
async def health() -> dict[str, Any]:
    maker = UniversalClient(config.map_maker)
    expander = UniversalClient(config.expander)
    return {
        "status": "ok",
        "map_maker": {
            "model": config.map_maker.model,
            "base_url": config.map_maker.base_url,
            "reachable": await maker.ping(),
            "api_key_configured": bool(config.map_maker.api_key.strip()),
        },
        "expander": {
            "model": config.expander.model,
            "base_url": config.expander.base_url,
            "reachable": await expander.ping(),
        },
        "dcc_url": config.dcc.base_url,
    }


@app.post("/map", response_model=None)
def create_map(req: MapRequest):
    if not req.domain.strip() or not req.target_outcome.strip():
        raise HTTPException(400, "domain và target_outcome là bắt buộc")

    try:
        ensure_map_maker_configured(config.map_maker)
        client = UniversalClient(config.map_maker)
        user_prompt = build_compiler_user_prompt(
            req.domain.strip(),
            req.target_outcome.strip(),
            req.depth,
            req.perspective,
        )
        kdmap, _, _ = generate_validated(
            client,
            user_prompt,
            domain=req.domain.strip(),
            target_outcome=req.target_outcome.strip(),
        )
        return {"map": kdmap.model_dump(), "mermaid": kdm_to_mermaid(kdmap)}
    except LLMConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except MapGenerationError as exc:
        return _map_generation_response(exc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/expand", response_model=None)
def expand_node(req: ExpandRequest):
    node_ids = {n.id for n in req.map.nodes}
    if req.node_id not in node_ids:
        raise HTTPException(404, f"node_id '{req.node_id}' not found")

    try:
        client = UniversalClient(config.expander)
        user_prompt = build_expand_user_prompt(req.map, req.node_id)
        kdmap, _, _ = generate_validated(client, user_prompt)
        return {
            "map": kdmap.model_dump(),
            "mermaid": kdm_to_mermaid(kdmap),
            "parent_node_id": req.node_id,
        }
    except LLMConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except MapGenerationError as exc:
        return _map_generation_response(exc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/export/capsule")
def export_capsule_endpoint(req: ExportCapsuleRequest) -> dict[str, Any]:
    capsule = export_capsule(req.map, req.approved_decisions)
    return json.loads(capsule.to_json())


@app.post("/export/dcc")
def export_dcc_endpoint(req: ExportDCCRequest) -> dict[str, Any]:
    capsule = export_capsule(req.map, req.approved_decisions)
    topic_id = req.topic_id or make_topic_slug(req.map.domain, req.map.target_outcome)
    dcc_base = config.dcc.base_url.rstrip("/")
    topics_url = f"{dcc_base}/api/topics"

    result: dict[str, Any] = {
        "topic_id": topic_id,
        "capsule": json.loads(capsule.to_json()),
        "dcc_pushed": False,
        "dcc_url": dcc_base,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                topics_url,
                json={
                    "topic_id": topic_id,
                    "description": capsule.global_context[:2000],
                },
            )
            if resp.status_code < 300:
                result["dcc_pushed"] = True
                result["dcc_response"] = resp.json()
            else:
                result["dcc_error"] = resp.text
    except httpx.RequestError:
        result["dcc_error"] = (
            f"DCC không phản hồi tại {topics_url} — kiểm tra port trong kdm_config.json"
        )
    except Exception as exc:
        result["dcc_error"] = str(exc)

    return result


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main() -> None:
    import uvicorn

    uvicorn.run("kdm.server:app", host="0.0.0.0", port=8790, reload=True)


if __name__ == "__main__":
    main()
