"""KDMap → DCC MemoryCapsule export."""

from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, Field

from kdm.schema import KDMap, NodeType, Reversibility


class CapsuleMetadata(BaseModel):
    last_updated_frame: int = 0
    token_efficiency_saved: str = "0%"


class MemoryCapsule(BaseModel):
    """Matches DCC dcc_middleware.MemoryCapsule schema."""

    topic: str
    global_context: str = ""
    key_decisions: list[str] = Field(default_factory=list)
    current_state: str = ""
    metadata: CapsuleMetadata = Field(default_factory=CapsuleMetadata)

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)


class ApprovedDecision(BaseModel):
    node_id: str
    chosen_option: str
    reason: str


REV_LABEL = {
    Reversibility.cheap: "🟢 rẻ",
    Reversibility.painful: "🟡 đau",
    Reversibility.cement: "🔴 xi măng",
}


def slugify(*parts: str) -> str:
    text = "-".join(p.strip() for p in parts if p.strip())
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text or "kdm-topic"


def export_capsule(kdmap: KDMap, approved: list[ApprovedDecision]) -> MemoryCapsule:
    topic = slugify(kdmap.domain, kdmap.target_outcome)

    context_parts = [
        kdmap.overview,
        "",
        "Dòng chảy:",
        *[f"- {f}" for f in kdmap.flows],
        "",
        "Ràng buộc cứng:",
        *[f"- {c}" for c in kdmap.hard_constraints],
        "",
        "Ngoài phạm vi (anti-map):",
        *[f"- {o}" for o in kdmap.out_of_scope],
    ]
    if kdmap.disclaimer:
        context_parts.extend(["", "Disclaimer:", kdmap.disclaimer])

    decisions_by_id = {d.node_id: d for d in approved}
    key_decisions: list[str] = []
    for node in kdmap.nodes:
        if node.type != NodeType.decision:
            continue
        chosen = decisions_by_id.get(node.id)
        if not chosen:
            continue
        rev = REV_LABEL.get(node.reversibility, "?") if node.reversibility else "?"
        key_decisions.append(
            f"Đã chọn {chosen.chosen_option} cho {node.title}. "
            f"Lý do: {chosen.reason}. Reversibility: {rev}. "
            f"Điểm chuyển đổi: {node.switch_trigger}"
        )

    first_stage = sorted(kdmap.stages, key=lambda s: s.order)[0]
    first_checkpoint = next(
        (n for n in kdmap.nodes if n.type == NodeType.checkpoint and n.stage_id == first_stage.id),
        None,
    )
    cp_text = first_checkpoint.title if first_checkpoint else "chưa xác định"
    current_state = (
        f"Stage hiện tại: {first_stage.title}. Checkpoint kế tiếp: {cp_text}"
    )

    return MemoryCapsule(
        topic=topic,
        global_context="\n".join(context_parts),
        key_decisions=key_decisions,
        current_state=current_state,
    )
