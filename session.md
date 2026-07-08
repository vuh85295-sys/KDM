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
- **URL**: http://localhost:8790
- **Run**: `cd /Volumes/Ruka_data/KDM && source .venv/bin/activate && python -m kdm.server`

### Trạng thái: V1.1 ✅ E2E VERIFIED
- 36/36 tests pass
- Map vẽ + popup + pan/zoom + duyệt quyết định + export capsule — tất cả đã sống
- Expand Ollama: raw_decode handle fail (đã fix parser)
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
- **Commit convention**: `git add kdm/ tests/ static/` (stage cụ thể, tránh file meta).
- **Check analyze**: `pytest tests/ -v` trước mỗi commit milestone.
- **DCC dependency**: KDM export format khớp DCC MemoryCapsule schema.

### Rủi ro kỹ thuật
1. **LLM ảo giác node id** — depends_on/stage_id trỏ đến id không tồn tại → validation bắt được, retry.
2. **Special chars tiếng Việt trong Mermaid** — compiler sanitize label, test unit riêng.
3. **Model 7B local ảo giác roadmap** — lý do map_maker dùng cloud model mạnh, chỉ expand dùng local.
4. **DCC server không chạy** — export fallback: trả file JSON để nạp tay, không crash.

---

## PHẦN 4 — NHIỆM VỤ HIỆN TẠI & CHECKPOINT

### PO (Ruka) — Sprint B: Kết nối KDM → DCC
Mục tiêu: kiểm chứng Actor của DCC có tuân thủ capsule do KDM sinh ra không (kỷ luật anti-map).

1. Bật DCC server → nạp capsule từ KDM vào DCC Vault
2. Chat 5 câu qua DCC với topic vừa nạp, kiểm tra:
   - Câu 1: Nó hiểu đúng dự án?
   - Câu 2: Trả lời database đúng quyết định?
   - 🪤 Câu 3+4: Gài bẫy tính năng mới → nó có kéo về anti-map không?
   - Câu 5: Trỏ đúng checkpoint kế?
3. 5/5 = hệ sinh thái VERIFIED. ≤ 4/5 = cần chỉnh capsule format.

### Sprint kế — v1.2 polish
- Ô "Lý do" bắt buộc decision 🟡/🔴 (fallback: fit_reason của option đã chọn)
- Topic slug: cut ~50 ký tự + transliterate "đ"→"d"
- Theo dõi chất lượng map: actor edges + database node
- Actor nodes thiếu depends_on; thiếu persistent DB

---

## PHẦN 5 — BÀI HỌC SPRINT (cho experience_matrix)
- "Extra data" = chữ ký model nhỏ ép JSON → raw_decode (áp dụng chung, kể cả Compactor DCC)
- CDN không tin được trên mọi mạng → vendor local mọi lib frontend (~30KB)
- Tính năng UI độc lập phải fail độc lập (try/catch tách + guard + console.warn)
- Verify bằng số đo (getComputedStyle, ratio log), không nhìn bằng mắt
- Bug phát hiện trong chat phải vào session CÙNG LƯỢT — chat là bộ nhớ tạm, session là bộ nhớ đội

---

**📏 Quy tắc**: session.md ~200 dòng → báo Hermes dọn
