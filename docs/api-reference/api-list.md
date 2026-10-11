# 📋 Danh Mục RESTful API Reference

Tài liệu này tổng hợp đầy đủ các nhóm API Endpoints cốt lõi của **KTCN Backend**, phân tách rõ ràng giữa quyền Quản trị (**Admin**) và Cổng thông tin công khai (**Portal**).

Tiền tố chung: `/api/v1`  
Tài liệu tương tác trực tiếp (Swagger UI): `http://localhost:8000/docs`

---

## 1. Xác Thực & Người Dùng (Auth & Users)

| Method | Endpoint | Quyền Hạn | Mô Tả |
| :--- | :--- | :---: | :--- |
| `POST` | `/api/v1/auth/login` | Public | Đăng nhập bằng username/password, trả về cookies & JWT |
| `POST` | `/api/v1/auth/refresh-token` | Public | Tự động làm mới Access Token bằng Refresh Token |
| `POST` | `/api/v1/auth/logout` | Authenticated | Đăng xuất, hủy cookie và thu hồi token trong DB |
| `GET` | `/api/v1/auth/me` | Authenticated | Lấy thông tin tài khoản hiện tại đang đăng nhập |
| `POST` | `/api/v1/auth/change-password` | Authenticated | Đổi mật khẩu tài khoản hiện tại |
| `GET` | `/api/v1/users` | Admin | Lấy danh sách tài khoản người dùng (phân trang, tìm kiếm) |
| `POST` | `/api/v1/users` | Super Admin | Tạo mới tài khoản quản trị viên / biên tập viên |
| `PUT` | `/api/v1/users/{id}` | Super Admin | Cập nhật thông tin, gán vai trò (`role`) hoặc khóa tài khoản |
| `DELETE`| `/api/v1/users/{id}` | Super Admin | Xóa mềm hoặc vô hiệu hóa tài khoản |
| `GET` | `/api/v1/admin/profile` | Authenticated | Lấy chi tiết hồ sơ cá nhân của quản trị viên |
| `PUT` | `/api/v1/admin/profile` | Authenticated | Cập nhật thông tin hồ sơ và ảnh đại diện |

---

## 2. Quản Lý Bài Viết & Tin Tức (Articles)

| Method | Endpoint | Quyền Hạn | Mô Tả |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/v1/portal/articles` | Public | Lấy danh sách tin tức đã xuất bản (phân trang, lọc danh mục, tag, từ khóa) |
| `GET` | `/api/v1/portal/articles/by-slug/{slug}` | Public | Lấy chi tiết bài viết theo slug và ngôn ngữ (`?lang=vi`) |
| `GET` | `/api/v1/portal/articles/latest` | Public | Lấy danh sách tin tức mới nhất trang chủ |
| `GET` | `/api/v1/portal/articles/pinned` | Public | Lấy danh sách tin tức được ghim nổi bật |
| `GET` | `/api/v1/admin/articles` | Editor/Admin | Quản lý danh sách bài viết (mọi trạng thái nháp, đã đăng, hẹn giờ) |
| `POST` | `/api/v1/admin/articles` | Editor/Admin | Tạo mới bài viết và các bản dịch ngôn ngữ tương ứng |
| `GET` | `/api/v1/admin/articles/{id}` | Editor/Admin | Xem chi tiết bài viết phục vụ chỉnh sửa |
| `PUT` | `/api/v1/admin/articles/{id}` | Editor/Admin | Cập nhật thông tin, nội dung và thẻ SEO của bài viết |
| `PATCH`| `/api/v1/admin/articles/{id}/publish` | Admin | Xuất bản hoặc hủy xuất bản bài viết |
| `DELETE`| `/api/v1/admin/articles/{id}` | Editor/Admin | Xóa bài viết (chuyển vào thùng rác / soft delete) |

---

## 3. Cây Danh Mục & Thẻ (Categories & Tags)

| Method | Endpoint | Quyền Hạn | Mô Tả |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/v1/portal/categories` | Public | Lấy danh sách danh mục phẳng |
| `GET` | `/api/v1/portal/categories/tree` | Public | Lấy cấu trúc cây danh mục đa cấp lồng nhau |
| `GET` | `/api/v1/portal/categories/by-slug/{slug}` | Public | Lấy chi tiết danh mục theo slug |
| `GET` | `/api/v1/admin/categories` | Admin | Quản lý danh sách danh mục trong Admin |
| `POST` | `/api/v1/admin/categories` | Admin | Tạo mới danh mục tin tức |
| `PUT` | `/api/v1/admin/categories/{id}` | Admin | Cập nhật danh mục và thứ tự sắp xếp |
| `DELETE`| `/api/v1/admin/categories/{id}` | Admin | Xóa danh mục |
| `GET` | `/api/v1/portal/tags` | Public | Lấy danh sách các thẻ bài viết phổ biến |
| `GET` | `/api/v1/admin/tags` | Admin | Quản lý danh sách thẻ tags |
| `POST` | `/api/v1/admin/tags` | Admin | Tạo mới thẻ tag |

---

## 4. Cơ Cấu Tổ Chức & Cán Bộ (Departments, Staff, Positions)

| Method | Endpoint | Quyền Hạn | Mô Tả |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/v1/portal/departments` | Public | Danh sách các Bộ môn, Khoa, Viện trực thuộc |
| `GET` | `/api/v1/portal/departments/by-slug/{slug}`| Public | Chi tiết bộ môn và danh sách giảng viên trực thuộc |
| `GET` | `/api/v1/admin/departments` | Admin | Quản lý cơ cấu bộ môn trong Admin |
| `POST` | `/api/v1/admin/departments` | Admin | Thêm mới bộ môn / đơn vị trực thuộc |
| `GET` | `/api/v1/portal/staffs` | Public | Danh sách cán bộ giảng viên (lọc theo bộ môn, học hàm) |
| `GET` | `/api/v1/portal/staffs/{id}` | Public | Chi tiết hồ sơ khoa học của cán bộ giảng viên |
| `GET` | `/api/v1/admin/staffs` | Admin | Quản lý danh sách giảng viên trong Admin |
| `POST` | `/api/v1/admin/staffs` | Admin | Thêm mới hồ sơ giảng viên |
| `PUT` | `/api/v1/admin/staffs/{id}` | Admin | Cập nhật thông tin giảng viên |
| `DELETE`| `/api/v1/admin/staffs/{id}` | Admin | Xóa hồ sơ giảng viên |
| `GET` | `/api/v1/portal/positions` | Public | Danh sách các chức vụ |
| `GET` | `/api/v1/portal/academic-titles` | Public | Danh sách học hàm (Giáo sư, Phó Giáo sư) |
| `GET` | `/api/v1/portal/degrees` | Public | Danh sách học vị (Tiến sĩ, Thạc sĩ...) |

---

## 5. Chương Trình Đào Tạo (Academic Programs)

| Method | Endpoint | Quyền Hạn | Mô Tả |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/v1/portal/programs` | Public | Danh sách các ngành đào tạo (Đại học & Sau đại học) |
| `GET` | `/api/v1/portal/programs/by-slug/{slug}` | Public | Chi tiết chương trình đào tạo, chuẩn đầu ra & đề cương |
| `GET` | `/api/v1/admin/programs` | Admin | Quản lý danh sách chương trình đào tạo trong Admin |
| `POST` | `/api/v1/admin/programs` | Admin | Tạo mới chương trình đào tạo |
| `PUT` | `/api/v1/admin/programs/{id}` | Admin | Cập nhật chương trình đào tạo |
| `DELETE`| `/api/v1/admin/programs/{id}` | Admin | Xóa chương trình đào tạo |

---

## 6. Menu, Banner & Media Storage

| Method | Endpoint | Quyền Hạn | Mô Tả |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/v1/portal/menus/by-code/{code}` | Public | Lấy cây menu điều hướng theo mã (MAIN_HEADER, FOOTER) |
| `GET` | `/api/v1/admin/menus` | Admin | Danh sách menu điều hướng trong hệ thống |
| `POST` | `/api/v1/admin/menus/{menu_id}/items` | Admin | Thêm mục liên kết mới vào cây menu |
| `PUT` | `/api/v1/admin/menus/items/{item_id}` | Admin | Chỉnh sửa mục menu và thứ tự hiển thị |
| `DELETE`| `/api/v1/admin/menus/items/{item_id}` | Admin | Xóa mục menu |
| `GET` | `/api/v1/portal/banners` | Public | Lấy danh sách banner slider đang hoạt động trang chủ |
| `GET` | `/api/v1/admin/banners` | Admin | Quản lý danh sách banners trong Admin |
| `POST` | `/api/v1/admin/banners` | Admin | Tạo mới banner |
| `POST` | `/api/v1/admin/media/upload` | Authenticated | Tải lên hình ảnh/tập tin tài liệu lên MinIO S3 |
| `GET` | `/api/v1/admin/media` | Authenticated | Danh sách thư viện media đã tải lên |

---

## 7. AI Hub & Dịch Thuật Đa Ngôn Ngữ

| Method | Endpoint | Quyền Hạn | Mô Tả |
| :--- | :--- | :---: | :--- |
| `POST` | `/api/v1/ai-hub/generate-seo` | Authenticated | Tự động sinh SEO meta title, description và từ khóa bằng AI |
| `GET` | `/api/v1/ai-hub/logs` | Admin | Xem nhật ký các yêu cầu gọi AI (Token, thời gian, chi phí) |
| `POST` | `/api/v1/translation/translate` | Authenticated | Dịch văn bản / HTML từ Tiếng Việt sang Tiếng Anh bảo toàn tags |
| `POST` | `/api/v1/translation/batch` | Authenticated | Dịch hàng loạt nhiều đoạn văn bản đồng thời |

---

## 8. Thông Báo Đẩy, Tư Vấn & Thống Kê

| Method | Endpoint | Quyền Hạn | Mô Tả |
| :--- | :--- | :---: | :--- |
| `POST` | `/api/v1/portal/notifications/subscribe` | Public | Đăng ký nhận thông báo đẩy Web Push từ trình duyệt |
| `POST` | `/api/v1/admin/notifications/broadcast` | Admin | Gửi thông báo đẩy hàng loạt tới tất cả người đăng ký |
| `POST` | `/api/v1/portal/consultations` | Public | Thí sinh gửi đơn đăng ký tư vấn tuyển sinh |
| `GET` | `/api/v1/admin/consultations` | Admin | Quản lý danh sách đơn đăng ký tư vấn tuyển sinh |
| `PATCH`| `/api/v1/admin/consultations/{id}/status` | Admin | Cập nhật trạng thái xử lý đơn tư vấn (PENDING, CONTACTED) |
| `GET` | `/api/v1/statistics` | Public | Lấy số liệu thống kê tổng truy cập, hôm nay và online realtime |
| `GET` | `/api/v1/dashboard/stats` | Admin | Tổng hợp dữ liệu thống kê bảng điều khiển trung tâm Admin |
| `GET` | `/api/v1/admin/audit-logs` | Super Admin | Lấy danh sách nhật ký kiểm toán thao tác hệ thống |
| `GET` | `/health` | Public | Giám sát trạng thái hoạt động của máy chủ (Database, Redis) |

---

## 9. Tìm Kiếm Toàn Cục & Thư Viện Ảnh (Global Search & Gallery)

| Method | Endpoint | Quyền Hạn | Mô Tả |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/v1/admin/search` | Authenticated | Tìm kiếm nhanh toàn cục đa nguồn (bài viết, user, danh mục, tag, cán bộ) qua `asyncio.gather` |
| `GET` | `/api/v1/admin/gallery` | Authenticated | Danh sách album ảnh trong Admin (phân trang, lọc theo department) |
| `POST` | `/api/v1/admin/gallery` | Authenticated | Tạo mới album ảnh kèm danh sách items |
| `GET` | `/api/v1/admin/gallery/{id}` | Authenticated | Xem chi tiết album ảnh |
| `PUT` | `/api/v1/admin/gallery/{id}` | Authenticated | Cập nhật thông tin album và sắp xếp ảnh |
| `DELETE`| `/api/v1/admin/gallery/{id}` | Authenticated | Xóa album ảnh |
| `GET` | `/api/v1/portal/gallery` | Public | Danh sách album ảnh hiển thị trên Portal |
| `GET` | `/api/v1/portal/gallery/{id}` | Public | Xem chi tiết album và các ảnh thành viên trên Portal |
