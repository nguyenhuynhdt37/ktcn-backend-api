# ⚙️ KTCN Backend REST API - Trường Kỹ Thuật và Công Nghệ - Đại Học Vinh

![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Python 3.11](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)

Máy chủ Backend RESTful API cốt lõi phục vụ Cổng thông tin & Admin Portal **Trường Kỹ Thuật và Công Nghệ - Đại Học Vinh**. Phát triển bằng **Python FastAPI** bất đồng bộ (AsyncIO) và **PostgreSQL**.

---

## ✨ Tính Năng Nổi Bật

- 🔑 **Auth & Phân Quyền:** JWT Token, mã hóa password Bcrypt, phân quyền RBAC.
- 📰 **Quản Lý Bài Viết & Danh Mục:** CRUD bài viết, tin tức, banner slider, SEO meta tags.
- 👥 **Quản Lý Cán Bộ & Bộ Môn:** Danh sách giảng viên, bộ môn trực thuộc Trường.

```bash
git clone https://github.com/nguyenhuynhdt37/ktcn-backend-api.git
cd ktcn-backend-api
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

---

## 👨‍💻 Tác Giả

**Nguyễn Xuân Huỳnh** — [GitHub Profile](https://github.com/nguyenhuynhdt37)
