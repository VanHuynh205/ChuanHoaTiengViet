# 13: Nối NVIDIA Nemotron vào một lượt chuẩn hóa có kiểm soát

Status: needs-triage
Implementation: complete for authorized internal scope; real Nemotron smoke passed
Blocker: none for internal integration; production remains outside scope
Evidence: ../nemotron-13-evidence.md
Publication: draft — chờ duyệt breakdown
Priority: P1
Type: implementation

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): A-01–02, A-05, A-10–11.

## Vấn đề cần giải quyết

NVIDIA client hiện theo GLM; K3 JSON/thinking/response lifecycle và tài khoản chưa được kiểm chứng.

## Vì sao quan trọng

Chỉ đổi model name không tạo integration đáng tin cậy.

## Kết quả mong muốn / What to build

Một lượt chuẩn hóa ngắn được NVIDIA Nemotron xử lý trong phạm vi kiểm thử nội bộ đã cho phép, có fallback và trạng thái đúng. Chủ project thay mục tiêu Kimi bằng Nemotron ngày 2026-09-07.

## Ràng buộc

Bị chặn bởi điều tra, không tự giải quyết quyền hosted trial hoặc quota. Không triển khai production trong ticket.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [x] Khi bắt đầu công việc tích hợp, nhắc chủ project cung cấp Python gọi API; không in/lưu key vào artifact.
- [x] Request dùng hợp đồng đã xác minh thay vì mặc định tham số GLM; xử lý pending/truncation/JSON lỗi theo bằng chứng thực tế.
- [x] Backend trả kết quả và lỗi đúng; giao diện kiểm chứng bằng component/hook tests; key nằm phía server; không tự fallback có phí. Không tuyên bố đã chạy browser E2E với NVIDIA.
- [x] Có contract test fake provider; smoke thật trong phạm vi nội bộ/dữ liệu tổng hợp, ghi rõ kết quả và giới hạn.

## Blocked by

- [11 — Cho phép dataset-only và thông báo trước khi gửi AI](11-dataset-only-choice.md)
- [12 — Áp dụng ngân sách AI chung và giới hạn theo user](12-shared-ai-budget.md)
- [Chốt phạm vi hosted trial](../../project-fit-wayfinding/issues/08-trial-boundary.md)
- [Xác minh hợp đồng Kimi trên tài khoản thực tế](wayfinding-10-kimi-account-contract.md) — bản nháp, dự kiến wayfinding 10.

## Khu vực có thể ảnh hưởng

NVIDIA adapter; settings validation; AI response parsing; live service; contract tests.

## Comments

### Cập nhật mục tiêu — 2026-09-07 (sau tích hợp Nemotron)

Bổ sung smoke prompt chủ động giải nghĩa: 6.871 giây, verified/provider_checked. AI_DISABLE_NETWORK local hiện đã chuyển sang 0 theo phiên chỉnh teencode; ghi chú bằng 1 trước đó là lịch sử. Không mở rộng nghiệm thu production.

Áp dụng [hồ sơ thay đổi và checklist review tổng thể](../teencode-policy-change.md). Ghi chú trái chính sách mới bên dưới là lịch sử; không tự đánh dấu các tiêu chí chưa kiểm chứng.


### Hoàn tất phạm vi nội bộ bằng Nemotron — 2026-09-07

Theo yêu cầu đổi model của chủ project, đã sửa HTTP 400 do gửi `extra_body` trên wire, giữ system prompt và hạ reasoning budget xuống 256. Smoke mặc định đọc .env: 13.119 giây, `verified/provider_checked`, một đoạn được kiểm tra, kết quả `Hôm nay đăng ký học phần`. Backend 455 passed, 1 skipped, 39 subtests; Ruff/Mypy pass. Xem [bằng chứng mới](../nemotron-13-evidence.md). Blocker Kimi bên dưới là lịch sử, không còn chặn model mới; không kết luận lỗi Kimi đã được sửa. AI mạng của ứng dụng chung vẫn tắt; nghiệm thu chỉ trong scope nội bộ.

### Key mới và mẫu text-only — 2026-09-07

Chủ project cập nhật key và báo Build UI hiện trả lời nhanh. Đã xác nhận process mới đọc đúng root .env, key không bị file khác ghi đè hoặc dư Bearer/whitespace. Mẫu requests độc lập đúng content chuỗi/max_tokens=16384/temperature=1/low vẫn chờ quá 60s. Đã đồng bộ content chuỗi và sửa TypeError khi finish_reason sai kiểu. 453 tests pass, Ruff/Mypy pass. [Chi tiết lần kiểm tra mới](../kimi-new-key-check.md); không suy lỗi Build UI cũ vẫn còn.

### Điều tra timeout và hạ reasoning — 2026-09-07

Đã hạ mặc định xuống low theo yêu cầu mới. Smoke không còn tự ghi đè .env bằng max. Đã chứng minh valid POST chờ header với cả requests/httpx/HTTP2 và deadline 180s; header polling cho lỗi NVIDIA 504, NVCF-STATUS=errored, có request ID. Sửa local bug tự retry 504 gây gửi lặp; test red→green. Smoke API ở low vẫn timeout 60s, chưa đạt nghiệm thu. [Báo cáo nguyên nhân và request ID](../kimi-timeout-diagnosis.md).

### Tích hợp nội bộ — 2026-09-07

Validation cuối: backend 451 passed, 1 skipped, 39 subtests; Ruff và Mypy pass. Các tiêu chí cần bằng chứng response/model thật vẫn chưa đánh dấu đạt vì cả hai smoke đều timeout.

Chủ project đã chốt scope nội bộ bằng dữ liệu tổng hợp và đã cung cấp key qua .env. Đã thêm Kimi SSE adapter, wiring factory, reasoning allowance trong trần ngân sách, fake contract tests; không bật mạng AI cho ứng dụng chung. Hai POST thật (max và low) đều timeout 60 giây, dataset fallback hoạt động. HEAD trả 405 xác nhận kết nối HTTP nhưng chưa xác nhận key/model. Chưa đạt nghiệm thu ticket 13; xem bằng chứng chi tiết phía trên.

### Cập nhật 2026-09-07

Đã nhận code Python mẫu do chủ project cung cấp; không còn chờ sample. Mẫu dùng placeholder key, chưa phải smoke thành công. [Đối chiếu request và khoảng trống](../../project-fit-wayfinding/assets/kimi-user-sample-2026-09-07.md) đã lưu. Chưa thay model/adapter vì điều tra hợp đồng và phạm vi trial còn mở theo thứ tự đã yêu cầu. Không yêu cầu dán key vào chat; khi cung cấp credential, dùng NVIDIA_API_KEY ở môi trường server/local .env.

Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.
