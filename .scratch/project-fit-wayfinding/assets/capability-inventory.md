# Capability hiện có: caller trong repository và giới hạn kết luận

Ngày điều tra: 2026-09-06. Chỉ đọc source/script/schema/test; không chạy API, SQL, seed, cleanup hoặc thay implementation.

## Phạm vi bằng chứng

Đã tìm kiếm backend/app, backend/scripts, backend/tests, frontend/src, scripts và schema SQL. Không có caller trong phạm vi này không chứng minh không có người dùng ngoài repository. Dữ liệu đang lưu trong SQL chưa được đọc.

## Kết quả

| Capability | Bằng chứng hiện tại | Kết luận theo mục tiêu đã chốt |
|---|---|---|
| user_sessions | Auth service tạo/revoke session; dependencies kiểm token; endpoint quản lý session có backend. [Auth dependency](../../../backend/app/api/dependencies.py:64), [repository](../../../backend/app/data_manager/new_tables_repo.py:129). | ALIGNED: phục vụ đăng nhập/logout thực sự. Không được xóa chỉ vì wrapper list/revoke-all chưa có UI caller. |
| phrase_overrides | Pending service đọc PhraseOverrideRepository để đưa vào live data; routes admin CRUD. [Pending service](../../../backend/app/data_manager/pending_service.py:15), [routes](../../../backend/app/api/routes.py:774). | ALIGNED về runtime: dữ liệu sửa cụm từ có tác dụng. UI wrapper chưa được gọi không khiến cả capability là thừa. |
| abbreviation_usage_stats | Live route inject repository, normalizer ghi bulk; backend có truy vấn thống kê. [Route](../../../backend/app/api/routes.py:306), [ghi usage](../../../backend/app/normalizer/live_normalizer.py:375). | PARTIALLY ALIGNED: có producer thực. Giá trị dashboard/analytics chưa được chứng minh; chưa cần mở rộng UI. Không coi là số đo quota AI. |
| AIUsageStats | Client ghi số call/token/error; endpoint admin snapshot. [Client](../../../backend/app/ai/client.py:55). | PARTIALLY ALIGNED: telemetry có thật, nhưng không phải quota ledger hoặc ngân sách đa worker. |
| user_preferences | Repository/API có CRUD; frontend wrappers không thấy caller. Workspace draft/variant hiện lưu sessionStorage. [Wrappers](../../../frontend/src/lib/api.ts:302), [workspace state](../../../frontend/src/lib/workspaceSession.ts:1). | UNCERTAIN về nhu cầu dùng ngoài. Chưa có đóng góp được chứng minh cho workspace hiện tại; không suy cần làm thêm UI. |
| annotation_data | Có CREATE TABLE, index và test schema; không thấy reader/writer ứng dụng hay script tạo corpus dùng bảng này. Scripts build/eval dùng file CSV/JSON. [Schema](../../../backend/database/init_schema.sql:230), [build assets](../../../backend/scripts/build_diacritic_assets.py:23). | UNCERTAIN về sử dụng bên ngoài. Bảng dự phòng không phải bằng chứng đã có workflow gán nhãn/học dữ liệu. |
| diacritic_cache (SQL) | Có table/index/cleanup và test schema, không thấy reader/writer ứng dụng. Restorer dùng AsyncTTLCache trong bộ nhớ. [Schema](../../../backend/database/init_schema.sql:215), [restorer cache](../../../backend/app/normalizer/diacritic_restorer.py:399). | UNCERTAIN về sử dụng bên ngoài. Phải phân biệt bảng SQL chưa nối và cache đang hoạt động. |
| /api/normalize, pipeline CLI | Route gọi pipeline; CLI gọi pipeline và ghi history. [Route](../../../backend/app/api/routes.py:262), [CLI](../../../backend/app/main.py:263). | Pipeline không phải code chết. CLI là công cụ nội bộ; /api/normalize chưa có frontend caller tìm thấy. Có đáng giữ public endpoint riêng hay không phụ thuộc caller ngoài và phạm vi đã chốt. |
| /api/normalize/live | useLiveNormalize được WorkspacePage gọi. [Workspace](../../../frontend/src/pages/WorkspacePage.tsx:64). | ALIGNED về kết nối vào sản phẩm; lỗi đã biết được theo dõi trong review, không điều tra/sửa lại ở đây. |
| /restore-diacritic và /disambiguate | Backend có route. Frontend restore wrapper không thấy caller; disambiguate chỉ được gọi bởi useAIDisambiguation, hook không được import bởi workspace. [Hook](../../../frontend/src/hooks/useAIDisambiguation.ts:21), [routes](../../../backend/app/api/routes.py:336). | PARTIALLY ALIGNED: có logic thật nhưng chưa là bước tự động của workspace. Cần thống nhất trách nhiệm, không kết luận mọi logic AI này đều bỏ. |
| user overrides | Workspace và dictionary page gọi addUserMeaning, backend lưu/merge vào live data. [Workspace](../../../frontend/src/pages/WorkspacePage.tsx:245), [dictionary](../../../frontend/src/pages/AdminDictionaryPage.tsx:100). | MISALIGNED với user chỉ dùng/xem đã chốt. Đây là capability đang dùng nhưng sai mục tiêu, không phải code chết. |
| script build/eval dữ liệu | Có công cụ build JSON từ CSV và đánh giá khôi phục dấu. [Build](../../../backend/scripts/build_diacritic_assets.py:29), [eval](../../../backend/scripts/eval_diacritic.py:1). | ALIGNED về vai trò công cụ nội bộ. Kết quả benchmark hiện hành/đủ chất lượng là câu hỏi khác. |
| sp_cleanup_expired_data | Có stored procedure trong schema, chưa tìm thấy caller lập lịch trong script ứng dụng đã quét. [Schema](../../../backend/database/init_schema.sql:827). | UNCERTAIN về lịch chạy thật; không được suy procedure đang chạy hoặc chưa từng chạy từ repository. |

## Hệ quả đối với hành vi mong muốn

- Không gộp “chưa có UI” với “không có chức năng”: session, phrase overrides, usage producers đang phục vụ backend.
- Không tuyên bố có pipeline học/annotation hay cache SQL bền vững chỉ từ các bảng được khai báo.
- Luồng user overrides đang hoạt động nhưng mâu thuẫn quyền đã chốt; quyết định sản phẩm này đã rõ, chưa thực hiện sửa.
- Frontend gọi một luồng chuẩn hóa chính; khả năng học nghĩa mới ở endpoint khác chưa chứng minh đã tham gia luồng chính.
- Chưa đủ căn cứ xóa endpoint/bảng chỉ vì không có caller trong repository. Cần chủ project xác nhận nơi triển khai và công cụ ngoài; ticket riêng giữ phần phụ thuộc này.

## Chưa đo

Không đo row count, access logs, scheduler, actual usage, quota hoặc latency. Không truy cập dữ liệu riêng để làm thống kê. Những bằng chứng này thuộc điều tra môi trường.

