# ⚙️ KTCN Backend REST API - Khoa Tài Chính Ngân Hàng

![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71100?style=for-the-badge&logo=sqlalchemy&logoColor=white)

Hệ thống RESTful API chính thức xử lý toàn bộ nghiệp vụ Backend cho Cổng thông tin & Admin Portal **Khoa Tài Chính Ngân Hàng**. Xây dựng bằng **Python FastAPI** bất đồng bộ (Asyncio) và **PostgreSQL**.

---

## ✨ Tính Năng Nổi Bật

- 🚀 **Hiệu Năng Cao:** Kiến trúc Async / Await với FastAPI và Asyncpg / SQLAlchemy 2.0.
- 🔐 **Xác Thực Bảo Mật:** JWT Authentication, OAuth2 password flow, mã hóa mật khẩu Passlib/Bcrypt.
- 📰 **REST APIs Nghiệp Vụ:** CRUD Bài viết, Tin tức, Danh mục, Banner slider, SEO Meta tags, Cán bộ Giảng viên.
- 📖 **Swagger / OpenAPI:** Tự động tạo tài liệu API tương tác tại `/docs`.

---

## 🚀 Hướng Dẫn Khởi Chạy Backend

```bash
git clone https://github.com/nguyenhuynhdt37/ktcn-backend-api.git
cd ktcn-backend-api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Truy cập tài liệu API: `http://localhost:8000/docs`

---

## 👨‍💻 Tác Giả

**Nguyễn Xuân Huỳnh** — [GitHub Profile](https://github.com/nguyenhuynhdt37)
