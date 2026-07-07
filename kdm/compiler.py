"""Deterministic KDMap → Mermaid compiler."""

from __future__ import annotations

import re

from kdm.schema import KDMap, KDMNode, NodeType, Reversibility

REVERSIBILITY_EMOJI = {
    Reversibility.cheap: "🟢",
    Reversibility.painful: "🟡",
    Reversibility.cement: "🔴",
}


def sanitize_label(text: str) -> str:
    """Escape characters that break Mermaid node labels."""
    text = text.replace("\n", " ").replace("\r", " ")
    text = text.replace('"', "#quot;")
    text = text.replace("(", "#40;").replace(")", "#41;")
    text = text.replace("[", "#91;").replace("]", "#93;")
    text = text.replace("{", "#123;").replace("}", "#125;")
    text = text.replace("&", "&amp;")
    return text.strip()


def _node_label(node: KDMNode) -> str:
    label = sanitize_label(node.title)
    if node.type == NodeType.decision and node.reversibility:
        emoji = REVERSIBILITY_EMOJI[node.reversibility]
        label = f"{emoji} {label}"
    return label


def _node_shape(node_id: str, node: KDMNode) -> str:
    label = _node_label(node)
    shapes = {
        NodeType.actor: f'{node_id}(["{label}"])',
        NodeType.component: f'{node_id}["{label}"]',
        NodeType.decision: f'{node_id}{{"{label}"}}',
        NodeType.checkpoint: f'{node_id}[["{label}"]]',
        NodeType.stage: f'{node_id}["{label}"]',
    }
    return shapes[node.type]


def kdm_to_mermaid(kdmap: KDMap) -> str:
    lines: list[str] = ["flowchart TD"]

    stage_order = sorted(kdmap.stages, key=lambda s: s.order)
    stage_titles = {s.id: sanitize_label(s.title) for s in stage_order}

    nodes_by_stage: dict[str | None, list[KDMNode]] = {}
    for node in kdmap.nodes:
        nodes_by_stage.setdefault(node.stage_id, []).append(node)

    for stage in stage_order:
        sid = stage.id
        title = stage_titles[sid]
        lines.append(f'  subgraph {sid}["{title}"]')
        for node in nodes_by_stage.get(sid, []):
            lines.append(f"    {_node_shape(node.id, node)}")
        lines.append("  end")

    for node in nodes_by_stage.get(None, []):
        lines.append(f"  {_node_shape(node.id, node)}")

    for node in kdmap.nodes:
        for dep in node.depends_on:
            lines.append(f"  {dep} --> {node.id}")

    lines.extend([
        "  classDef revGreen fill:#d4edda,stroke:#28a745",
        "  classDef revYellow fill:#fff3cd,stroke:#ffc107",
        "  classDef revRed fill:#f8d7da,stroke:#dc3545",
    ])

    for node in kdmap.nodes:
        if node.type == NodeType.decision and node.reversibility:
            cls = {
                Reversibility.cheap: "revGreen",
                Reversibility.painful: "revYellow",
                Reversibility.cement: "revRed",
            }[node.reversibility]
            lines.append(f"  class {node.id} {cls}")

    return "\n".join(lines) + "\n"


def extract_node_ids(mermaid: str) -> set[str]:
    return set(re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", mermaid))
