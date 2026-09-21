# Những capability chưa nối vào workspace có người sử dụng thực tế không?

Parent: ../map.md
Labels: wayfinder:task
Type: task
Wayfinding Status: resolved
Assignee: Codex — inventory capability
Blocked by: 

## Question

Kiểm kê caller, script, test, schema và công cụ ngoài repository đối với annotation_data, diacritic_cache, preferences, sessions, usage wrappers, các endpoint normalize/restore/disambiguate và user overrides. Phân biệt: đang phục vụ sản phẩm; công cụ nội bộ hữu ích; code không có caller trong repository; người dùng ngoài repository chưa rõ.

Chỉ đọc. Không xem không có caller trong repository là bằng chứng chắc chắn không ai dùng. Kết quả phục vụ quyết định phạm vi, không tự xóa code. Phần xác nhận deployment/caller ngoài đã tách sang [Xác nhận những nơi đang sử dụng project](09-external-consumers.md), nên resolution của ticket này chỉ áp dụng cho kiểm kê trong repository.

## Comments

Nguồn: các điểm UNCERTAIN và câu hỏi còn mở trong review mức độ phù hợp của project, cuộc trao đổi ngày 2026-09-06.

### Bằng chứng ban đầu từ review trước — chưa phải kết luận sử dụng thực tế

- `frontend/src/pages/WorkspacePage.tsx` gọi `useLiveNormalize`; chưa tìm thấy caller của `useAIDisambiguation` ngoài chính hook đó. Backend `/api/normalize/disambiguate` có logic ghi nhận nghĩa AI.
- `annotation_data` và `diacritic_cache` có trong schema; tìm kiếm runtime `backend/app` trước đó chưa thấy truy cập hai bảng này. Có caller ngoài repository hay không còn cần xác minh.
- Sessions phục vụ kiểm tra/revoke token nên không được gom chung thành code thừa chỉ vì chưa có màn hình quản lý sessions.
- Đã hỏi chủ project có deployment hoặc script/công cụ ngoài bản trên máy này hay không. Câu hỏi là thu thập sự thật, không xin phép triển khai.

## Answer

Đã kiểm kê source, scripts, schema và tests: [bằng chứng caller và phân loại](../assets/capability-inventory.md). Sessions, phrase overrides, usage producers và CLI có đường sử dụng thật. Preferences API/wrappers, hai bảng annotation/cache SQL và một số endpoint chưa thấy consumer sản phẩm trong repository; không kết luận có thể xóa. User overrides đang được dùng nhưng trái quyền đã chốt. Đường học nghĩa AI qua disambiguate chưa được nối vào workspace.

Ticket hoàn tất kiểm kê nội bộ, không xác nhận deployment hoặc dữ liệu SQL. Câu hỏi caller ngoài là blocker còn mở của việc chốt phạm vi, được giữ riêng để không biến thiếu bằng chứng thành quyết định loại bỏ.
