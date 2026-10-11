# 🛠️ Hướng Dẫn Cài Đặt & Cấu Hình Môi Trường (Installation & Setup)

Tài liệu này cung cấp hướng dẫn chi tiết từng bước để thiết lập môi trường phát triển (Local Development) và chuẩn bị cơ sở hạ tầng cho dự án **KTCN Backend REST API**.

---

## 1. 📋 Yêu Cầu Hệ Thống (Prerequisites)

Trước khi bắt đầu, hãy đảm bảo máy tính của bạn đã cài đặt các công cụ sau:

- **Hệ điều hành:** Linux, macOS hoặc Windows (WSL2 khuyến nghị).
- **Python:** Phiên bản `3.12` trở lên (Khuyến nghị dùng `python 3.12`).
- **Trình quản lý gói:** `pip` hoặc `uv` (công cụ cực nhanh cho Python).
- **Docker & Docker Compose:** Docker Engine phiên bản `24.0+` và Docker Compose v2.
- **Git:** Phiên bản `2.30+`.

---

## 2. 📥 Clone Repository & Thiết Lập Môi Trường Ảo

### Bước 1: Sao chép mã nguồn
```bash
git clone https://github.com/nguyenhuynhdt37/ktcn-backend-api.git
cd ktcn-backend-api
```

### Bước 2: Tạo và kích hoạt Virtual Environment

**Cách 1: Sử dụng Python venv truyền thống**
```bash
# Tạo môi trường ảo
python3 -m venv venv

# Kích hoạt trên macOS / Linux:
source venv/bin/activate

# Kích hoạt trên Windows (PowerShell):
# .\venv\Scripts\Activate.ps1
```

**Cách 2: Sử dụng công cụ `uv` (Khuyên dùng vì tốc độ tải cực nhanh)**
```bash
uv venv --python 3.12
source .venv/bin/activate
```

### Bước 3: Cài đặt các gói phụ thuộc (Dependencies)
```bash
# Cài đặt qua pip:
pip install --upgrade pip
pip install -r requirements.txt

# Hoặc qua uv:
# uv pip install -r requirements.txt
```

---

## 3. ⚙️ Cấu Hình Biến Môi Trường (.env)

Sao chép file mẫu `.env.example` thành `.env`:
```bash
cp .env.example .env
```

### Bảng giải thích chi tiết các tham số cấu hình trong `.env`:

| Nhóm | Biến môi trường | Giá trị mặc định | Giải thích chi tiết |
|---|---|---|---|
| **Dự án** | `PROJECT_NAME` | `"University Portal Backend"` | Tên ứng dụng hiển thị trên Swagger và log. |
| | `ENV` | `"development"` | Môi trường chạy (`development`, `staging`, `production`). Khi ở `development`, Swagger UI và ReDoc được bật công khai. |
| | `DEBUG` | `true` | Bật/tắt chế độ debug và log chi tiết. |
| | `API_V1_STR` | `"/api/v1"` | Tiền tố chung cho toàn bộ các API v1. |
| **CORS & Host** | `BACKEND_CORS_ORIGINS` | `'["http://localhost:3000", "http://localhost:5173"]'` | Danh sách nguồn gốc (origins) được phép gọi API (JSON array). |
| | `ALLOWED_HOSTS` | `'["*"]'` | Danh sách host được chấp nhận qua middleware `TrustedHostMiddleware`. |
| **Bảo mật** | `SECRET_KEY` | *Bắt buộc sinh chuỗi bí mật* | Khóa dùng để ký JWT Token. **Không dùng giá trị mặc định trên production!** Sinh bằng: `openssl rand -hex 32` |
| | `ALGORITHM` | `"HS256"` | Thuật toán băm chữ ký JWT. |
| | `ACCESS_TOKEN_EXPIRE_MINUTES` | `11520` (8 ngày) | Thời gian sống của JWT Access Token (tính bằng phút). |
| | `REFRESH_TOKEN_EXPIRE_DAYS` | `8` | Thời hạn sống của Refresh Token lưu trong database và Cookie. |
| | `COOKIE_SECURE` | `false` | Đặt `true` khi chạy Production có HTTPS để kích hoạt thuộc tính `Secure` cho Cookie. |
| | `COOKIE_SAMESITE` | `"lax"` | Chính sách gửi cookie giữa các domain (`lax`, `strict`, `none`). |
| **PostgreSQL** | `POSTGRES_SERVER` | `"localhost"` | Địa chỉ máy chủ PostgreSQL. |
| | `POSTGRES_PORT` | `5432` | Cổng kết nối PostgreSQL. |
| | `POSTGRES_USER` | `"postgres"` | Tên tài khoản quản trị PostgreSQL. |
| | `POSTGRES_PASSWORD` | `"postgres_password"` | Mật khẩu truy cập PostgreSQL. |
| | `POSTGRES_DB` | `"university_cms"` | Tên cơ sở dữ liệu. |
| **Redis** | `REDIS_HOST` | `"localhost"` | Địa chỉ máy chủ Redis. |
| | `REDIS_PORT` | `6379` | Cổng Redis. |
| | `REDIS_PASSWORD` | `""` | Mật khẩu Redis (để trống nếu không bật auth). |
| | `REDIS_DB` | `0` | Database index Redis (0 - 15). |
| **Storage MinIO** | `MINIO_ENDPOINT` | `"localhost:9000"` | Địa chỉ API của MinIO/S3 bên ngoài. |
| | `MINIO_INTERNAL_ENDPOINT`| `""` | Địa chỉ nội bộ nếu backend chạy trong docker network kết nối MinIO. |
| | `MINIO_ACCESS_KEY` | `"minio_admin"` | Access Key quản trị MinIO. |
| | `MINIO_SECRET_KEY` | `"minio_password"` | Secret Key truy cập MinIO. |
| | `MINIO_SECURE` | `false` | Đặt `true` nếu MinIO chạy qua SSL/HTTPS. |
| | `MINIO_BUCKET` | `"university-media"` | Tên bucket mặc định lưu trữ file ảnh, tài liệu. |
| **AI Gateway** | `AI_PROVIDER` | `"omniroute"` | Nhà cung cấp AI (`omniroute`, `gemini`, ...). |
| | `AI_BASE_URL` | `"http://localhost:8090"` | Địa chỉ endpoint AI Gateway (OmniRoute / LiteLLM). |
| | `AI_API_KEY` | `"sk-omniroute-secret-key"` | Master Key kết nối OmniRoute AI Gateway. |
| | `AI_DEFAULT_MODEL`| `"gemini-2.5-flash"` | Model mặc định cho sinh text và SEO tags. |
| **Dịch thuật** | `TRANSLATION_MODEL_NAME` | `"facebook/nllb-200-distilled-1.3B"` | Tên HuggingFace model NLLB dùng cho dịch nội bộ nếu bật chế độ offline. |
| | `TRANSLATION_DEVICE` | `"auto"` | Thiết bị xử lý (`cpu`, `cuda`, hoặc `auto`). |
| **Web Push** | `VAPID_PUBLIC_KEY` | `""` | VAPID Public Key cho Web Push Notifications (trình duyệt). |
| | `VAPID_PRIVATE_KEY` | `""` | VAPID Private Key để ký gói tin gửi Web Push. |
| | `VAPID_CLAIM_EMAIL` | `"admin@itup.io.vn"` | Email định danh người quản trị trong gói tin Push. |

---

## 4. 🐳 Khởi Động Hạ Tầng Phụ Thuộc Bằng Docker

Backend cần PostgreSQL (hỗ trợ pgvector), Redis và MinIO để hoạt động. Bạn có thể khởi chạy nhanh các dịch vụ này bằng file `docker-compose.dev.yml`:

```bash
docker compose -f docker-compose.dev.yml up -d
```

Lệnh trên sẽ khởi chạy 4 container nền tảng:
- `be_postgres` (PostgreSQL 17 + pgvector): `localhost:5432`
- `be_redis` (Redis 8 Alpine): `localhost:6379`
- `be_minio` (MinIO Server): API tại `localhost:9000`, Web Console quản trị tại `localhost:9091`
- `omniroute_gateway` (LiteLLM AI Router): `localhost:8090`

Kiểm tra trạng thái các container:
```bash
docker compose -f docker-compose.dev.yml ps
```

---

## 5. 🗄️ Khởi Tạo Cơ Sở Dữ Liệu (Migrations & Seeding)

### Bước 1: Áp dụng Migrations bằng Alembic
Dự án sử dụng Alembic để quản trị schema CSDL đồng bộ với các model SQLAlchemy. Chạy lệnh sau để tạo toàn bộ bảng:

```bash
alembic upgrade head
```

> [!NOTE]
> Lệnh này sẽ duyệt qua toàn bộ 58 migration version trong thư mục `migrations/versions/` và đồng bộ cấu trúc mới nhất vào database `university_cms`.

### Bước 2: Khởi tạo dữ liệu mẫu (Seed Data)
Dự án cung cấp các script khởi tạo dữ liệu mặc định:

```bash
# 1. Khởi tạo tài khoản quản trị Admin và danh sách người dùng ban đầu:
python database/scripts/run_users_seed.py

# 2. Khởi tạo danh sách các Bộ môn / Khoa trực thuộc:
python database/scripts/seed_departments.py

# 3. Khởi tạo danh mục Chức vụ (Positions):
python database/scripts/seed_positions.py

# 4. Khởi tạo dữ liệu Cán bộ, Giảng viên mẫu:
python database/scripts/seed_fake_staffs.py

# 5. Khởi tạo Menu điều hướng và các cờ ngôn ngữ:
python scripts/seed_cute_flags.py
python scripts/seed_footer_menu.py
```

Sau khi hoàn tất, cơ sở dữ liệu đã sẵn sàng với tài khoản quản trị tối cao (Super Admin) mặc định để bạn đăng nhập vào hệ thống.
