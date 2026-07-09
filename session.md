# KDM — Session (Hiến pháp Dự án)
> 📜 HIẾN PHÁP — Bộ nhớ dùng chung cho Claude + Cursor + Hermes.
> ĐỌC TRƯỚC khi làm việc. Hermes quản lý file này.
> Repo: /Volumes/Ruka_data/KDM · HEAD: `d92026e`

---

## PHẦN 1 — QUYẾT ĐỊNH KIẾN TRÚC (locked)

### Tier 1 — BẮT BUỘC (vi phạm = dừng)
- **LLM chỉ trả JSON theo schema cứng.** KHÔNG BAO GIỜ cho LLM viết Mermaid. App tự compile JSON → Mermaid bằng code deterministic (M2 compiler).
- **2 endpoint LLM**: `map_maker` (cloud model mạnh — vẽ map lần đầu Turn 0) và `expander` (local Ollama — expand node, rẻ, chạy hàng ngày). Config trong `kdm_config.json`.
- **Export → DCC MemoryCapsule JSON**: map sau khi duyệt decision → push vào DCC Vault (nếu đang chạy) hoặc tải file JSON.
- **Pydantic v2** là single source of truth cho mọi schema. Validation cứng 3 lớp (parse → retry → 422).
- **Frontend 1 file**: `static/index.html` (vanilla JS + mermaid.js CDN). KHÔNG Streamlit, không build step.

### Stack & Pattern
- FastAPI + pydantic v2 + httpx. Python 3.11+.
- UniversalClient tái dùng pattern từ DCC (base_url, api_key, model per role).
- Retry loop: validate → fail → retry tối đa 2 lần kèm validation error → HTTP 422.
- Compiler deterministic: `kdm_to_mermaid(kdmap: KDMap) → str`, có sanitize label (dấu ngoặc, quote, ký tự đặc biệt tiếng Việt).
- Milestone rời (M1→M6). Commit sau mỗi M, test pass mới sang M tiếp.

### Kiến trúc
```
[Browser: index.html + mermaid.js]
        │ REST
        ▼
[FastAPI: kdm_server.py] ── validate JSON (pydantic) ── retry loop
        │
        ▼
[UniversalClient]
   ├── map_maker  : cloud model mạnh (vẽ map lần đầu — Turn 0)
   └── expander   : local Ollama (expand node, rẻ, chạy hàng ngày)
        │
        ▼
[Export] → DCC MemoryCapsule JSON → POST vào DCC Vault (topic mới)
```

---

## PHẦN 2 — TRẠNG THÁI HIỆN TẠI

### SERVER
- **KDM URL**: http://localhost:8790
- **DCC URL**: http://localhost:8888 (PID 57652, code v3 Immune System)
- **Run KDM**: `cd /Volumes/Ruka_data/KDM && source .venv/bin/activate && python -m kdm.server`

### Trạng thái: ECOSYSTEM VERIFIED ✅
- **Tầng Actor**: ✅ Hiến pháp trói được cả model yếu (Qwen 7B) lẫn khôn (Gemini 2.5 Pro)
  - build_actor_system_prompt: 4 luật ⛔ + khế ước ngôn ngữ 3 lớp
- **Tầng Compactor**: ✅ Immune System v3 (51 tests pass)
  - v1: Write zones (LOCKED/GUARDED/FLUID) + fail-safe
  - v2: CJK punctuation net + 🔴 LOCKED exact compare + decision source filter
  - v3: Full-capsule language net + FLUID semantic guard + negation-preserving compaction

### KDM — V1.1 ✅ E2E VERIFIED
- 36/36 tests pass
- **Chưa thử lửa**: Khóa Export khi còn node 🔴 (chưa gặp map có xi măng thật)

### CHƯA LÀM (backlog)
- Learn Mode UI (schema đã hỗ trợ `mode`, UI để v2)
- Auth, multi-user, lưu map server-side
- Sửa map bằng tay trên UI (kéo thả node)
- Tiếng Anh UI
- **Sổ nợ v1.2**: Ô "Lý do" bắt buộc decision 🟡/🔴, Topic slug, Theo dõi chất lượng map

---

## PHẦN 3 — CONTEXT CHO HERMES

### Quy ước làm việc
- **Spec source**: `KDM_SPEC.md` — do Claude Fable tạo, là spec gốc.
- **Milestone rời**: M1→M6, commit sau mỗi milestone, test pass mới sang tiếp.
- **Cursor**: đọc session.md + spec.md trước khi code.
- **Claude Desktop (Fable)**: viết spec, push vào session.md khi có thay đổi/decision mới.
- **Hermes**: quản lý session.md + experience_matrix_pro.md + checklist.md. Dọn session.md khi ~200 dòng.
- **DCC dependency**: KDM export format khớp DCC MemoryCapsule schema.

### Rủi ro kỹ thuật
1. **LLM ảo giác node id** — depends_on/stage_id trỏ đến id không tồn tại → validation bắt được, retry.
2. **Special chars tiếng Việt trong Mermaid** — compiler sanitize label, test unit riêng.
3. **Model 7B local ảo giác roadmap** — lý do map_maker dùng cloud model mạnh, chỉ expand dùng local.
4. **DCC server không chạy** — export fallback: trả file JSON để nạp tay, không crash.

---

## PHẦN 4 — BÀI HỌC SPRINT (experience_matrix)

### Ba lớp phòng thủ ngôn ngữ — Pattern chính thức
1. **Khế ước ngôn ngữ có ví dụ đúng/sai**: Hợp đồng kèm mẫu, đặt ở 2 vị trí (đầu system + cuối user prompt)
2. **Lưới bắt tự động**: Đếm ký tự có dấu tiếng Việt trong output — bằng 0 là English, ép retry. CJK detection (Unicode ranges) cả dấu câu
3. **Format terminology chuẩn hoá**: Song ngữ "Edge Computing — Xử lý dữ liệu gần nguồn..."

### Định luật mới từ Sprint B
- **"Phép nén đánh rơi chữ KHÔNG"** — mọi Compactor phải có luật giữ phủ định khi nén lời từ chối
- Thay đổi phạm vi CHỈ hợp lệ qua POST /api/capsule từ KDM — không lời chat nào đổi được phạm vi
- Lưới validate phải quét toàn capsule, không theo field — kẻ tấn công luôn tìm vùng không gác
- 2 model đọc "data không lồ" (typo) ngược nhau 180° → tính năng v1.2 KDM "model đọc lại xác nhận lý do" là BẮT BUỘC
- "Ký ức cũ đúng hơn ký ức hỏng" — mọi hệ memory có Compactor PHẢI có write-zones + validate-or-keep-old
- "Extra data" = chữ ký model nhỏ ép JSON → raw_decode (áp dụng chung, kể cả Compactor DCC)
- CDN không tin được trên mọi mạng → vendor local mọi lib frontend (~30KB)
- Tính năng UI độc lập phải fail độc lập (try/catch tách + guard + console.warn)
- Verify bằng số đo (getComputedStyle, ratio log), không nhìn bằng mắt
- Bug phát hiện trong chat phải vào session CÙNG LƯỢT — chat là bộ nhớ tạm, session là bộ nhớ đội

---

## PHẦN 5 — KẾT QUẢ SPRINT B (DCC Ecosystem)

### 🎓 BÀI THI TỐT NGHIỆP — KẾT QUẢ 2 CA

**TẦNG ACTOR: ✅ VERIFIED**
- Ca 1 Qwen 7B local: **5/5** (vòng 1 chỉ 3/5 + vỡ tiếng Trung — cùng model, khác mỗi hiến pháp)
- Ca 2 Gemini 2.5 Pro: **4/4** (Q4 mẫu mực — từ chối 🔴 + trích switch_trigger + phản vấn)

**TẦNG COMPACTOR: ✅ VERIFIED (v3 Immune System)**
- v1: Write zones (LOCKED/GUARDED/FLUID) + fail-safe + strip SYSTEM blocks
- v2: CJK punctuation net + 🔴 LOCKED exact compare + decision source filter
- v3: Full-capsule language net + FLUID semantic guard + negation-preserving compaction
- **51 tests** (14 actor + 4 capsule + 33 immune system) + regression ✅

### 📋 VIỆC TIẾP THEO
1. **Tẩy độc topic cũ** — DELETE + POST capsule sạch, thi lại RÚT GỌN (Q3+Q4 x 1 model)
2. **v1.2 KDM** — Ô "Lý do" bắt buộc, Topic slug, Theo dõi chất lượng map
3. **Sprint C** — Sửa map bằng tay UI

---

**📏 Quy tắc**: session.md ~200 dòng → báo Hermes dọn