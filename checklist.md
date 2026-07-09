# KDM — Troubleshooting Checklist

> **Checklist + lỗi hay gặp cross-milestone.**
> Do Hermes quản lý — thêm khi phát hiện pattern lặp lại.
> Không thay thế experience_matrix_pro.md (lỗi theo milestone được ghi ở đó).

---

## 🔥 Deploy Checklist

- [ ] `kdm_config.json` đã config đúng endpoint `map_maker` (cloud) và `expander` (local Ollama) chưa?
- [ ] `pytest tests/ -v` = 0 failures?
- [ ] DCC server có chạy ở `localhost:8788` không? (nếu cần export tự động)
- [ ] Mermaid render thử với ít nhất 1 map thật (không chỉ test mock)
- [ ] Sanitize label test với tiếng Việt có dấu, ngoặc, quote — `pytest tests/test_compiler.py -v`

## 🐛 Lỗi Hay Gặp

- **Lỗi:** LLM trả JSON syntax error / thiếu field
  **Fix:** Retry loop bắt + validation error message đính kèm prompt retry. 2 lần fail → HTTP 422.
  **Spec gốc:** M3 — generate_validated

- **Lỗi:** Mermaid render sai vì label chứa ký tự đặc biệt
  **Fix:** `sanitize_label()` escape `(){}[]"&` → `#40;#41;#123;#125;#91;#93;#quot;&amp;`
  **Spec gốc:** M2 — compiler

- **Lỗi:** depends_on/stage_id trỏ đến id không tồn tại
  **Fix:** pydantic model_validator kiểm tra cross-reference, raise ValueError
  **Spec gốc:** M1 — schema validators

- **Lỗi:** Model local 7B tạo roadmap sai (ảo giác công nghệ)
  **Fix:** map_maker dùng cloud model mạnh cho Turn 0. Expander local chỉ expand node đã tồn tại.
  **Spec gốc:** Section 1 — Kiến trúc

- **Lỗi:** DCC server timeout/offline khi export
  **Fix:** Export fallback → trả file JSON. UI hiển thị link tải. Không crash server.
  **Spec gốc:** M5 — API

- **Lỗi:** Quên stage_id trong node → validation bắt được
  **Fix:** Node không nhất thiết phải có stage_id (node tự do ngoài subgraph). Validation chỉ reject nếu stage_id tồn tại nhưng không match.
  **Spec gốc:** M1 — schema

## 💡 Pattern & Reminder

- **Deterministic > LLM-generated**: Mọi output có thể deterministic (Mermaid, capsule mapping) thì làm bằng code, không qua LLM.
- **Backward mapping**: Từ target_outcome truy ngược, không liệt kê xuôi từ domain.
- **3 lớp an toàn**: Parse → validate (pydantic) → retry (kèm error) → 422.
- **Decision 🔴 lên đầu**: Sort decision node 🔴 (cement) lên đầu màn duyệt — buộc xử lý rủi ro trước.
- **Export = snapshot**: Map tại thời điểm export là bất biến. Không thay đổi sau khi đã đẩy vào DCC.

---

> *Chỉ ghi khi pattern lặp lại 2+ lần. Mỗi entry nhỏ gọn, không dài dòng.*
