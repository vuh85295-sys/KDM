# KDM — Experience Matrix (Tri thức tổng hợp)

> **L3 knowledge:** Kiến trúc, bài học, decision log cho KDM.
> Cập nhật sau mỗi milestone hoặc khi có phát hiện mới.

---

## 1. KIẾN TRÚC HỆ THỐNG

### 1.1 Tổng quan
KDM (Knowledge Domain Mapper) — biến ý muốn 2 dòng của người ngoài ngành thành bản đồ hệ thống chuyên môn, nói được ngôn ngữ của chuyên gia.

**Input**: `domain` + `target_outcome` (bắt buộc — cái neo backward mapping)
**Output**: KDMap JSON → Mermaid flowchart (deterministic)

### 1.2 Components

| Module | File | Trách nhiệm |
|--------|------|-------------|
| Schema | `kdm/schema.py` | KDMap pydantic models + validators. Single source of truth. |
| Compiler | `kdm/compiler.py` | KDMap → Mermaid deterministic. Sanitize label. |
| LLM Client | `kdm/llm.py` | UniversalClient (tái dùng DCC). generate_validated 3 lớp retry. |
| Prompts | `kdm/prompts.py` | 2-phase compiler prompt: Domain Adaptation → Backward Mapping. |
| Capsule | `kdm/capsule.py` | KDMap → DCC MemoryCapsule JSON mapping. |
| Server | `kdm/server.py` | FastAPI routes + static mount. |
| Frontend | `static/index.html` | Vanilla JS + mermaid.js CDN. 1 file, không build. |

### 1.3 Key Decisions

| Quyết định | Lựa chọn | Reversibility | Lý do |
|-----------|---------|---------------|-------|
| 2 endpoint LLM | Cloud (map_maker) + local Ollama (expander) | 🟡 Đau nhưng đổi được | Model 7B local ảo giác roadmap ở lần vẽ gốc. Trả vài cent cloud cho Turn 0, expand dùng local. |
| JSON → Mermaid bằng code | Deterministic compiler | 🟢 Đổi rẻ | LLM viết Mermaid sai cú pháp hoa hồng. Code deterministic = test được, sai biết ngay. |
| Frontend 1 file tĩnh | Vanilla JS + CDN | 🟢 Đổi rẻ | Không build step, không dependency. Ai cũng mở được. |
| Export → DCC Capsule | JSON format khớp DCC | 🟢 Đổi rẻ | Tái dùng DCC vault, không cần DB riêng cho v1. |

---

## 2. BÀI HỌC & PATTERN

### 2.1 Pattern đã xác nhận
- **LLM output contract**: "Respond ONLY with a single JSON object..." + format=json / response_format nếu endpoint hỗ trợ.
- **Lưới an toàn 3 lớp**: Parse → pydantic validate → retry 2 lần kèm error → HTTP 422.
- **Backward mapping**: TỪ target_outcome truy ngược, không liệt kê xuôi từ domain.
- **Anti-map**: `out_of_scope` kèm lý do 1 dòng — cắt mọi thứ không phục vụ target_outcome.
- **Decision buộc duyệt**: Mọi decision node phải duyệt (🔴 lên đầu) trước khi export.

### 2.2 Bài học từ Pos_salon áp dụng cho KDM
- ✅ **Milestone rời**: Commit sau mỗi M, test pass mới sang M tiếp.
- ✅ **Snapshot pattern** (gián tiếp): Map snapshot tại thời điểm export → bất biến.
- ✅ **Fallback an toàn**: DCC server không chạy → trả file JSON, không crash.

### 2.3 Cảnh báo
- ⚠️ **Không hardcode từ vựng phần mềm**: Compiler prompt domain-agnostic. Phase 1 tự xác định Actor/flow/constraints từ domain + target_outcome.
- ⚠️ **Không deploy KDM lên production khi chưa có external validation disclaimer** nếu map có `requires_external_validation=True`.
- ⚠️ **Expand không đào sâu vô tận**: depth parameter giới hạn 1-5. Mỗi expand tạo KDMap con.

---

## 3. MILESTONE LOG

| M | Files | Tests | Commits | Trạng thái |
|---|-------|-------|---------|-----------|
| M1 | schema.py, tests/ | 6 | - | ✅ Schema + validators |
| M2 | compiler.py + tests | 5 | - | ✅ Deterministic compiler |
| M3 | llm.py + prompts.py + tests | 12 (offline mock) | 8a66216 | ✅ UniversalClient + 3 lớp retry |
| M4 | capsule.py + tests | 3 | - | ✅ KDMap → DCC Capsule |
| M5 | server.py + kdm_config.json | - | - | ✅ FastAPI port 8790 |
| M6 | static/index.html | - | 2deec90 → d92026e | ✅ Pan/Zoom + popup + event delegation |
| **V1.1** | Toàn bộ | **36/36** | d92026e | ✅ E2E: wish → map → duyệt → capsule |

### V1.1 VERIFIED E2E (2026-07-08)
Bảng verify:
1. ✅ Map vẽ + khai quật component/actor ngầm (Gemini map_maker)
2. ✅ Popup 3 loại node, terminology chuẩn chuyên gia
3. ✅ Expand qua Ollama local — raw_decode sống trong sản xuất
4. ✅ Pan/zoom/fit — vendor local, verify bằng console log
5. ✅ Màn duyệt quyết định — radio + pros/cons render đúng
6. ✅ Export capsule — global_context đủ bộ: flows, hard constraints ĐỊNH LƯỢNG, anti-map kèm lý do

### Sprint lessons (v1.1)
- "Extra data" = chữ ký model nhỏ ép JSON → raw_decode (áp dụng cả Compactor DCC)
- CDN không tin được → vendor local (~30KB, 100% offline-capable)
- UI tính năng độc lập phải fail độc lập (try/catch + guard + console.warn)
- Verify bằng số đo (getComputedStyle, ratio log), không nhìn mắt
- Bug trong chat phải vào session CÙNG LƯỢT — chat là bộ nhớ tạm, session là bộ nhớ đội

## 4. LƯU Ý KỸ THUẬT
- Export DCC dùng `global_context` thay vì `context_summary` (khớp schema DCC thực tế)
- Server port: 8790 (không phải 8788 như spec)
- map_maker mặc định gpt-4o-mini, cần API key
- expander dùng Ollama local (đã reachable)
- Tab duyệt: phải duyệt hết 🔴 trước khi export

### Cảnh báo bổ sung v1.1
- ⚠️ Ô "Lý do" decision 🟡/🔴 có thể rỗng → fallback fit_reason của option đã chọn
- ⚠️ Topic slug cần cắt ~50 ký tự + transliterate "đ"→"d"

---

## 5. REFERENCE
- **Spec gốc**: `KDM_SPEC.md`
- **DCC reference**: `/Volumes/Ruka_data/dcc/` — UniversalClient pattern, MemoryCapsule schema
- **Pos_salon reference**: `/Volumes/Ruka_data/pos_salon/` — R-System convention
