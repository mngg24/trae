# Worker (VideoSup)

## Cấu trúc thư mục

- `videosup_worker/`: mã nguồn worker (contracts, fetcher, utilities)
- `tests/`: unit tests

## Chạy unit tests

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## Ghi chú

- Integration tests pipeline yêu cầu có `ffmpeg` và `ffprobe` trong PATH. Nếu thiếu, các test này sẽ bị skip.

## Chạy trong Docker (kèm MinIO)

Từ thư mục root repo:

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from worker
```
