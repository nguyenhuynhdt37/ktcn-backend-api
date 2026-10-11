# 🧭 Phân Giải Menu Điều Hướng Động (Menu Target Resolution Flow)

Tài liệu này mô tả chi tiết thuật toán phân giải đích đến (Target Resolver), cơ chế quản lý liên kết động chống gãy link (Broken Link Prevention) và quy trình dựng cấu trúc cây Menu đa cấp trong **KTCN Backend API**.

---

## 1. Vấn Đề Thực Tế & Kiến Trúc Target Resolver

Trong các hệ thống CMS truyền thống, menu thường lưu trữ URL tĩnh (Hardcoded URL, ví dụ: `/tin-tuc/thong-bao-tuyen-sinh-2025`). Khi bài viết hoặc danh mục thay đổi tiêu đề hoặc đổi slug, toàn bộ liên kết trên menu sẽ bị gãy (lỗi 404).

Để giải quyết triệt để vấn đề này, **KTCN Backend API** thiết kế cơ chế **Target Resolver** tại `app/modules/menu/target_resolver.py`:

```mermaid
graph TD
    MenuDB["Bản Ghi MenuItem (target_type, target_id, custom_url)"] --> Resolver{"MenuTargetResolver"}
    
    Resolver -- target_type = 'category' --> ResolveCat["Truy vấn bảng Category<br/>Lấy slug mới nhất -> '/tin-tuc/{slug}'"]
    Resolver -- target_type = 'article' --> ResolveArt["Truy vấn bảng Article<br/>Lấy slug mới nhất -> '/bai-viet/{slug}'"]
    Resolver -- target_type = 'department' --> ResolveDept["Truy vấn bảng Department<br/>Lấy slug mới nhất -> '/gioi-thieu/{slug}'"]
    Resolver -- target_type = 'program' --> ResolveProg["Truy vấn bảng Program<br/>Lấy slug mới nhất -> '/dao-tao/{slug}'"]
    Resolver -- target_type = 'custom' --> ResolveCustom["Sử dụng custom_url nguyên bản"]
    Resolver -- target_type = 'none' --> ResolveNone["Đặt url = null (Menu cha chỉ kích hoạt Dropdown)"]

    ResolveCat --> ResultURL["URL Đích Chính Xác & Động"]
    ResolveArt --> ResultURL
    ResolveDept --> ResultURL
    ResolveProg --> ResultURL
    ResolveCustom --> ResultURL
    ResolveNone --> ResultURL
```

---

## 2. Các Loại Đích Đến Hỗ Trợ (Supported Target Types)

| Kiểu đích (`target_type`) | Tham số cần có | Cách phân giải URL tự động | Xử lý khi thực thể bị xóa |
|---|---|---|---|
| `category` | `target_id` (UUID danh mục) | Ghép nối prefix danh mục: `/chuyen-muc/{category.slug}` | Đánh dấu `is_broken = true`, url trở về rỗng |
| `article` | `target_id` (UUID bài viết) | Ghép nối prefix bài viết: `/bai-viet/{article.slug}` | Đánh dấu `is_broken = true`, thông báo cho Admin |
| `department` | `target_id` (UUID khoa/bộ môn) | Ghép nối prefix đơn vị: `/don-vi/{department.slug}` | Đánh dấu `is_broken = true` |
| `program` | `target_id` (UUID ngành học) | Ghép nối prefix chương trình: `/dao-tao/{program.slug}` | Đánh dấu `is_broken = true` |
| `custom` | `custom_url` (chuỗi URL) | Giữ nguyên URL người dùng nhập (hỗ trợ cả link ngoài) | Luôn hợp lệ |
| `none` | Không có | `url = null` | Thường dùng cho các nút menu cha cấp 1 |

---

## 3. Thuật Toán Dựng Cây Menu Đa Cấp (Hierarchical Tree Builder)

Để giảm thiểu số lượng truy vấn xuống CSDL, backend truy vấn toàn bộ danh sách phẳng các item của một Menu (`position = 'header'` hoặc `'footer'`) trong **duy nhất một truy vấn**, sau đó dựng cây phân cấp trong bộ nhớ RAM:

```mermaid
sequenceDiagram
    autonumber
    actor Client as Client Portal
    participant API as Menu Portal Router (/api/v1/portal/menus/{location})
    participant Service as MenuService
    participant Resolver as TargetResolver
    participant DB as PostgreSQL

    Client->>API: GET /api/v1/portal/menus/header?language=vi
    API->>Service: get_menu_by_location("header", "vi")
    Service->>DB: Truy vấn 1 lần tất cả MenuItems thuộc header có is_active = true
    DB-->>Service: Trả về danh sách phẳng (Flat list)
    
    Service->>Resolver: Batch resolve toàn bộ target_ids trong danh sách
    Resolver->>DB: Batch query Categories & Articles theo IDs
    Resolver-->>Service: Gắn resolved_url cho từng MenuItem
    
    Service->>Service: Dựng cây phân cấp (Recursive Build Tree) theo parent_id và sắp xếp theo sort_order
    Service-->>API: Trả về JSON cấu trúc cây hoàn chỉnh (Root -> Children -> Sub-children)
    API-->>Client: Dữ liệu Render Navbar Menu cực nhanh (< 15ms)
```

---

## 4. Xử Lý Các Mục Menu Bị Mồ Côi Khi Thực Thể Đích Bị Xóa

Hệ thống có bộ quét tự động phát hiện mục menu bị gãy link:
- Khi một bài viết hoặc danh mục bị xóa mềm (`is_deleted = True`), dịch vụ `MenuTargetResolver` tự động phát hiện liên kết đích không còn tồn tại.
- Thuộc tính `target_status` sẽ trả về `DELETED_OR_NOT_FOUND`.
- Phía Admin Portal sẽ hiển thị biểu tượng cảnh báo màu vàng tam giác kèm nhãn *"Thực thể liên kết đã bị xóa"* để quản trị viên kịp thời trỏ lại liên kết mới.

---

Tiếp tục tìm hiểu về quản lý cơ cấu tổ chức tại: **[Quản Lý Cơ Cấu Tổ Chức & Đào Tạo (organization-and-staff.md)](./organization-and-staff.md)**.
