# 📚 Tài Liệu Kỹ Thuật Toàn Diện - KTCN Backend REST API
> **Trường Kỹ Thuật và Công Nghệ - Đại Học Vinh**  
> Máy chủ dịch vụ RESTful API bất đồng bộ (Asynchronous) phát triển trên nền tảng **FastAPI**, **PostgreSQL**, **Redis**, **MinIO/S3** và **OmniRoute AI Gateway**.

---

## 🧭 Bản Đồ Cấu Trúc Tài Liệu (Documentation Map)

Toàn bộ tài liệu kỹ thuật của hệ thống được tổ chức chuyên nghiệp theo các thư mục chức năng:

```text
docs/
├── README.md                                  # Cổng tài liệu trung tâm (Trang này)
├── getting-started/                           # Hướng dẫn Cài đặt & Vận hành
│   ├── installation-and-setup.md              # Yêu cầu hệ thống, môi trường ảo, cấu hình .env, Migrations, Seed data
│   ├── running-the-app.md                     # Chạy ứng dụng qua Docker Compose, Uvicorn, OmniRoute Gateway
│   └── testing-and-quality.md                 # Bộ kiểm thử Pytest, Linter (Ruff, Black, Mypy) & Quy chuẩn code
├── architecture/                              # Kiến trúc & Thiết kế kỹ thuật
│   ├── overview.md                            # Kiến trúc Modular Monolith, Middleware pipeline, Lifecycle
│   └── database-design.md                     # Thiết kế CSDL PostgreSQL + pgvector, Mô hình Đa ngôn ngữ (i18n)
├── features/                                  # Chi tiết Tính năng & Luồng hoạt động (Sequence Diagrams)
│   ├── auth-and-security.md                   # Xác thực JWT, Refresh Token Rotation, HTTP-only Cookie, Phân quyền RBAC, Audit Log
│   ├── i18n-and-translation.md                # Hệ thống Đa ngôn ngữ, Tự động dịch AI (NLLB-200 / OmniRoute), Redis Cache
│   ├── article-and-content.md                 # Vòng đời Bài viết (Draft/Published), Danh mục, Thẻ, SEO Assistant
│   ├── organization-and-staff.md              # Quản trị Cơ cấu Khoa/Bộ môn, Giảng viên, Học hàm, Học vị, Thư viện ảnh
│   ├── training-and-consultation.md           # Chương trình Đào tạo, Tiếp nhận Tư vấn Tuyển sinh, Luồng SSE & Web Push
│   ├── media-and-storage.md                   # Quản lý Media, MinIO / S3 Object Storage, URL Resolver, Bảo mật Upload
│   ├── ai-hub-and-seo.md                      # AI Hub Gateway, Tự động sinh SEO Meta, Quản lý Token & Chi phí
│   ├── analytics-and-monitoring.md            # Middleware VisitorCounter, Thống kê lượt xem, Health Check, Giám sát
│   ├── menu-and-navigation.md                 # Thuật toán Target Resolver, chống gãy liên kết Menu, Dựng cây phân cấp
│   └── global-search-and-gallery.md           # Tìm kiếm đa nguồn (Cmd+K) & Album ảnh Gallery
├── api-reference/                             # Danh Mục & Chi Tiết API Endpoints
│   ├── overview.md                            # Tổng quan 24 nhóm API Endpoints (Admin & Portal)
│   └── api-list.md                            # Bảng chi tiết toàn bộ các đường dẫn API và quyền hạn
└── legacy-guides/                             # Kho lưu trữ 24 tài liệu hướng dẫn và tích hợp Frontend trước đây
```

---

## 🚀 Đọc Nhanh Theo Nhu Cầu

- **Bạn là Lập trình viên mới bắt đầu?**  
  👉 Xem ngay: [Hướng Dẫn Cài Đặt](getting-started/installation-and-setup.md) ➔ [Hướng Dẫn Khởi Chạy](getting-started/running-the-app.md) ➔ [Kiểm Thử & Quy Chuẩn Code](getting-started/testing-and-quality.md).
- **Bạn cần tìm hiểu Thiết kế Kiến trúc & Cơ sở Dữ liệu?**  
  👉 Xem: [Tổng Quan Kiến Trúc](architecture/overview.md) ➔ [Thiết Kế Cơ Sở Dữ Liệu](architecture/database-design.md).
- **Bạn là Frontend Developer đang tích hợp API?**  
  👉 Xem: [Tổng Quan API Reference](api-reference/overview.md) ➔ [Bảng Chi Tiết API](api-reference/api-list.md) kết hợp [Luồng Xác Thực & Cookie](features/auth-and-security.md).
- **Bạn cần cẩm nang tổng hợp All-in-One trong một file duy nhất?**  
  👉 Mở file tài liệu tổng hợp: [`md/boost.md`](../md/boost.md).
