# 📖 Tổng Hợp Danh Mục API Endpoints (API Reference Overview)

Tài liệu này cung cấp bảng chỉ mục toàn diện về toàn bộ 24 nhóm RESTful API endpoints đang vận hành trong **KTCN Backend API**, được phân tách rõ ràng giữa **Cổng thông tin công khai (Portal APIs)** và **Cổng quản trị nghiệp vụ (Admin APIs)**.

---

## 1. Tiêu Chuẩn Thiết Kế API

- **Base URL**: `http://localhost:8000` (Dev) hoặc `https://api.ktcn.vinhuni.edu.vn` (Prod).
- **Tiền tố phiên bản**: `/api/v1`
- **Định dạng dữ liệu**: `application/json` (trừ upload file dùng `multipart/form-data` và luồng sự kiện dùng `text/event-stream`).
- **Swagger UI Interactive Docs**: [http://localhost:8000/docs](http://localhost:8000/docs) (Chỉ bật trong môi trường development).

---

## 2. Bảng Tra Cứu Toàn Bộ Nhóm API Endpoints

| STT | Nhóm Tính Năng | Tiền Tố Endpoint | Quyền Hạn (Auth) | Mô Tả Chức Năng |
|---|---|---|---|---|
| **1** | **Health Check** | `/health` | Công khai | Kiểm tra kết nối cơ sở dữ liệu và Redis |
| **2** | **Xác Thực (Auth)** | `/api/v1/auth` | Công khai / Người dùng | Đăng nhập, đăng xuất, refresh token, quên mật khẩu |
| **3** | **Quản Lý User** | `/api/v1/users` | `super_admin`, `admin` | CRUD tài khoản người dùng, phân vai trò |
| **4** | **Hồ Sơ Cá Nhân** | `/api/v1/admin/profile` | Người dùng đã đăng nhập | Xem và cập nhật thông tin cá nhân, đổi mật khẩu |
| **5** | **Bài Viết (Portal)** | `/api/v1/portal/articles` | Công khai | Đọc danh sách bài viết đã xuất bản, chi tiết theo slug |
| **6** | **Bài Viết (Admin)** | `/api/v1/admin/articles` | `admin`, `editor` | Soạn thảo, lưu nháp, duyệt xuất bản, quản lý bài viết |
| **7** | **Danh Mục (Category)** | `/api/v1/portal/categories`<br/>`/api/v1/admin/categories` | Công khai / `admin` | Cây danh mục tin tức, đa ngôn ngữ, sắp xếp |
| **8** | **Thẻ Từ Khóa (Tags)** | `/api/v1/portal/tags`<br/>`/api/v1/admin/tags` | Công khai / `admin` | Quản lý tags gắn kèm bài viết |
| **9** | **Menu Điều Hướng** | `/api/v1/portal/menus`<br/>`/api/v1/admin/menus` | Công khai / `admin` | Dựng cây Menu header/footer, phân giải link động |
| **10** | **Khoa & Bộ Môn** | `/api/v1/portal/departments`<br/>`/api/v1/admin/departments` | Công khai / `admin` | Thông tin các Khoa, Bộ môn trực thuộc Trường |
| **11** | **Cán Bộ Giảng Viên** | `/api/v1/portal/staffs`<br/>`/api/v1/admin/staffs` | Công khai / `admin` | Danh sách giảng viên, lý lịch khoa học, học hàm học vị |
| **12** | **Chức Vụ (Positions)** | `/api/v1/portal/positions`<br/>`/api/v1/admin/positions` | Công khai / `admin` | Danh mục chức vụ (Trưởng khoa, Trưởng bộ môn, ...) |
| **13** | **Học Hàm (Titles)** | `/api/v1/portal/academic-titles`<br/>`/api/v1/admin/academic-titles` | Công khai / `admin` | Danh mục Giáo sư, Phó giáo sư |
| **14** | **Học Vị (Degrees)** | `/api/v1/portal/degrees`<br/>`/api/v1/admin/degrees` | Công khai / `admin` | Danh mục Tiến sĩ, Thạc sĩ, Kỹ sư |
| **15** | **CT Đào Tạo (Programs)**| `/api/v1/portal/programs`<br/>`/api/v1/admin/programs` | Công khai / `admin` | Ngành học, khung chương trình đào tạo, chuẩn đầu ra |
| **16** | **Bộ Sưu Tập (Galleries)**| `/api/v1/portal/galleries`<br/>`/api/v1/admin/galleries` | Công khai / `admin` | Album ảnh hoạt động, sự kiện của đơn vị |
| **17** | **Banner Slider** | `/api/v1/portal/banners`<br/>`/api/v1/admin/banners` | Công khai / `admin` | Banner trình chiếu trang chủ và trang con |
| **18** | **Đa Ngôn Ngữ (Languages)**| `/api/v1/portal/languages`<br/>`/api/v1/admin/languages` | Công khai / `admin` | Danh sách ngôn ngữ hỗ trợ (vi, en, lo), cờ biểu tượng |
| **19** | **Dịch Thuật (Translation)**| `/api/v1/translation` | `admin`, `editor` | Dịch văn bản, dịch cấu trúc HTML qua NLLB-200 / AI |
| **20** | **AI Hub** | `/api/v1/ai-hub` | `admin`, `editor` | Gợi ý SEO, sinh tóm tắt bài viết, tạo vector embeddings |
| **21** | **Tư Vấn (Consultation)**| `/api/v1/portal/consultations`<br/>`/api/v1/admin/consultations` | Công khai (POST)<br/>`admin` (GET/SSE) | Đăng ký tư vấn tuyển sinh và luồng sự kiện realtime SSE |
| **22** | **Thông Báo (Notification)**| `/api/v1/portal/notifications`<br/>`/api/v1/admin/notifications` | Công khai / `admin` | Đăng ký Web Push, chuông thông báo trong Admin |
| **23** | **Media & Tệp Tin** | `/api/v1/portal/media`<br/>`/api/v1/admin/media` | Công khai / `admin`, `editor` | Tải lên hình ảnh MinIO, thư viện quản lý media |
| **24** | **Thống Kê & Giám Sát** | `/api/v1/portal/statistics`<br/>`/api/v1/admin/dashboard`<br/>`/api/v1/admin/audit-logs` | Công khai (Visitor)<br/>`admin`, `super_admin` | Đếm lượt xem, Dashboard tổng hợp số liệu, Audit Log |

---

## 3. Cấu Trúc Phản Hồi Chuẩn (Standard Response Format)

Mọi API phản hồi dữ liệu thành công đều tuân thủ cấu trúc đồng nhất:

```json
{
  "success": true,
  "data": { ... },
  "message": "Thao tác thành công",
  "meta": {
    "page": 1,
    "page_size": 20,
    "total_items": 150,
    "total_pages": 8
  }
}
```

Đối với các trường hợp lỗi:
```json
{
  "success": false,
  "error_code": "RESOURCE_NOT_FOUND",
  "message": "Không tìm thấy dữ liệu yêu cầu",
  "details": null,
  "timestamp": "2026-10-11T09:00:00Z"
}
```

---

Để xem lại hướng dẫn cài đặt và khởi chạy, vui lòng truy cập: **[docs/README.md](../README.md)**.
