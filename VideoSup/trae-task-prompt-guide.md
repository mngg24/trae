# Hướng dẫn tối ưu prompt để giao Task cho Trae (Playbook)

Mục tiêu của tài liệu:
- Giúp mô tả yêu cầu rõ ràng, có thể kiểm chứng, hạn chế hiểu lầm.
- Tối ưu vòng lặp làm việc: Trae hiểu đúng ngay lần đầu, hoặc biết cách tinh chỉnh khi lệch.

## 1) Nguyên tắc chung để viết prompt hiệu quả

### 1.1. “Đầu vào bắt buộc” nên có trong mọi prompt
- Bối cảnh dự án: mục tiêu sản phẩm, kiến trúc/stack, ràng buộc (async jobs, provider ngoài).
- Phạm vi thay đổi: file/module nào, có được tạo file mới không, có ảnh hưởng API/DB không.
- Tiêu chuẩn kỹ thuật: style, conventions, error handling, logging, security, performance.
- Đầu ra mong muốn: thay đổi code, tài liệu, test, lệnh chạy (nếu cần), tiêu chí “đúng”.
- Trường hợp biên: input xấu, timeout, retry, idempotency, cleanup.
- Cách xác minh: unit/integration/E2E/load; sample data; expected results.

### 1.2. Quy tắc làm rõ mơ hồ
- Thay “nhanh/chất lượng cao” bằng chỉ số: p95 render, success rate, bitrate/CRF, cache hit.
- Nếu có nhiều phương án: yêu cầu Trae nêu trade-off và đề xuất 1 phương án mặc định.
- Chốt “definition of done”: test pass, không leak disk, có log theo job_id, rollback plan (nếu deploy).

### 1.3. Quy tắc tránh “task rỗng”
- Không giao “làm pipeline FFmpeg” chung chung.
- Chia theo step có thể test được: normalize → concat → mux audio → subtitle → output.
- Mỗi step phải có acceptance criteria và ví dụ input/output.

### 1.4. Ràng buộc nguồn lực và an toàn
- Nêu rõ giới hạn: CPU-only/GPU available, disk tạm, concurrency.
- Nêu yêu cầu an toàn: không log secrets, không hardcode keys, giới hạn retry, TTL cho artifacts.

---

## 2) Cấu trúc prompt chuẩn (Template chung)

Sao chép và điền theo khung:

### [Tựa đề]
Mục tiêu ngắn gọn trong 1 câu.

### [Bối cảnh]
- Dự án: …
- Stack/Module liên quan: …
- Hành vi hiện tại: …
- Vấn đề/nhu cầu: …

### [Yêu cầu]
- Phạm vi: …
- Chi tiết cần làm (bullet rõ ràng): …
- Không làm (out of scope): …

### [Ràng buộc]
- Hiệu năng: …
- Bảo mật: …
- Tương thích: …
- Nguồn lực: …

### [Tiêu chí hoàn thành]
- Điều kiện pass/fail cụ thể: …
- Test cần có/chạy được: …
- Logging/metrics cần có: …

### [Dữ liệu mẫu / Case tái hiện]
- Input mẫu: …
- Kết quả mong đợi: …
- Case lỗi dự kiến: …

### [Cách bàn giao]
- Danh sách file thay đổi: …
- Hướng dẫn chạy (nếu cần): …

---

## 3) Playbook theo luồng công việc

### 3.1. Luồng: Phát triển tính năng mới

#### Giai đoạn A — Làm rõ yêu cầu & thiết kế
Thông tin bắt buộc:
- User flow, API contract, schema dữ liệu, state machine, metrics cần đo.
- Rủi ro và chiến lược fallback/feature flag.

Prompt mẫu:
"""
Bạn hãy thiết kế state machine và error taxonomy cho job render video.
Bối cảnh: hệ thống async job; worker chạy FFmpeg; clip từ provider ngoài; cần /get-status.
Yêu cầu: đề xuất các trạng thái, progress steps, mã lỗi; output ở dạng bảng + JSON mẫu.
Tiêu chí hoàn thành: có thể dùng trực tiếp để implement, gồm ví dụ job success/fail, hướng retry.
"""

#### Giai đoạn B — Implement theo module
Thông tin bắt buộc:
- File/module đích, interface, điểm tích hợp, dependency hiện có.
- Acceptance criteria và test tối thiểu.

Prompt mẫu:
"""
Implement module tải clip có retry/backoff và cache theo URL+ETag (nếu có).
Ràng buộc: timeout rõ; giới hạn concurrency; không tải trùng khi retry; log theo job_id.
Tiêu chí hoàn thành: có unit test mock HTTP; có error code phân loại.
"""

#### Giai đoạn C — Xác minh & hardening
Thông tin bắt buộc:
- Bộ case: clip hỏng, URL 404, provider timeout, disk gần đầy.
- Mục tiêu: không leak temp, job fail có lý do.

Prompt mẫu:
"""
Thêm integration test chạy FFmpeg thật với 2 clip mẫu và 1 audio mẫu.
Mục tiêu: xác nhận concat + mux audio + burn subtitle chạy được, ffprobe pass.
Tiêu chí: test deterministic, output duration trong ngưỡng hợp lý.
"""

---

### 3.2. Luồng: Sửa lỗi (Bugfix)

#### Giai đoạn A — Thu thập bằng chứng
Thông tin bắt buộc:
- Log/error message, input tái hiện, phiên bản môi trường, expected vs actual.

Prompt mẫu:
"""
Bug: FFmpeg concat fail với lỗi 'Non-monotonous DTS' khi ghép nhiều clip.
Dữ liệu: (đính kèm stderr tail + thông số ffprobe của từng clip).
Yêu cầu: phân tích nguyên nhân, đề xuất fix ít rủi ro; cập nhật pipeline.
Tiêu chí: integration test bổ sung để lỗi không tái diễn.
"""

#### Giai đoạn B — Fix + regression test
Thông tin bắt buộc:
- Đề nghị Trae chỉ thay đổi tối thiểu, thêm test.

Prompt mẫu:
"""
Hãy sửa lỗi và chỉ trả về diff code + test mới.
Ràng buộc: không đổi API contract; không thêm dependency mới nếu không cần.
"""

---

### 3.3. Luồng: Tối ưu hiệu năng/chi phí

#### Giai đoạn A — Baseline & đo lường
Thông tin bắt buộc:
- Số liệu p50/p95 duration, CPU%, queue depth, storage footprint, egress.

Prompt mẫu:
"""
Mục tiêu: giảm p95 render time của job 'final' mà không giảm chất lượng quá mức.
Dữ liệu baseline: p95=..., CPU=..., preset hiện tại=..., CRF=...
Yêu cầu: đề xuất 3 phương án tối ưu (trade-off), chọn 1 mặc định; nêu KPI theo dõi.
"""

#### Giai đoạn B — Implement có feature flag
Thông tin bắt buộc:
- Flag name, rollout plan, rollback.

Prompt mẫu:
"""
Thêm render profile 'preview' tách khỏi 'final' bằng feature flag.
Tiêu chí: preview tạo nhanh hơn, final không ảnh hưởng; có log phân biệt profile.
"""

---

### 3.4. Luồng: Thiết kế tài liệu (Docs/Design)

#### Giai đoạn A — Chuẩn hoá cấu trúc tài liệu
Thông tin bắt buộc:
- Audience (dev/ops), mục tiêu, format (markdown), deliverables.

Prompt mẫu:
"""
Hãy tạo tài liệu runbook xử lý sự cố cho worker media:
Các mục: triệu chứng, nguyên nhân thường gặp, cách kiểm tra, cách khắc phục, khi nào escalate.
Ràng buộc: ngắn gọn, dùng checklist, có mapping error codes → hành động.
"""

---

## 4) Ví dụ prompt hiệu quả vs chưa tối ưu (kèm phân tích)

### 4.1. Chưa tối ưu
"""
Làm giúp mình phần FFmpeg ghép video với audio và subtitle cho dự án.
"""

Vấn đề:
- Không có input schema, không có định nghĩa subtitle style/timing.
- Không có tiêu chí hoàn thành, không có test, không có ràng buộc hiệu năng.
- Không nói rõ output (MP4 hay HLS), có lưu trữ hay không.

### 4.2. Tối ưu
"""
Mục tiêu: Implement pipeline FFmpeg render MP4 từ danh sách clip + TTS + subtitle.
Bối cảnh: worker async; mỗi job có job_id; clip đầu vào từ URL (provider ngoài).
Yêu cầu:
1) Download clips với timeout+retry(backoff) + cache theo URL, log theo job_id.
2) Normalize clip về cùng resolution=720p, fps=30, codec=h264+aac trước concat.
3) Generate subtitle ASS theo timing từ TTS; style: chữ to, viền, highlight theo từ.
4) Compose: concat clip + mux TTS, đảm bảo duration không lệch quá ngưỡng; cleanup temp bắt buộc.
Ràng buộc: không log secrets; giới hạn concurrency; nếu clip hỏng thì fail có error code chuẩn.
Tiêu chí hoàn thành:
- Có integration test chạy FFmpeg với assets nhỏ; ffprobe output pass.
- Job fail trả được error taxonomy; không leak disk sau N lần chạy.
"""

Điểm khác biệt:
- Rõ bối cảnh + input + output + ràng buộc + kiểm chứng.
- Chia thành bước có thể test; giảm rủi ro “Trae hiểu sai mục tiêu”.

---

## 5) Cách tinh chỉnh khi Trae làm chưa đúng yêu cầu

### 5.1. Chiến lược “đưa bằng chứng”
- Đưa input tái hiện tối thiểu: 1–2 clip, stderr tail, ffprobe output.
- Nêu expected vs actual rõ ràng bằng con số (duration, exit code, bitrate).

Prompt gợi ý:
"""
Kết quả hiện tại sai: subtitle bị trễ ~800ms và có đoạn bị tràn màn.
Đây là 5 dòng subtitle và duration TTS tương ứng: …
Yêu cầu: điều chỉnh thuật toán timing + giới hạn max chars/line; bổ sung test cho case này.
"""

### 5.2. Chiến lược “khống chế phạm vi thay đổi”
- Yêu cầu: chỉ trả về diff; không refactor lan rộng; không thêm dependency.

Prompt gợi ý:
"""
Chỉ sửa trong module subtitle generator; không thay đổi API contract.
Chỉ trả về patch/diff và test mới.
"""

### 5.3. Chiến lược “đóng tiêu chí”
- Khi Trae trả lời dài nhưng khó kiểm chứng: yêu cầu checklist DoD + cách chạy test.

Prompt gợi ý:
"""
Hãy bổ sung tiêu chí hoàn thành dạng checklist và cách xác minh từng mục.
"""

### 5.4. Nếu nghi ngờ thiếu ngữ cảnh dự án
- Yêu cầu Trae liệt kê những thông tin còn thiếu và hỏi lại theo câu hỏi đóng.

Prompt gợi ý:
"""
Trước khi implement, hãy hỏi tối đa 5 câu để chốt:
output cần MP4 hay HLS, có GPU không, subtitle style cụ thể, storage dùng loại nào, giới hạn concurrency.
"""

