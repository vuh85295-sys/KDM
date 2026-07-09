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
- **DCC URL**: http://localhost:8888 (PID 91046, code v4 Immune System)
- **Run KDM**: `cd /Volumes/Ruka_data/KDM && source .venv/bin/activate && python -m kdm.server`

### Sprint B: 🏆 ECOSYSTEM VERIFIED (2026-07-09)
- **Tầng Actor**: ✅ Hiến pháp trói được cả Qwen 7B (5/5) lẫn Gemini (4/4)
- **Tầng Compactor**: ✅ Immune System v4 (57 tests) — bytes-frozen global_context
- **Vòng khép kín E2E**: Wish → KDM → duyệt 🔴 → export → POST /api/capsule → Vault → Actor → Compactor → ký ức tiến hóa

### KDM — V1.1 ✅ E2E VERIFIED (36 tests)
- **Chưa thử lửa**: Khóa Export khi còn node 🔴

### Backlog v1.2
- Compactor tự phong 🔴 (cap 🟡, 🔴 chỉ từ KDM/user confirm)
- Rác turn thô "(turn: ...)" trong current_state
- Ô "Lý do" bắt buộc + model đọc lại xác nhận
- Topic slug ≤50 ký tự, Learn Mode UI, kéo thả map, auth

---

## PHẦN 3 — CONTEXT CHO HERMES

### Quy ước làm việc
- **Spec source**: `KDM_SPEC.md` — do Claude Fable tạo, là spec gốc.
- **Milestone rời**: M1→M6, commit sau mỗi milestone, test pass mới sang tiếp.
- **Cursor**: đọc session.md + spec.md trước khi code.
- **Claude Desktop (Fable)**: viết spec, push vào session.md khi có thay đổi/decision mới.
- **Hermes**: quản lý session.md + experience_matrix_pro.md + checklist.md. Dọn session.md khi ~200 dòng.
- **DCC immune system**: 4 phiên bản v1→v4, 57 tests, repo `vuh85295-sys/DDC`
- **DCC dependency**: KDM export format khớp DCC MemoryCapsule schema.

### Rủi ro kỹ thuật
1. **LLM ảo giác node id** → validation bắt được, retry.
2. **Special chars tiếng Việt trong Mermaid** → compiler sanitize label.
3. **Model 7B local ảo giác roadmap** → map_maker dùng cloud, expand dùng local.
4. **DCC server không chạy** → export fallback file JSON.

---

## PHẦN 4 — BÀI HỌC SPRINT B (experience_matrix)

### Ba lớp phòng thủ ngôn ngữ
1. **Khế ước ngôn ngữ có ví dụ đúng/sai**: 2 vị trí (đầu system + cuối user prompt)
2. **Lưới bắt tự động**: Đếm ký tự có dấu tiếng Việt + CJK detection
3. **Format terminology chuẩn hoá**: Song ngữ

### 8 Định luật Sprint B
1. Capsule inject không luật thi hành = tài liệu tham khảo; model càng mạnh phá càng thuyết phục
2. Hiến pháp phải trói CẢ kẻ nói (Actor) lẫn kẻ ghi (Compactor)
3. Ký ức phải phân vùng ghi: FROZEN (bytes-equal) / GUARDED (append + source filter) / FLUID (có lính gác ngữ nghĩa)
4. "Phép nén đánh rơi chữ KHÔNG" — nén lời từ chối phải giữ phủ định
5. Chất độc luôn tìm vùng không gác: đảo (nói dối) → cộng (pha loãng) → vùng FLUID
6. Validate-or-keep-old: ký ức cũ đúng hơn ký ức hỏng
7. Rút quyền viết thắng thêm lính gác — vùng không cửa không cần khóa
8. Bài test bẫy tự nó đầu độc ký ức — mọi lần thử lửa phải có tẩy độc + khám nghiệm hậu kỳ

---

**📏 Quy tắc**: session.md ~200 dòng → báo Hermes dọn