"""KDMap pydantic schema — single source of truth."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class NodeType(str, Enum):
    actor = "actor"
    component = "component"
    decision = "decision"
    stage = "stage"
    checkpoint = "checkpoint"


class Reversibility(str, Enum):
    cheap = "green"
    painful = "yellow"
    cement = "red"


class DecisionOption(BaseModel):
    name: str
    pros: list[str] = Field(default_factory=list, max_length=3)
    cons: list[str] = Field(default_factory=list, max_length=3)
    fit_reason: str


class KDMNode(BaseModel):
    id: str
    type: NodeType
    title: str
    summary: str
    terminology: list[str] = Field(default_factory=list)
    stage_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    options: list[DecisionOption] = Field(default_factory=list)
    reversibility: Reversibility | None = None
    switch_trigger: str | None = None
    proof: str | None = None
    requires_external_validation: bool = False


class Stage(BaseModel):
    id: str
    title: str
    order: int


class KDMap(BaseModel):
    mode: Literal["build", "learn"] = "build"
    domain: str
    target_outcome: str
    overview: str
    flows: list[str]
    hard_constraints: list[str]
    out_of_scope: list[str]
    stages: list[Stage]
    nodes: list[KDMNode]
    disclaimer: str | None = None

    @field_validator("stages")
    @classmethod
    def validate_stage_count(cls, v: list[Stage]) -> list[Stage]:
        if not (3 <= len(v) <= 5):
            raise ValueError("stages must contain 3–5 items")
        return v

    @model_validator(mode="after")
    def validate_graph(self) -> KDMap:
        stage_ids = {s.id for s in self.stages}
        node_ids = {n.id for n in self.nodes}

        if len(node_ids) != len(self.nodes):
            raise ValueError("node ids must be unique")

        needs_disclaimer = False

        for node in self.nodes:
            if node.stage_id is not None and node.stage_id not in stage_ids:
                raise ValueError(f"node {node.id}: stage_id '{node.stage_id}' not found")

            for dep in node.depends_on:
                if dep not in node_ids:
                    raise ValueError(f"node {node.id}: depends_on '{dep}' not found")

            if node.type != NodeType.stage and not node.terminology:
                raise ValueError(f"node {node.id}: terminology required (except type=stage)")

            if node.type == NodeType.decision:
                if not (2 <= len(node.options) <= 3):
                    raise ValueError(f"node {node.id}: decision must have 2–3 options")
                if node.reversibility is None:
                    raise ValueError(f"node {node.id}: decision requires reversibility")
                if not node.switch_trigger:
                    raise ValueError(f"node {node.id}: decision requires switch_trigger")

            if node.type == NodeType.checkpoint and not node.proof:
                raise ValueError(f"node {node.id}: checkpoint requires proof")

            if node.requires_external_validation:
                needs_disclaimer = True

        if needs_disclaimer and not (self.disclaimer and self.disclaimer.strip()):
            raise ValueError("disclaimer required when any node has requires_external_validation=True")

        return self
