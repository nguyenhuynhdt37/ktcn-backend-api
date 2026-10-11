# 🧪 Kiểm Thử & Tiêu Chuẩn Chất Lượng Mã Nguồn (Testing & Quality)

Tài liệu này hướng dẫn cách chạy bộ kiểm thử tự động (Unit Test / Integration Test) và duy trì tiêu chuẩn code sạch (Code Quality & Formatting) cho dự án KTCN Backend API.

---

## 1. ⚙️ Cấu Hình Bộ Kiểm Thử (Pytest Configuration)

Bộ kiểm thử được cấu hình trong `pyproject.toml` và sử dụng `pytest-asyncio` để kiểm thử toàn diện các coroutine bất đồng bộ của FastAPI:

```toml
[tool.pytest.ini_options]
minversion = "8.0"
addopts = "-ra -q"
testpaths = ["tests"]
asyncio_mode = "auto"
```

### Các Fixture Cốt Lõi (`tests/conftest.py`):
- `event_loop`: Quản lý vòng lặp sự kiện bất đồng bộ cho toàn bộ session test.
- `db_session`: Khởi tạo và dọn dẹp transaction CSDL cho từng test case.
- `admin_credentials`: Tạo tài khoản quản trị test (`admin_api_test`) và tự động dọn dẹp (cascade delete) sau khi hoàn tất.
- `client`: `httpx.AsyncClient` giả lập HTTP client, tự động gắn header `x-real-ip` ngẫu nhiên để tránh đụng trần Rate Limiting giữa các test case.
- `admin_headers`: Tự động gửi request đăng nhập lấy Access Token JWT và đính kèm vào header `Authorization: Bearer <token>`.
- `mock_ai_service`: Tự động giả lập (Mock) các phản hồi từ AI Hub và Translation Service, tránh phụ thuộc vào mạng Internet hoặc tiêu tốn token thực tế khi chạy kiểm thử.

---

## 2. 🏃‍♂️ Hướng Dẫn Chạy Test (Running Tests)

Đảm bảo môi trường ảo đã kích hoạt và dịch vụ CSDL test đang hoạt động:

```bash
# Chạy toàn bộ test suite
pytest

# Chạy hiển thị chi tiết từng test case và log
pytest -v -s

# Chạy riêng một file test cụ thể
pytest tests/test_article.py

# Chạy test theo từ khóa tên hàm (ví dụ các test về đăng nhập)
pytest -k "test_login"

# Chạy và xuất báo cáo độ bao phủ mã nguồn (Coverage)
pytest --cov=app tests/
```

---

## 3. 🛡️ Quy Tắc Kiểm Thử Bắt Buộc (Strict Engineering Testing Rules)

Tuân thủ nghiêm ngặt quy định phát triển của dự án:

> [!IMPORTANT]
> **Testing Rules:**
> 1. Sau khi viết hoặc chỉnh sửa bất kỳ API hoặc logic Backend nào, **LUÔN LUÔN tự chạy script hoặc lệnh cURL để kiểm chứng thực tế** (kiểm tra validation, HTTP response status code, dữ liệu trả về).
> 2. **Tuyệt đối không** chuyển giao cho Frontend hoặc yêu cầu người dùng thử nghiệm nếu bản thân lập trình viên chưa chạy lệnh kiểm chứng trước.
> 3. Các API nhạy cảm (Auth, Phân quyền, Thao tác dữ liệu quan trọng) bắt buộc phải có test case bao quát cả kịch bản thành công (Happy path) và kịch bản lỗi biên (Edge cases, sai quyền, thiếu trường).

---

## 4. 🧹 Tiêu Chuẩn Định Dạng & Phân Tích Tĩnh (Linting & Formatting)

Dự án áp dụng bộ công cụ phân tích tĩnh tiêu chuẩn của cộng đồng Python hiện đại:

### 1. Kiểm tra Lỗi Cú pháp & Quy chuẩn với Ruff
Ruff là linter siêu nhanh, thay thế cho flake8, pydocstyle và nhiều plugin khác:
```bash
# Kiểm tra lỗi linter
ruff check .

# Tự động sửa các lỗi có thể fix tự động
ruff check --fix .
```

### 2. Định dạng Code tự động với Black
Black đảm bảo tính nhất quán về khoảng trắng, độ dài dòng (88 ký tự) và thụt lề:
```bash
# Tự động format toàn bộ codebase
black .

# Chỉ kiểm tra xem có file nào sai format hay không
black --check .
```

### 3. Sắp xếp Thư viện Import với isort
```bash
isort .
```

### 4. Kiểm tra Kiểu Dữ Liệu Tĩnh với Mypy
Dự án kích hoạt chế độ kiểm tra kiểu nghiêm ngặt (Strict Typing):
```bash
mypy app/
```

---

## 5. 💡 Lệnh Kiểm Tra Nhanh Trước Khi Tạo Git Commit

Trước khi đẩy code lên remote repository, hãy chạy chuỗi lệnh sau để đảm bảo 100% không làm gãy pipeline CI/CD:

```bash
ruff check . && black --check . && mypy app/ && pytest
```
