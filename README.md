# ⚙️ KTCN Backend REST API — Trường Kỹ Thuật và Công Nghệ (Đại Học Vinh)

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7.0+-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![MinIO](https://img.shields.io/badge/MinIO-S3_Storage-C72C48?style=for-the-badge&logo=minio&logoColor=white)](https://min.io/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

Máy chủ Backend RESTful API hiệu năng cao phục vụ toàn diện **Cổng thông tin điện tử (Client Portal)** và **Hệ thống Quản trị nội dung (Admin Portal)** của **Trường Kỹ Thuật và Công Nghệ — Đại Học Vinh**.

Hệ thống được xây dựng trên nền tảng **FastAPI bất đồng bộ (AsyncIO)**, **PostgreSQL (kèm pgvector)**, **Redis Cache & Session**, **MinIO S3 Object Storage**, tích hợp trí tuệ nhân tạo **Google Gemini / OmniRoute** và mô hình dịch thuật cục bộ mã nguồn mở **Facebook NLLB-200**.

---

## 📚 Hệ Thống Tài Liệu Kỹ Thuật Chính Thức

Toàn bộ tài liệu chi tiết từ thiết lập, kiến trúc đến sơ đồ luồng hoạt động được tổ chức quy chuẩn trong thư mục [`docs/`](./docs/README.md):

| Nhóm Tài Liệu | Mô Tả | Đường Dẫn Trực Tiếp |
|---|---|---|
| **01. Bắt Đầu** | Hướng dẫn cài đặt phụ thuộc, cấu hình `.env`, chạy Uvicorn, Docker & Migrations | 📖 [docs/01-getting-started/](./docs/01-getting-started/installation.md) |
| **02. Kiến Trúc** | Modular Monolith, AsyncIO, Middleware Pipeline, Thiết kế CSDL & Bảo mật RBAC | 🏛️ [docs/02-architecture/](./docs/02-architecture/system-overview.md) |
| **03. Luồng Hoạt Động** | Sơ đồ Mermaid tuần tự các luồng: Auth, Bài viết, Dịch thuật, AI Hub, Real-time SSE | 🔄 [docs/03-feature-flows/](./docs/03-feature-flows/auth-flow.md) |
| **04. Tham Khảo API** | Bảng tra cứu danh mục toàn bộ 24 nhóm API Endpoints (Portal & Admin) | 📑 [docs/04-api-reference/](./docs/04-api-reference/overview.md) |

---

## ✨ Tính Năng Nổi Bật

- 🔐 **Xác Thực Kép & Bảo Mật Chuyên Sâu**:
  - Hỗ trợ đồng thời **HttpOnly Cookies** (bảo vệ chống XSS cho Web) và **Bearer Token** (cho Mobile/API).
  - Phân quyền theo vai trò (RBAC): `super_admin`, `admin`, `editor`.
  - Cơ chế xoay vòng Refresh Token (Token Rotation) và ghi nhận nhật ký thiết bị đăng nhập (`login_histories`).
- 📰 **Vòng Đời Quản Lý Bài Viết & Đa Danh Mục**:
  - Máy trạng thái bài viết: Bản nháp (`draft`) $\to$ Đã xuất bản (`published`) $\to$ Lưu trữ (`archived`).
  - Hỗ trợ gắn nhiều danh mục, hệ thống Tags linh hoạt, chống trùng lặp Slug.
  - Tự động thống kê lượt xem với bộ lọc chống gian lận (Anti-spam IP qua Redis).
- 🤖 **AI Hub & Trợ Lý Tối Ưu SEO**:
  - Tích hợp **Google Gemini / OmniRoute** tự động phân tích bài viết, tính điểm SEO, sinh `meta_title`, `meta_description`, `focus_keywords`.
  - Tự động trích xuất tóm tắt bài viết.
  - Tạo vector embeddings (`pgvector`) phục vụ tìm kiếm ngữ nghĩa thông minh (Semantic Search).
- 🌐 **Pipeline Dịch Thuật Đa Ngôn Ngữ Tự Động**:
  - Tích hợp mô hình offline **Facebook NLLB-200** chạy trực tiếp trên máy chủ, bảo toàn 100% cấu trúc thẻ HTML.
  - Hỗ trợ dịch ngữ cảnh chuyên ngành giáo dục kỹ thuật (IT, Điện tử, Cơ khí, Tuyển sinh).
  - Lưu trữ theo mô hình bảng dịch chuẩn hóa phân tách `EntityTranslation`.
- 💬 **Tư Vấn Tuyển Sinh & Real-Time SSE**:
  - Tiếp nhận form đăng ký tư vấn tuyển sinh từ thí sinh ngoài Portal.
  - Đẩy sự kiện tức thời đến màn hình Admin qua **Server-Sent Events (SSE)** kèm chuông âm thanh và cập nhật Badge không cần tải lại trang.
  - Tích hợp thông báo đẩy ngoại tuyến **Web Push Notifications** (chuẩn VAPID).
- 🧭 **Menu Điều Hướng Động (Target Resolver)**:
  - Tự động phân giải liên kết động tới Danh mục, Bài viết, Bộ môn, Ngành học hoặc Custom URL mà không bị gãy liên kết khi thực thể đổi tên.
- 🏫 **Quản Lý Cơ Cấu Tổ Chức & Đào Tạo**:
  - Quản lý Khoa/Bộ môn, hồ sơ cán bộ giảng viên, chức vụ, học hàm học vị, khung chương trình đào tạo đại học và sau đại học.
  - Bộ sưu tập album hình ảnh hoạt động của từng đơn vị (`galleries`).
- 🖼️ **Lưu Trữ Tệp Tin MinIO/S3**:
  - Tải lên tệp tin bất đồng bộ lên MinIO Object Storage, tự động nén tối ưu sang định dạng `.webp` và sinh thumbnail kích thước chuẩn.

---

## ⚡ Khởi Chạy Nhanh (Quickstart)

### 1. Chuẩn bị môi trường & dịch vụ phụ trợ
Khởi chạy PostgreSQL, Redis và MinIO bằng Docker Compose:
```bash
docker compose up -d postgres redis minio
```

### 2. Thiết lập môi trường Python
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 3. Di chuyển cơ sở dữ liệu & nạp dữ liệu mẫu
```bash
alembic upgrade head
python scripts/populate_all_departments.py
python scripts/import_remaining_programs.py
python scripts/seed_footer_menu.py
```

### 4. Khởi động máy chủ phát triển
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- **API Base**: `http://localhost:8000`
- **Swagger UI Interactive**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 🧪 Kiểm Thử Tự Động (Testing)

```bash
# Chạy toàn bộ test suites
pytest

# Kiểm tra độ bao phủ mã nguồn
pytest --cov=app --cov-report=term-missing
```

---

## 👨‍💻 Tác Giả & Bản Quyền

- **Tác giả**: Nguyễn Xuân Huỳnh — [GitHub Profile](https://github.com/nguyenhuynhdt37)
- **Bản quyền**: © Trường Kỹ Thuật và Công Nghệ — Đại Học Vinh. Bảo lưu mọi quyền.
