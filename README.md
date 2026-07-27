# ⚙️ KTCN Backend REST API - Máy Chủ Dịch Vụ RESTful API Khoa Tài Chính Ngân Hàng

[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python 3.11](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![SQLAlchemy 2.0](https://img.shields.io/badge/SQLAlchemy-2.0-D71100?style=for-the-badge&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![Swagger Docs](https://img.shields.io/badge/OpenAPI-Swagger-85EA2D?style=for-the-badge&logo=swagger&logoColor=black)](http://localhost:8000/docs)

Máy chủ Backend RESTful API cốt lõi phục vụ hệ sinh thái **Khoa Tài Chính Ngân Hàng** (bao gồm Client Web Portal và Admin Dashboard). Hệ thống được phát triển bằng **Python FastAPI** bất đồng bộ (AsyncIO), cơ sở dữ liệu **PostgreSQL** và **SQLAlchemy 2.0 ORM**.

---

## 📑 Mục Lục
- [Kiến Trúc Hệ Thống](#-kiến-trúc-hệ-thống)
- [Tính Năng Nổi Bật](#-tính-năng-nổi-bật)
- [Mô Hình Cơ Sở Dữ Liệu](#-mô-hình-cơ-sở-dữ-liệu)
- [Cấu Trúc Thư Mục](#-cấu-trúc-thư-mục)
- [Danh Sách RESTful API Endpoints](#-danh-sách-restful-api-endpoints)
- [Hướng Dẫn Khởi Chạy](#-hướng-dẫn-khởi-chạy)

---

## 🏗️ Kiến Trúc Hệ Thống

Hệ thống tuân thủ mô hình **Clean Architecture / Layered Architecture**:
- **Router Layer (APIs):** Tiếp nhận HTTP requests, xử lý validation đầu vào bằng Pydantic schemas.
- **Service Layer (Business Logic):** Xử lý nghiệp vụ, phân quyền, mã hóa mật khẩu, tương tác cơ sở dữ liệu.
- **Data Layer (Models & Migrations):** Định nghĩa sơ đồ bảng trong DB qua SQLAlchemy ORM và quản lý lịch sử thay đổi DB bằng Alembic.

---

## ✨ Tính Năng Nổi Bật

### 🔑 1. Xác Thực & Phân Quyền (Auth & Security)
- Mã hóa mật khẩu bảo mật chuẩn `Bcrypt` / `Passlib`.
- Cấp phát và xác thực Token chuẩn `JWT (JSON Web Token)` bất đồng bộ.
- Phân quyền theo cấp bậc Role-Based Access Control (RBAC): `SUPER_ADMIN`, `EDITOR`, `STAFF`.

### 📰 2. Quản Lý Tin Tức & Danh Mục
- API CRUD Bài viết với định dạng Rich Text / HTML.
- Tự động tạo `slug` chuẩn SEO cho bài viết và danh mục.
- Đếm số lượt đọc (view count), bài viết ghim (featured articles).

### 👥 3. Quản Lý Cán Bộ & Bộ Môn (Staff & Faculties)
- Quản lý danh sách giảng viên, học hàm, học vị, chức vụ và email liên hệ.
- Phân loại giảng viên theo từng Bộ môn trực thuộc Khoa.

### 🖼️ 4. Banner Slider & Media Upload
- Upload hình ảnh/file biểu mẫu trực tiếp lên máy chủ.
- Xếp thứ tự hiển thị banner trang chủ.

---

## 🗄️ Mô Hình Cơ Sở Dữ Liệu

Các bảng chính trong hệ thống PostgreSQL:
- **`users`**: Quản lý tài khoản admin/biên tập viên (`id`, `username`, `hashed_password`, `role`, `is_active`).
- **`categories`**: Danh mục tin tức (`id`, `name`, `slug`, `description`).
- **`articles`**: Bài viết & Tin tức (`id`, `title`, `slug`, `content`, `thumbnail`, `category_id`, `author_id`, `views_count`, `is_published`).
- **`faculties`**: Bộ môn trực thuộc (`id`, `name`, `code`, `description`).
- **`staff`**: Danh sách Cán bộ Giảng viên (`id`, `full_name`, `academic_degree`, `position`, `email`, `faculty_id`).
- **`banners`**: Banner slider (`id`, `title`, `image_url`, `link_url`, `display_order`, `is_active`).

---

## 📁 Cấu Trúc Thư Mục

```
ktcn-backend-api/
├── app/
│   ├── api/                    # REST API Endpoints Router
│   │   ├── v1/
│   │   │   ├── endpoints/      # Controllers (auth.py, articles.py, staff.py, banners.py)
│   │   │   └── api.py          # Master Router Setup
│   ├── core/                   # Cấu hình Core & Security
│   │   ├── config.py           # Pydantic BaseSettings
│   │   ├── security.py         # Mã hóa password & JWT Token handler
│   │   └── database.py         # Async SQLAlchemy engine & SessionLocal
│   ├── models/                 # SQLAlchemy ORM Models
│   ├── schemas/                # Pydantic Validation Schemas
│   ├── services/               # Logic nghiệp vụ xử lý DB
│   └── main.py                 # File khởi chạy chính của Uvicorn FastAPI
├── alembic/                    # Lịch sử Database Migrations
├── requirements.txt            # Danh sách thư viện Python
└── README.md
```

---

## 📋 Danh Sách RESTful API Endpoints chính

| HTTP Method | Route | Chức Năng | Auth Required |
| :--- | :--- | :--- | :---: |
| `POST` | `/api/v1/auth/login` | Đăng nhập lấy JWT Token | ❌ |
| `GET` | `/api/v1/articles` | Lấy danh sách bài viết (Có phân trang, search, category filter) | ❌ |
| `GET` | `/api/v1/articles/{slug}` | Lấy chi tiết bài viết theo slug | ❌ |
| `POST` | `/api/v1/articles` | Tạo bài viết mới | ✅ (Admin/Editor) |
| `PUT` | `/api/v1/articles/{id}` | Cập nhật bài viết | ✅ (Admin/Editor) |
| `DELETE` | `/api/v1/articles/{id}` | Xóa bài viết | ✅ (Admin) |
| `GET` | `/api/v1/staff` | Lấy danh sách giảng viên theo bộ môn | ❌ |
| `POST` | `/api/v1/upload` | Upload hình ảnh/tài liệu lên server | ✅ |

---

## 🚀 Hướng Dẫn Khởi Chạy

### 1. Tạo và kích hoạt môi trường ảo Python:
```bash
git clone https://github.com/nguyenhuynhdt37/ktcn-backend-api.git
cd ktcn-backend-api

python3 -m venv venv
source venv/bin/activate
```

### 2. Cài đặt các thư viện:
```bash
pip install -r requirements.txt
```

### 3. Cấu hình file môi trường `.env`:
```env
PROJECT_NAME="KTCN Backend API"
SECRET_KEY="your_super_secret_jwt_key_here"
POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=yourpassword
POSTGRES_DB=ktcn_db
POSTGRES_PORT=5432
```

### 4. Chạy Migrations tạo bảng DB:
```bash
alembic upgrade head
```

### 5. Khởi chạy Uvicorn Server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Mở tài liệu API Swagger UI tại: `http://localhost:8000/docs`

---

## 👨‍💻 Tác Giả

**Nguyễn Xuân Huỳnh** — [GitHub Profile](https://github.com/nguyenhuynhdt37)
