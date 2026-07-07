"""KDM FastAPI server."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from kdm.capsule import ApprovedDecision, MemoryCapsule, export_capsule, slugify
from kdm.compiler import kdm_to_mermaid
from kdm.llm import KDMConfig, UniversalClient, generate_validated, load_config
from kdm.prompts import build_compiler_user_prompt, build_expand_user_prompt
from kdm.schema import KDMap

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


@app.on_event("startup")
def reload_config() -> None:
    global config
    config = load_config(CONFIG_PATH)


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
        },
        "expander": {
            "model": config.expander.model,
            "base_url": config.expander.base_url,
            "reachable": await expander.ping(),
        },
        "dcc_url": config.dcc_url,
    }


@app.post("/map")
def create_map(req: MapRequest) -> dict[str, Any]:
    if not req.domain.strip() or not req.target_outcome.strip():
        raise HTTPException(400, "domain và target_outcome là bắt buộc")

    client = UniversalClient(config.map_maker)
    user_prompt = build_compiler_user_prompt(
        req.domain.strip(),
        req.target_outcome.strip(),
        req.depth,
        req.perspective,
    )
    kdmap, raw, errors = generate_validated(
        client,
        user_prompt,
        domain=req.domain.strip(),
        target_outcome=req.target_outcome.strip(),
    )
    if kdmap is None:
        raise HTTPException(422, detail={"errors": errors, "raw": raw})

    return {"map": kdmap.model_dump(), "mermaid": kdm_to_mermaid(kdmap)}


@app.post("/expand")
def expand_node(req: ExpandRequest) -> dict[str, Any]:
    node_ids = {n.id for n in req.map.nodes}
    if req.node_id not in node_ids:
        raise HTTPException(404, f"node_id '{req.node_id}' not found")

    client = UniversalClient(config.expander)
    user_prompt = build_expand_user_prompt(req.map, req.node_id)
    kdmap, raw, errors = generate_validated(client, user_prompt)
    if kdmap is None:
        raise HTTPException(422, detail={"errors": errors, "raw": raw})

    return {
        "map": kdmap.model_dump(),
        "mermaid": kdm_to_mermaid(kdmap),
        "parent_node_id": req.node_id,
    }


@app.post("/export/capsule")
def export_capsule_endpoint(req: ExportCapsuleRequest) -> dict[str, Any]:
    capsule = export_capsule(req.map, req.approved_decisions)
    return json.loads(capsule.to_json())


@app.post("/export/dcc")
def export_dcc_endpoint(req: ExportDCCRequest) -> dict[str, Any]:
    capsule = export_capsule(req.map, req.approved_decisions)
    topic_id = req.topic_id or slugify(req.map.domain, req.map.target_outcome)

    result: dict[str, Any] = {
        "topic_id": topic_id,
        "capsule": json.loads(capsule.to_json()),
        "dcc_pushed": False,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{config.dcc_url.rstrip('/')}/api/topics",
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
