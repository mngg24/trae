# Kế hoạch thực thi: Media Processing & DevOps/QA (VideoSup)

Tài liệu này là kế hoạch thực thi cho 2 mảng:
- Media Processing: pipeline xử lý clip/video, audio (TTS), subtitle, đóng gói và phân phối.
- DevOps/QA: CI/CD, kiểm thử đa tầng, quan sát hệ thống, triển khai an toàn và vận hành ổn định.

## 0) Phạm vi, giả định, ràng buộc

### Phạm vi
- Xây dựng worker/pipeline media: nhận input (danh sách clip + script/timing) → render ra MP4 (download) và tuỳ chọn HLS (stream).
- Xây dựng tiêu chuẩn DevOps/QA tối thiểu để phát hiện lỗi sớm, deploy an toàn, theo dõi chất lượng dịch vụ.

### Giả định
- Clip đầu vào đến từ dịch vụ Image-to-Video (ví dụ PixVerse) dưới dạng URL hoặc file.
- Script đầu vào có cấu trúc phân cảnh và có thể sinh TTS.
- Hệ thống backend có mô hình job bất đồng bộ (enqueue job + polling status).

### Ràng buộc nguồn lực
- CPU/IO/disk có hạn; burn subtitle và encode là tác vụ nặng.
- Phụ thuộc dịch vụ ngoài (PixVerse/TTS) có thể chậm, timeout, thay đổi chất lượng.
- Độ tin cậy đầu ra quan trọng hơn tối đa hoá chất lượng trong giai đoạn MVP.

### Thước đo (KPIs/SLOs) dùng xuyên suốt
- Job success rate (theo loại job) và failure reason distribution.
- p50/p95 job duration (queue wait + processing).
- A/V sync: lệch offset audio-video ở p95 (mục tiêu vận hành: ổn định và có thể đo).
- Playback UX (nếu có HLS): startup time, rebuffer rate, CDN cache hit.
- Cost proxy: CPU time / video minute, storage footprint theo tầng (raw/intermediate/final).

### Cách thể hiện “thời gian ước tính”
Kế hoạch sử dụng Effort Level (S/M/L/XL) + điểm phụ thuộc (Dependencies) để lập lịch, thay vì cam kết thời gian cụ thể.
- S: ít việc, ít rủi ro, dễ kiểm chứng
- M: trung bình, cần test/cân chỉnh
- L: phức tạp, nhiều phụ thuộc, cần quan sát và tối ưu
- XL: thay đổi kiến trúc/scale, cần nhiều vòng kiểm định

---

## 1) Giai đoạn 1 — Nền tảng & Chuẩn hoá hợp đồng dữ liệu (Effort: S–M)

### Mục tiêu
- Chuẩn hoá “media contract” để worker có thể chạy ổn định và tái lập được job.
- Thiết lập chuẩn logging/metrics theo job để QA và debug có căn cứ.

### Bước hành động
1. Chốt schema input cho media worker (media job spec)
   - Yêu cầu kỹ thuật:
     - Có `job_id`, `project_id/user_id` (nếu cần), `scenes[]` (mỗi scene có `clip_url`, `prompt`, `expected_duration_ms`), `voiceover_script`, `subtitle_style`, `output` (mp4/hls), `render_profile` (preview/final).
     - Chuẩn hoá time unit (ms) và encoding defaults.
   - Ràng buộc:
     - Dữ liệu phải đủ để replay job mà không cần phụ thuộc trạng thái UI.
   - Checkpoint:
     - 3 ví dụ JSON mẫu (ngắn/vừa/dài) chạy qua validator.
   - Deliverable:
     - File `architecture.md` hoặc `media-contract.md` mô tả schema + ví dụ.
   - Tiêu chí hoàn thành:
     - Team backend/frontend dùng chung schema; không còn “field mơ hồ”.

2. Định nghĩa state machine & lỗi chuẩn cho job
   - Yêu cầu kỹ thuật:
     - Trạng thái: `queued → running → (succeeded|failed|canceled)`, kèm `progress` theo step (download/normalize/compose/package/upload).
     - Error taxonomy: `PROVIDER_TIMEOUT`, `BAD_MEDIA`, `FFMPEG_FAILED`, `STORAGE_FAILED`, `VALIDATION_ERROR`, …
   - Checkpoint:
     - API `/get-status` trả được state + progress + error code thống nhất.
   - Deliverable:
     - Bảng trạng thái & mã lỗi.
   - Tiêu chí hoàn thành:
     - Mỗi lỗi có thông điệp ngắn gọn + hướng xử lý (retry/abort).

3. Chuẩn hoá logging/metrics theo job
   - Yêu cầu kỹ thuật:
     - Log có cấu trúc (ít nhất: `job_id`, `step`, `duration_ms`, `ffmpeg_exit_code`, `provider`, `input_durations`, `output_url`).
     - Lưu “tail” stderr FFmpeg có giới hạn ký tự.
   - Deliverable:
     - Quy ước log + ví dụ log.
   - Tiêu chí hoàn thành:
     - Có thể truy vết 1 job thất bại trong < 5 phút bằng log.

### Rủi ro chính & xử lý
- Rủi ro: schema đổi liên tục gây nghẽn tích hợp
  - Phòng ngừa: chốt schema tối thiểu + versioning (`schema_version`)
  - Xử lý: backward compatible trong 1–2 phiên bản

---

## 2) Giai đoạn 2 — Media Pipeline MVP (MP4) ổn định (Effort: M–L)

### Mục tiêu
- Render MP4 “chạy chắc”: concat clip + TTS + sync cơ bản + burn subtitle, có cleanup và retry hợp lý.
- Có bộ test tích hợp chạy FFmpeg thật với assets nhỏ để chống “vỡ ngầm”.

### Bước hành động
1. Ingest & download clip an toàn
   - Yêu cầu kỹ thuật:
     - Timeout, retry có backoff, giới hạn concurrency tải.
     - Verify: HTTP status, content-length hợp lý, checksum (nếu có).
   - Ràng buộc:
     - Không tải trùng khi retry (cache theo URL + ETag nếu có).
   - Checkpoint:
     - Thống kê download error rate theo provider.
   - Deliverable:
     - Module “fetcher” + test (mock HTTP).
   - Tiêu chí hoàn thành:
     - Tải 3–5 clip liên tiếp ổn định, có retry và không treo job.

2. Normalize media trước khi concat
   - Yêu cầu kỹ thuật:
     - Chuẩn hoá về cùng: resolution, fps, codec, audio presence (nếu cần).
     - Ưu tiên CFR để giảm drift.
   - Ràng buộc:
     - Tránh encode lại nếu clip đã đúng chuẩn (fast path).
   - Checkpoint:
     - Báo cáo “normalize happened?” theo từng clip.
   - Deliverable:
     - Hàm probe + normalize profile.
   - Tiêu chí hoàn thành:
     - Concat không còn fail vì mismatch codec/timebase trong các case mẫu.

3. Compose: concat + audio TTS + mix + sync
   - Yêu cầu kỹ thuật:
     - TTS output chuẩn hoá (sample rate, channels).
     - Loudness normalize (ít nhất tránh clipping/volume lệch lớn).
     - Sync chiến lược rõ ràng:
       - Nếu audio dài hơn video: kéo dài video (freeze/loop nhẹ) hoặc cắt audio theo rule.
       - Nếu video dài hơn audio: pad audio hoặc giữ silence.
   - Ràng buộc:
     - Đảm bảo job deterministic: cùng input → cùng output profile.
   - Checkpoint:
     - Ghi duration trước/sau compose; cảnh báo khi lệch quá ngưỡng.
   - Deliverable:
     - Pipeline FFmpeg compose + cấu hình profile.
   - Tiêu chí hoàn thành:
     - p95 lệch duration giữa audio và video giảm và có thể đo.

4. Subtitle: generate timed subtitles + burn-in
   - Yêu cầu kỹ thuật:
     - Subtitle format: SRT/ASS (ASS phù hợp hiệu ứng bouncing/highlight).
     - Rule chia câu, max chars/line, safe area (không che UI).
   - Ràng buộc:
     - Burn-in làm tăng thời gian encode; cần profile preview/final.
   - Checkpoint:
     - Visual sanity check với 3 kịch bản: ngắn/vừa/dài.
   - Deliverable:
     - Generator subtitle + style template.
   - Tiêu chí hoàn thành:
     - Subtitle không tràn màn, timing hợp lý, không gây crash encode.

5. Output MP4 + upload + cleanup
   - Yêu cầu kỹ thuật:
     - Atomic write: output tmp → rename.
     - Cleanup bắt buộc (temp dir, intermediate).
     - Upload tới storage (nếu có) kèm metadata (duration, resolution).
   - Checkpoint:
     - Disk usage theo job; đảm bảo không leak.
   - Deliverable:
     - Artifact MP4 + URL lưu trữ.
   - Tiêu chí hoàn thành:
     - Chạy 50 job mẫu không tăng disk bất thường; job fail cũng cleanup.

6. Integration tests cho media pipeline
   - Yêu cầu kỹ thuật:
     - Dùng assets nhỏ cố định (2–3 clip mp4 + audio) để test concat/mux/burn.
     - So khớp: file tồn tại, duration hợp lý, ffprobe pass.
   - Deliverable:
     - Bộ test chạy được trong CI.
   - Tiêu chí hoàn thành:
     - PR thay đổi pipeline không làm test đỏ ngẫu nhiên.

### Rủi ro chính & xử lý
- Rủi ro: FFmpeg lỗi do input “bẩn”/URL hỏng
  - Phòng ngừa: probe trước, retry download, fallback normalize
  - Xử lý: mark failed có lý do + lưu artifacts debug (giới hạn)
- Rủi ro: lệch tiếng khó kiểm soát
  - Phòng ngừa: CFR normalize + đo duration/offset + rule sync rõ ràng
  - Xử lý: thêm “sync mode” lựa chọn (stretch/cut/pad) theo profile

---

## 3) Giai đoạn 3 — Tối ưu trải nghiệm phân phối (Preview + HLS/ABR + Cache) (Effort: M–L)

### Mục tiêu
- Người dùng xem nhanh (preview) trong khi final vẫn được render.
- Playback mượt hơn nhờ HLS/ABR và CDN caching.
- Giảm băng thông và egress nhờ cache và phân tầng lưu trữ.

### Bước hành động
1. Tách render profile: preview vs final
   - Yêu cầu kỹ thuật:
     - Preview ưu tiên tốc độ (lower res/bitrate, subtitle đơn giản).
     - Final ưu tiên chất lượng (profile chuẩn, subtitle đầy đủ).
   - Deliverable:
     - 2 profile cấu hình encode.
   - Tiêu chí hoàn thành:
     - Tỉ lệ người dùng nhận preview sớm tăng; job final không bị ảnh hưởng.

2. HLS/ABR packaging
   - Yêu cầu kỹ thuật:
     - Ladder tối thiểu 2–3 mức (tuỳ tài nguyên).
     - Playlist đúng chuẩn, segment duration hợp lý.
   - Ràng buộc:
     - Tăng số file; cần lifecycle rõ.
   - Deliverable:
     - HLS output + hướng dẫn player.
   - Tiêu chí hoàn thành:
     - Playback startup nhanh hơn MP4 trực tiếp trên mạng yếu.

3. CDN/cache & cache key theo content hash
   - Yêu cầu kỹ thuật:
     - Cache final theo `content_hash` (script + prompts + ảnh nhân vật + profile).
     - CDN cache headers phù hợp.
   - Deliverable:
     - Cơ chế cache + thống kê cache hit.
   - Tiêu chí hoàn thành:
     - Cache hit tăng theo usage; giảm egress và thời gian tải lại.

4. Lưu trữ phân tầng & lifecycle policy
   - Yêu cầu kỹ thuật:
     - TTL raw clips ngắn; intermediate xoá ngay; final theo chính sách sản phẩm.
   - Deliverable:
     - Policy rõ + job cleanup chạy định kỳ.
   - Tiêu chí hoàn thành:
     - Storage footprint ổn định theo lượng user thực tế.

### Rủi ro chính & xử lý
- Rủi ro: ABR/HLS phức tạp làm tăng lỗi playback
  - Phòng ngừa: giữ MP4 fallback; test player trên trình duyệt mục tiêu
  - Xử lý: feature flag bật/tắt HLS

---

## 4) Giai đoạn 4 — DevOps/QA “production-ready” (CI/CD, quan sát, triển khai an toàn) (Effort: M–XL)

### Mục tiêu
- Tự động hoá test và triển khai để giảm lỗi do con người.
- Có khả năng phát hiện lỗi sớm (shift-left) và phản ứng nhanh khi sự cố.

### Bước hành động
1. Chuẩn hoá môi trường chạy bằng container
   - Yêu cầu kỹ thuật:
     - Backend API, worker media, frontend tách riêng.
     - FFmpeg version pin; chạy được giống nhau giữa dev/staging/prod.
   - Deliverable:
     - Dockerfile(s) + compose cho local parity.
   - Tiêu chí hoàn thành:
     - Máy mới có thể chạy hệ thống bằng một cấu hình thống nhất.

2. Thiết lập CI: build + test + security checks
   - Yêu cầu kỹ thuật:
     - Unit test, integration media test (assets nhỏ), lint/format.
     - Dependency scan, secret scan tối thiểu.
   - Deliverable:
     - Pipeline CI chạy trên mỗi PR.
   - Tiêu chí hoàn thành:
     - Không merge nếu test fail; giảm lỗi “vỡ sau merge”.

3. Thiết lập CD: staging tự động + prod có kiểm soát
   - Yêu cầu kỹ thuật:
     - Deploy staging tự động sau merge main.
     - Prod có canary/rolling + rollback.
   - Deliverable:
     - Quy trình deploy + runbook rollback.
   - Tiêu chí hoàn thành:
     - Release không làm gián đoạn dịch vụ; rollback có thể thực hiện theo runbook.

4. QA chiến lược: unit/integration/E2E/load
   - Yêu cầu kỹ thuật:
     - E2E: UI → create job → polling → playback → download.
     - Load test: N job đồng thời, đo backlog và p95 duration.
   - Deliverable:
     - Bộ test + kịch bản chạy định kỳ/On-demand.
   - Tiêu chí hoàn thành:
     - Có baseline số liệu; phát hiện regression trước khi lên prod.

5. Observability: metrics/logs/tracing + alerting
   - Yêu cầu kỹ thuật:
     - Dashboard: queue depth, success rate, p95 duration, disk usage, provider error rate.
     - Alert: backlog tăng, fail rate tăng, disk gần đầy, error spike.
   - Deliverable:
     - Dashboard + alert rules + runbook xử lý.
   - Tiêu chí hoàn thành:
     - Sự cố phổ biến được phát hiện sớm và có quy trình xử lý.

### Rủi ro chính & xử lý
- Rủi ro: phụ thuộc dịch vụ ngoài gây flaky
  - Phòng ngừa: retry/backoff, timeout, circuit breaker, mock trong test
  - Xử lý: degrade gracefully (trả trạng thái chờ/nhắc thử lại)
- Rủi ro: chi phí compute/storage tăng nhanh
  - Phòng ngừa: TTL + cache + profile preview/final + giới hạn concurrency
  - Xử lý: autoscale worker theo queue; cap output retention
- Rủi ro: lộ secrets / vi phạm bảo mật
  - Phòng ngừa: secret manager/env, secret scan, least privilege
  - Xử lý: rotate keys, audit logs, incident checklist

---

## 5) Checkpoints theo mốc (gợi ý)
- C1: Contract + state machine + logging/metrics cơ bản hoàn tất
- C2: MVP MP4 render chạy ổn định với bộ assets mẫu + cleanup tốt
- C3: Preview/final profile + (tuỳ chọn) HLS + cache/lifecycle
- C4: CI/CD + test đa tầng + giám sát + deploy an toàn

