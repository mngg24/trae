# Media Contract (VideoSup)

Tài liệu này định nghĩa hợp đồng dữ liệu giữa Backend và Worker cho job xử lý video bất đồng bộ.

## 1) Versioning
- `schema_version`: phiên bản schema (semver). Worker phải hỗ trợ backward compatibility tối thiểu cho phiên bản gần nhất.

## 2) State Machine (Job Lifecycle)

- `queued`: job đã được tạo và xếp hàng, chưa xử lý
- `running`: job đang chạy, có `progress` theo step
- `succeeded`: job hoàn tất thành công, có output URL(s)
- `failed`: job thất bại, có `error` theo taxonomy
- `canceled`: job bị huỷ chủ động

`running.progress.step` phải thuộc tập:
- `download`
- `normalize`
- `compose`
- `package`
- `upload`

## 3) Error Taxonomy (chuẩn mã lỗi)

| code | message (gợi ý) | strategy |
|---|---|---|
| `PROVIDER_TIMEOUT` | Provider phản hồi quá thời gian cho phép | `retry` (giới hạn) |
| `BAD_MEDIA` | Tài nguyên media hỏng/không đọc được/không đúng định dạng | `abort` |
| `FFMPEG_FAILED` | FFmpeg trả lỗi khi xử lý | `abort` (hoặc `retry` nếu lỗi phụ thuộc IO) |
| `STORAGE_FAILED` | Upload/lưu trữ thất bại | `retry` (giới hạn) |
| `VALIDATION_ERROR` | Input không hợp lệ theo schema | `abort` |

Worker phải trả về:
- `error.code`: một trong các code trên (hoặc mở rộng có versioning)
- `error.message`: ngắn gọn, không chứa secrets
- `error.strategy`: `retry` hoặc `abort`

## 4) Media Job Spec (JSON Schema)

Schema sử dụng JSON Schema 2020-12.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://videosup.local/schemas/media-job-spec.json",
  "title": "VideoSup Media Job Spec",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "job_id",
    "project_id",
    "created_at",
    "render_profile",
    "output_format",
    "scenes",
    "voiceover_script",
    "subtitle_style",
    "state"
  ],
  "properties": {
    "schema_version": {
      "type": "string",
      "description": "Semver schema version, e.g. 1.0.0",
      "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"
    },
    "job_id": { "type": "string", "minLength": 1 },
    "project_id": { "type": "string", "minLength": 1 },
    "created_at": {
      "type": "string",
      "description": "ISO-8601 timestamp",
      "minLength": 1
    },
    "render_profile": {
      "type": "string",
      "enum": ["preview", "final"]
    },
    "output_format": {
      "type": "string",
      "enum": ["mp4", "hls"]
    },
    "scenes": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["scene_id", "clip_url", "prompt", "expected_duration_ms"],
        "properties": {
          "scene_id": { "type": "string", "minLength": 1 },
          "clip_url": { "type": "string", "minLength": 1 },
          "prompt": { "type": "string" },
          "expected_duration_ms": { "type": "integer", "minimum": 0 }
        }
      }
    },
    "voiceover_script": {
      "type": "string",
      "description": "TTS input text"
    },
    "subtitle_style": {
      "type": "object",
      "additionalProperties": false,
      "required": ["preset"],
      "properties": {
        "preset": {
          "type": "string",
          "description": "Logical preset name, e.g. tiktok_bounce"
        },
        "language": { "type": "string" },
        "max_chars_per_line": { "type": "integer", "minimum": 10 },
        "safe_area_pct": { "type": "number", "minimum": 0, "maximum": 0.5 }
      }
    },
    "state": {
      "type": "object",
      "additionalProperties": false,
      "required": ["status"],
      "properties": {
        "status": {
          "type": "string",
          "enum": ["queued", "running", "succeeded", "failed", "canceled"]
        },
        "progress": {
          "type": "object",
          "additionalProperties": false,
          "required": ["step", "pct"],
          "properties": {
            "step": {
              "type": "string",
              "enum": ["download", "normalize", "compose", "package", "upload"]
            },
            "pct": { "type": "integer", "minimum": 0, "maximum": 100 },
            "detail": { "type": "string" }
          }
        },
        "error": {
          "type": "object",
          "additionalProperties": false,
          "required": ["code", "message", "strategy"],
          "properties": {
            "code": { "type": "string" },
            "message": { "type": "string" },
            "strategy": { "type": "string", "enum": ["retry", "abort"] }
          }
        }
      },
      "allOf": [
        {
          "if": { "properties": { "status": { "const": "running" } } },
          "then": { "required": ["progress"] }
        },
        {
          "if": { "properties": { "status": { "const": "failed" } } },
          "then": { "required": ["error"] }
        }
      ]
    },
    "outputs": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "mp4_url": { "type": "string" },
        "hls_master_url": { "type": "string" }
      }
    }
  }
}
```

## 5) Ví dụ JSON

### 5.1. Case 1: Preview (ngắn)
```json
{
  "schema_version": "1.0.0",
  "job_id": "job_preview_0001",
  "project_id": "videosup_demo",
  "created_at": "2026-05-30T10:00:00Z",
  "render_profile": "preview",
  "output_format": "mp4",
  "scenes": [
    {
      "scene_id": "s1",
      "clip_url": "https://example.invalid/clip1.mp4",
      "prompt": "Nhân vật bước vào khung hình, mỉm cười.",
      "expected_duration_ms": 2500
    }
  ],
  "voiceover_script": "Xin chào! Đây là bản xem trước.",
  "subtitle_style": {
    "preset": "tiktok_bounce",
    "language": "vi",
    "max_chars_per_line": 24,
    "safe_area_pct": 0.12
  },
  "state": {
    "status": "queued"
  }
}
```

### 5.2. Case 2: Final (dài, đầy đủ thuộc tính)
```json
{
  "schema_version": "1.0.0",
  "job_id": "job_final_0420",
  "project_id": "videosup_demo",
  "created_at": "2026-05-30T10:05:00Z",
  "render_profile": "final",
  "output_format": "hls",
  "scenes": [
    {
      "scene_id": "s1",
      "clip_url": "https://example.invalid/clip1.mp4",
      "prompt": "Nhân vật nhìn thẳng camera, gật đầu.",
      "expected_duration_ms": 4200
    },
    {
      "scene_id": "s2",
      "clip_url": "https://example.invalid/clip2.mp4",
      "prompt": "Nhân vật chỉ tay về phía xa, ánh sáng ấm.",
      "expected_duration_ms": 3800
    },
    {
      "scene_id": "s3",
      "clip_url": "https://example.invalid/clip3.mp4",
      "prompt": "Cảnh chuyển động nhẹ, nền thành phố về đêm.",
      "expected_duration_ms": 5200
    }
  ],
  "voiceover_script": "Câu chuyện bắt đầu khi nhân vật quyết định bước ra khỏi vùng an toàn...",
  "subtitle_style": {
    "preset": "tiktok_bounce",
    "language": "vi",
    "max_chars_per_line": 28,
    "safe_area_pct": 0.10
  },
  "state": {
    "status": "running",
    "progress": {
      "step": "download",
      "pct": 10,
      "detail": "Downloading 3 clips"
    }
  },
  "outputs": {
    "hls_master_url": "s3://bucket/jobs/job_final_0420/master.m3u8"
  }
}
```

