"""Compiler prompts — 2-phase domain-agnostic mapping."""

from __future__ import annotations

from kdm.schema import KDMap


PERSPECTIVE_HINTS = {
    "engineer": "Góc nhìn Kỹ sư hệ thống: ưu tiên kiến trúc, trade-off kỹ thuật, khả năng vận hành.",
    "investor": "Góc nhìn Nhà đầu tư: ưu tiên chi phí, thời gian ra thị trường, rủi ro xi măng.",
    "founder": "Góc nhìn Người khởi nghiệp: ưu tiên MVP nhanh, học từ thị trường, tránh over-engineer.",
    "custom": "Góc nhìn tự do: cân bằng giữa thực tế và mục tiêu người dùng.",
}


def build_compiler_system_prompt() -> str:
  schema = KDMap.model_json_schema()
  return f"""Bạn là Strategic Knowledge Architect — biến mô tả ngắn thành bản đồ hệ thống chuyên môn.

Thực hiện 2 phase trong MỘT response:

**Phase 1 — Domain Adaptation**: từ domain + target_outcome, xác định:
(a) các Actor thật sự,
(b) các dòng chảy qua hệ thống (dữ liệu/tiền/nước/điện/người...),
(c) hard constraints của ngành.

**Phase 2 — Backward Mapping**: TỪ target_outcome truy ngược:
1. Khai quật yêu cầu ngầm — component bắt buộc tồn tại về logic
2. Luật 80/20: cắt mọi thứ không phục vụ target_outcome → đẩy vào out_of_scope kèm lý do 1 dòng
3. Ép mọi lựa chọn công nghệ/vật liệu/phương pháp thành decision node — cấm quyết định ngầm
4. Chia 3–5 stage theo tiến hóa; mỗi stage kết bằng ≥1 checkpoint
5. Điền terminology cho từng node (trừ type=stage): "thuật ngữ — giải nghĩa 1 dòng"

Quy tắc:
- node id: slug ascii, unique
- decision: 2–3 options, reversibility (green/yellow/red), switch_trigger
- checkpoint: proof cụ thể, đo được
- disclaimer bắt buộc non-empty nếu có node requires_external_validation=true
- mode luôn "build" trừ khi được yêu cầu khác

Respond ONLY with a single JSON object matching this schema. No markdown fences, no commentary.

JSON Schema:
{schema}"""


def build_compiler_user_prompt(
    domain: str,
    target_outcome: str,
    depth: int = 3,
    perspective: str = "engineer",
) -> str:
    hint = PERSPECTIVE_HINTS.get(perspective, PERSPECTIVE_HINTS["custom"])
    return f"""domain: {domain}
target_outcome: {target_outcome}
depth: {depth} (1=sơ lược, 5=chi tiết — số node và decision tỉ lệ depth)
perspective: {hint}

Tạo KDMap JSON đầy đủ."""


def build_expand_user_prompt(parent_map: KDMap, node_id: str) -> str:
    node = next(n for n in parent_map.nodes if n.id == node_id)
    target = node.proof or node.summary
    return f"""Mở rộng node con cho bản đồ hiện có.

domain (node cha): {node.title}
target_outcome (từ node cha): {target}
summary node cha: {node.summary}
parent domain gốc: {parent_map.domain}
parent target_outcome gốc: {parent_map.target_outcome}

Tạo KDMap JSON con — chi tiết hóa node này thành subgraph độc lập (3–5 stage, nodes mới).
Giữ mode="{parent_map.mode}"."""
