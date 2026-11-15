# Chatbot hỏi đáp thông tin website

Trợ lý ảo ở góc dưới bên phải website, trả lời **chỉ dựa trên dữ liệu công khai của trường** (khoa, chương trình đào tạo,
cán bộ, tuyển sinh, liên hệ, tin tức). Thiết kế: [`docs/superpowers/specs/2026-11-15-chatbot-design.md`](../superpowers/specs/2026-11-15-chatbot-design.md).

## Luồng một lượt hỏi

`POST /api/v1/portal/chatbot/messages` với `{session_id, message, lang}` →

1. Kiểm tra đầu vào (`guard.py`): rỗng / quá 500 ký tự / mẫu prompt injection → trả lời cố định, **không gọi model**.
2. FAQ & xã giao (`faq.py`): chào, cảm ơn, tạm biệt, bạn là ai, giúp được gì, gặp tư vấn viên… → trả lời có sẵn, **không gọi model**.
3. Dựng ngữ cảnh (`knowledge.py`): khối lõi (đơn vị, ban lãnh đạo, chương trình, cán bộ; cache 5 phút) + tối đa 4 bài viết khớp từ khóa.
4. Lịch sử do server giữ trong Redis (`session.py`), không nhận lịch sử từ trình duyệt.
5. Gọi `AIService.generate_text` (model `CHATBOT_MODEL`) với chỉ dẫn hệ thống (`prompt.py`).
6. Kiểm tra đầu ra (`output_guard.py`): lộ chỉ dẫn/canary → từ chối; bỏ HTML/Markdown; cắt 2000 ký tự.

## Model: Grok chính, Groq dự phòng

Cấu hình trong cổng LiteLLM (`omniroute/config.yaml`, file này bị git-ignore vì chứa khóa; mẫu ở `config.example.yaml`):

- `grok-chat` → `xai/grok-4-fast-non-reasoning`, khóa `XAI_API_KEY` (đặt trong môi trường container `omniroute`).
  **Xác minh tên model** bằng `GET https://api.x.ai/v1/models` với khóa thật rồi sửa nếu cần.
- Khi Grok lỗi/hết hạn mức, tự chuyển sang `chatbot-groq-fallback` (`groq/openai/gpt-oss-120b`, `reasoning_effort: low`).
  Alias này **không có** fallback tiếp theo nên dữ liệu chatbot không đi sang nhà cung cấp khác.
- Model thực tế xử lý được ghi trong `ai_request_logs` (trang AI Hub).
- Lưu ý: mục `llama-3.3-70b` có sẵn trong cấu hình cũ không còn tồn tại trên tài khoản Groq hiện tại.

## Biến môi trường

`XAI_API_KEY`, `CHATBOT_MODEL` (mặc định `grok-chat`), `CHATBOT_MAX_MESSAGE_CHARS` (500), `CHATBOT_RATE_LIMIT_PER_MIN` (8/IP),
`CHATBOT_HISTORY_TURNS` (10), `CHATBOT_SESSION_TTL_SECONDS` (1800), `CHATBOT_KNOWLEDGE_TTL_SECONDS` (300),
`CHATBOT_MAX_OUTPUT_TOKENS` (500). Xem `.env.example`.

## Sửa nội dung

- Câu FAQ/xã giao và lời đáp: `app/modules/chatbot/faq.py` (`_PHRASES`, `FAQ_ANSWERS`).
- Câu từ chối / "không có thông tin" / chỉ dẫn hệ thống: `app/modules/chatbot/prompt.py`.
- Câu hỏi gợi ý ở khung chat: frontend `src/features/chatbot/data/suggestions.ts` (vi/en).

## Kiểm thử và nghiệm thu

- Unit test: `pytest tests/chatbot -q`.
- Nghiệm thu qua endpoint thật (18 kịch bản: hỏi đúng, thiếu dữ liệu, ngoài phạm vi, injection, giả vai, giả lịch sử, quá dài, xã giao):
  `PYTHONPATH=. python scripts/chatbot_acceptance.py --base http://localhost:8000 [--check-logs]`.
  Chạy lại với model chính và model dự phòng (đổi `CHATBOT_MODEL`) — cả hai phải PASS.

## Giới hạn đã biết

- Bài viết chỉ tìm theo từ khóa (không hiểu nghĩa); câu diễn đạt xa chữ trong bài có thể bỏ sót.
- Chưa streaming; lượt hỏi đầu sau khi khởi động chậm hơn vì dựng khối lõi (về sau lấy từ cache).
- Khớp mẫu injection là lớp phòng thủ đầu tiên, không thay thế các lớp sau (đóng khung dữ liệu, kiểm tra đầu ra, không có công cụ).
