# Software Spec — KDM (Knowledge Domain Mapper) v1.0 MVP

**Vai trò hệ thống**: Strategic Knowledge Architect — biến ước muốn 2 dòng của người ngoài ngành thành bản đồ hệ thống chuyên môn, nói được ngôn ngữ của chuyên gia.
**Chế độ MVP**: Build Mode (map sản phẩm/hệ thống). Learn Mode để v2, nhưng schema phải hỗ trợ sẵn `mode`.
**Nguyên tắc tối thượng**: LLM chỉ trả JSON theo schema cứng. KHÔNG BAO GIỜ cho LLM viết Mermaid. App tự compile JSON → Mermaid bằng code deterministic.

---

## 1. Kiến trúc tổng thể

```
[Browser: index.html + mermaid.js]
        │ REST
        ▼
[FastAPI: kdm_server.py] ── validate JSON (pydantic) ── retry loop
        │
        ▼
[UniversalClient]  ← tái dùng pattern từ DCC
   ├── map_maker  : cloud model mạnh (vẽ map lần đầu — Turn 0)
   └── expander   : local Ollama (expand node, rẻ, chạy hàng ngày)
        │
        ▼
[Export] → DCC MemoryCapsule JSON → POST vào DCC Vault (topic mới)
```

**Stack**: Python 3.11+, FastAPI, pydantic v2, httpx. Frontend: 1 file `index.html` tĩnh (vanilla JS + mermaid.js CDN). Không Streamlit, không build step.

**Lý do 2 endpoint LLM**: model 7B local ảo giác roadmap "mượt mà sai" ở lần vẽ gốc. Map sai ở gốc = cả hành trình sai. Trả vài cent cloud cho Turn 0, còn expand/duyệt hàng ngày dùng local. Config giống `~/.dcc/config.json`: mỗi role một `Endpoint {base_url, api_key, model}`.

---

## 2. JSON Schema — `KDMap` (pydantic, single source of truth)

> Thiết kế NGƯỢC từ schema `MemoryCapsule` của DCC (topic, context_summary, key_decisions, current_state) để export không cần converter phức tạp.

```python
class NodeType(str, Enum):
    actor = "actor"          # ai dùng / ai tương tác hệ thống
    component = "component"  # khối chức năng (app, database, phòng ngủ, bếp...)
    decision = "decision"    # điểm phải chọn — node quan trọng nhất
    stage = "stage"          # giai đoạn tiến hóa (MVP → mở rộng / thô → hoàn thiện)
    checkpoint = "checkpoint"# bằng chứng năng lực/nghiệm thu, verify được

class Reversibility(str, Enum):
    cheap = "green"    # 🟢 đổi rẻ — chọn đại, sai sửa sau
    painful = "yellow" # 🟡 đổi được nhưng đau
    cement = "red"     # 🔴 xi măng — sai là đập đi làm lại

class DecisionOption(BaseModel):
    name: str
    pros: list[str]          # tối đa 3
    cons: list[str]          # tối đa 3
    fit_reason: str          # vì sao hợp/không hợp với target_outcome NÀY

class KDMNode(BaseModel):
    id: str                              # slug, unique, ascii: "db_choice"
    type: NodeType
    title: str                           # tiếng Việt, ngắn
    summary: str                         # tối đa 2 câu — luật 80/20
    terminology: list[str] = []          # từ vựng chuyên gia của node này,
                                         # format "thuật ngữ — giải nghĩa 1 dòng"
                                         # (điều kiện "vào chuồng gà nói về gà")
    stage_id: str | None                 # node thuộc stage nào
    depends_on: list[str] = []           # id các node tiên quyết → vẽ edge
    # --- chỉ cho type=decision ---
    options: list[DecisionOption] = []
    reversibility: Reversibility | None
    switch_trigger: str | None           # "đổi khi >10k users", "đổi khi cần IoT"
    # --- chỉ cho type=checkpoint ---
    proof: str | None                    # "chạy Qwen 7B qua MLX, đo token/s"
    requires_external_validation: bool = False  # KTS thẩm định, kiểm tra quy hoạch...

class KDMap(BaseModel):
    mode: Literal["build", "learn"] = "build"
    domain: str                          # input người dùng
    target_outcome: str                  # input BẮT BUỘC — cái neo backward mapping
    overview: str                        # 2 dòng bản chất
    flows: list[str]                     # dòng chảy hệ thống LLM nhận diện ở Phase 1
                                         # (dữ liệu/tiền/nước/điện/người...)
    hard_constraints: list[str]          # ràng buộc vật lý/pháp lý của ngành
    out_of_scope: list[str]              # ANTI-MAP — cái KHÔNG làm/học ở scope này
    stages: list[dict]                   # [{id, title, order}]
    nodes: list[KDMNode]
    disclaimer: str | None               # bắt buộc non-empty nếu tồn tại bất kỳ
                                         # node requires_external_validation=True
```

**Validation cứng (pydantic validators)**:
- 3–5 stages; mọi `stage_id`/`depends_on` phải trỏ đến id tồn tại (chống LLM ảo id)
- `type=decision` → bắt buộc `options` (2–3), `reversibility`, `switch_trigger`
- `type=checkpoint` → bắt buộc `proof`
- Mọi node phải có ≥1 terminology, trừ type=stage

---

## 3. Compiler Prompt — 2 phase (domain-agnostic)

Không hardcode từ vựng phần mềm. Một system prompt, hai bước trong cùng 1 call:

**Phase 1 — Domain Adaptation**: từ `domain` + `target_outcome`, xác định:
(a) các Actor thật sự, (b) các dòng chảy qua hệ thống (câu hỏi gốc: *"cái gì chảy qua hệ thống và luật vật lý/pháp lý nào ràng buộc nó?"*), (c) hard constraints của ngành.

**Phase 2 — Backward Mapping**: TỪ target_outcome truy ngược (không liệt kê xuôi từ domain):
1. Khai quật yêu cầu ngầm: những component wish không nhắc nhưng bắt buộc tồn tại về logic (kiểu app quản lý bãi, database chung; bếp, toilet, cầu thang)
2. Luật 80/20: cắt mọi thứ không phục vụ target_outcome → đẩy vào `out_of_scope` kèm lý do 1 dòng
3. Ép mọi lựa chọn công nghệ/vật liệu/phương pháp thành decision node — cấm quyết định ngầm
4. Chia stage theo tiến hóa; mỗi stage kết bằng ≥1 checkpoint
5. Điền terminology cho từng node bằng đúng từ chuyên gia trong ngành dùng

**Output contract**: "Respond ONLY with a single JSON object matching the provided schema. No markdown fences, no commentary." Kèm full JSON schema (`KDMap.model_json_schema()`) trong system prompt. Nếu endpoint hỗ trợ (Ollama/OpenAI) → bật `format=json` / `response_format={"type":"json_object"}`, không chỉ ép bằng prompt.

**Lưới an toàn 3 lớp** (hàm `generate_validated(prompt) -> KDMap`):
1. Parse + pydantic validate
2. Fail → retry tối đa 2 lần, đính kèm validation error message vào prompt retry
3. Vẫn fail → trả HTTP 422 kèm raw output để user thấy, không crash

---

## 4. Mermaid Compiler (deterministic, code thuần)

`kdm_to_mermaid(kdmap: KDMap) -> str`:
- `flowchart TD`; mỗi stage = `subgraph`
- Shape theo type: actor `([...])`, component `[...]`, decision `{...}`, checkpoint `[[...]]`
- Decision node: prefix emoji 🟢/🟡/🔴 theo reversibility + `classDef` màu tương ứng
- Edge từ `depends_on`
- **Escape/sanitize label** (dấu ngoặc, quote, ký tự đặc biệt tiếng Việt) — đây là lý do tồn tại của compiler; test unit riêng cho label chứa `(){}[]"&`

---

## 5. API (FastAPI)

| Method | Path | Body | Trả về |
|---|---|---|---|
| POST | `/map` | `{domain, target_outcome, depth:1-5, perspective}` | `{map: KDMap, mermaid: str}` |
| POST | `/expand` | `{map: KDMap, node_id}` | KDMap con của node đó (dùng endpoint `expander` local; node gốc làm domain, proof/summary làm target) |
| POST | `/export/capsule` | `{map: KDMap, approved_decisions: [{node_id, chosen_option, reason}]}` | `MemoryCapsule` JSON |
| POST | `/export/dcc` | như trên + `{topic_id}` | Đẩy thẳng capsule vào DCC server `http://localhost:8788` (nếu đang chạy); fail thì trả file JSON để nạp tay |
| GET | `/health` | — | trạng thái 2 endpoint LLM |

**Mapping export capsule** (khớp schema DCC hiện có):
- `topic` ← slug(domain + target_outcome)
- `context_summary` ← overview + flows + hard_constraints + **out_of_scope (anti-map — để Actor tự kéo user về đường chính)** + disclaimer
- `key_decisions` ← mỗi decision đã duyệt: `"Đã chọn {option} cho {title}. Lý do: {reason}. Reversibility: {màu}. Điểm chuyển đổi: {switch_trigger}"`
- `current_state` ← `"Stage hiện tại: {stage đầu tiên}. Checkpoint kế tiếp: {checkpoint đầu của stage đó}"`

---

## 6. Frontend — `static/index.html` (1 file duy nhất)

1. **Form**: ô Domain, ô Target Outcome (required, placeholder ví dụ ParkingLink wish), slider Depth 1–5, dropdown Perspective (Kỹ sư hệ thống / Nhà đầu tư / Người khởi nghiệp / Tự do nhập)
2. **Map view**: render mermaid; click node → panel bên phải hiện summary, terminology, options; nút "Expand" gọi `/expand` render map con
3. **Màn duyệt Decision** (bước bắt buộc trước export): liệt kê mọi decision node, sort 🔴 lên đầu; mỗi node radio chọn option + ô lý do; chưa duyệt hết node 🔴 thì nút Export bị khóa
4. **Export**: nút "Khởi tạo Project (→ DCC)" và nút "Tải Capsule JSON"
5. Hiển thị disclaimer nổi bật nếu map có `requires_external_validation`

Không framework, không build. mermaid.js qua CDN.

---

## 7. Cấu trúc thư mục & thứ tự thực thi (cho Cursor)

```
kdm/
├── kdm/schema.py        # M1 — pydantic models + validators + tests
├── kdm/compiler.py      # M2 — kdm_to_mermaid + sanitize + tests
├── kdm/llm.py           # M3 — UniversalClient, generate_validated (3 lớp)
├── kdm/prompts.py       # M3 — compiler prompt 2-phase
├── kdm/capsule.py       # M4 — KDMap → MemoryCapsule mapping + tests
├── kdm/server.py        # M5 — FastAPI, mount static
├── static/index.html    # M6
├── kdm_config.json      # endpoints map_maker/expander
└── tests/
```

**Milestone rời, commit sau mỗi M, test pass mới sang M tiếp** (đúng convention pos_salon). M1–M2 và M4 test offline không cần LLM (mock). M3 test với Ollama local.

## 8. Ngoài scope v1 (anti-map của chính KDM)

- Learn Mode UI (schema đã hỗ trợ, UI để v2)
- Auth, multi-user, lưu map server-side (map sống trong browser + file JSON export)
- Sửa map bằng tay trên UI (v2: kéo thả node)
- Tiếng Anh UI (tiếng Việt trước)
