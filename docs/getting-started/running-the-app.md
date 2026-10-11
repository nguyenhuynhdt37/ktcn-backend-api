# 🚀 Hướng Dẫn Khởi Chạy Hệ Thống (Running the Application)

Tài liệu này hướng dẫn chi tiết các phương thức khởi chạy KTCN Backend API phục vụ cả môi trường phát triển (Local Development) và môi trường máy chủ sản xuất (Production Deployment).

---

## 1. 💻 Phương Thức 1: Khởi Chạy Local (Dev Mode - Khuyến Nghị Cho Lập Trình Viên)

Phương thức này giúp lập trình viên tận dụng tính năng tự động reload code (Hot-reloading) khi chỉnh sửa file mà không phải tốn thời gian build lại Docker container.

### Bước 1: Khởi động các dịch vụ nền tảng (PostgreSQL, Redis, MinIO, OmniRoute)
Tại thư mục gốc dự án:
```bash
docker compose -f docker-compose.dev.yml up -d
```

### Bước 2: Kích hoạt môi trường ảo Python
```bash
source venv/bin/activate
# Hoặc nếu dùng uv: source .venv/bin/activate
```

### Bước 3: Khởi chạy Backend bằng Uvicorn
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Giải thích các cờ lệnh:**
- `app.main:app`: Chỉ định file `app/main.py` và biến khởi tạo ứng dụng `app = FastAPI(...)`.
- `--host 0.0.0.0`: Lắng nghe yêu cầu từ tất cả các giao diện mạng (cho phép máy ảo, mobile hoặc máy trong cùng mạng LAN test API).
- `--port 8000`: Cổng mặc định của Backend.
- `--reload`: Tự động tải lại máy chủ mỗi khi có thay đổi trong mã nguồn Python (chỉ dùng trong quá trình dev).

---

## 2. 🐳 Phương Thức 2: Khởi Chạy Toàn Bộ Bằng Docker Compose (Production / Staging)

Phương thức này đóng gói toàn bộ Backend và các dịch vụ đi kèm thành các container biệt lập, sẵn sàng cho môi trường Server hoặc Staging.

### Khởi chạy hệ thống:
```bash
# Build và chạy ngầm toàn bộ các dịch vụ
docker compose -f docker-compose.yml up -d --build
```

### Xem nhật ký hoạt động (Logs):
```bash
# Xem log của dịch vụ backend theo thời gian thực
docker compose logs -f backend

# Xem log của tất cả các container
docker compose logs -f
```

### Dừng hệ thống:
```bash
# Dừng các container (dữ liệu vẫn được giữ trong Docker Volumes)
docker compose down

# Dừng và xóa toàn bộ dữ liệu database, redis, minio (Thận trọng!)
# docker compose down -v
```

---

## 3. 🤖 Vận Hành AI Gateway (OmniRoute / LiteLLM)

Dự án tích hợp **OmniRoute** làm cổng trung gian (AI Router Gateway). Mọi yêu cầu từ backend tới các mô hình AI (như Google Gemini, OpenAI GPT, Claude) đều được định tuyến qua OmniRoute:

### Cấu hình OmniRoute (`./omniroute/config.yaml`):
Nếu bạn muốn bổ sung model hoặc API Key mới:
1. Mở file `omniroute/config.yaml` (hoặc copy từ `omniroute/config.example.yaml`).
2. Khai báo các mô hình AI và Provider API Key tương ứng.
3. Restart lại service OmniRoute:
   ```bash
   docker compose restart omniroute
   ```

OmniRoute lắng nghe tại cổng `localhost:8090` với Master Key mặc định `sk-omniroute-secret-key`.

---

## 4. 🌐 Bảng Danh Mục Các Đường Dẫn Quan Trọng (Web Interfaces & Endpoints)

Khi hệ thống đã khởi chạy thành công, bạn có thể truy cập các dịch vụ qua trình duyệt:

| Dịch vụ / Giao diện | Địa chỉ URL | Thông tin xác thực mặc định | Mô tả |
|---|---|---|---|
| **API Root & Health** | `http://localhost:8000/health` | Không yêu cầu | Trả về trạng thái kiểm tra CSDL, Redis và hệ thống. |
| **Swagger UI (Interactive API Docs)** | `http://localhost:8000/docs` | Không yêu cầu (khi `ENV=development`) | Giao diện kiểm thử trực tiếp toàn bộ REST API endpoints. |
| **ReDoc Documentation** | `http://localhost:8000/redoc` | Không yêu cầu (khi `ENV=development`) | Giao diện tài liệu API chuẩn hóa OpenAPI theo dạng tài liệu đọc. |
| **MinIO Storage Web Console** | `http://localhost:9091` | User: `minio_admin`<br>Pass: `minio_password` | Giao diện quản lý file, xem bucket `university-media`, tạo key. |
| **OmniRoute AI Gateway** | `http://localhost:8090` | Bearer Token: `sk-omniroute-secret-key` | Cổng Gateway định tuyến AI OpenAI-compatible. |
| **PostgreSQL Port** | `localhost:5432` | User: `postgres`<br>Pass: `postgres_password`<br>DB: `university_cms` | Kết nối qua DBeaver, pgAdmin hoặc DataGrip. |
| **Redis Port** | `localhost:6379` | Không mật khẩu | Kết nối qua RedisInsight hoặc CLI `redis-cli`. |

---

## 5. 🔍 Xử Lý Lỗi Thường Gặp Khi Khởi Chạy (Troubleshooting)

### 1. Lỗi `address already in use: 5432` hoặc `6379`
- **Nguyên nhân:** Có dịch vụ PostgreSQL hoặc Redis cài trực tiếp trên máy hoặc một dự án Docker khác đang chiếm dụng cổng này.
- **Xử lý:** 
  - Kiểm tra tiến trình đang chiếm cổng: `lsof -i :5432` hoặc `lsof -i :6379`.
  - Tắt dịch vụ cũ hoặc đổi port mapping trong `docker-compose.dev.yml` (ví dụ `"5433:5432"`).

### 2. Lỗi `database "university_cms" does not exist`
- **Nguyên nhân:** Container postgres khởi tạo trước đó với tên DB khác hoặc chưa chạy script migration.
- **Xử lý:** Chạy `alembic upgrade head`. Nếu container postgres đã tạo volume cũ, hãy xóa volume và khởi tạo lại:
  ```bash
  docker compose -f docker-compose.dev.yml down -v
  docker compose -f docker-compose.dev.yml up -d
  alembic upgrade head
  ```

### 3. Lỗi MinIO connection error
- **Nguyên nhân:** Bucket `university-media` chưa được tạo tự động hoặc MinIO chưa sẵn sàng.
- **Xử lý:** Đăng nhập vào MinIO Console tại `http://localhost:9091`, tạo bucket mới có tên `university-media` và đặt quyền Access Policy là `Public` để portal hiển thị được ảnh.
