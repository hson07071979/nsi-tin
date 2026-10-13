"""Đẩy PPTX lên Cloudflare R2 (API tương thích S3). Trang quản trị /daily đọc lại qua R2 binding.

Secrets cần trong repo (Settings → Secrets → Actions):
  R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET (mặc định nsi-slides)
Thiếu secret → bỏ qua upload, không làm hỏng workflow (file vẫn có trong artifact của lượt chạy).

Khóa trên R2:
  daily/<ngày>.pptx   metadata: nguon = gemini | claude, luc = giờ dựng
  daily/latest.json   {"ngay", "nguon", "luc"} cho nút "Tải PPT" mặc định
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

VN = timezone(timedelta(hours=7))
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _client():
    acc, key, sec = (os.environ.get(k) for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"))
    if not (acc and key and sec):
        return None
    import boto3  # noqa: PLC0415
    return boto3.client("s3", endpoint_url=f"https://{acc}.r2.cloudflarestorage.com", aws_access_key_id=key,
                        aws_secret_access_key=sec, region_name="auto")


def put(ngay: str, pptx: Path, nguon: str) -> bool:
    c = _client()
    if c is None:
        print("R2: thiếu secret → bỏ qua upload")
        return False
    bucket = os.environ.get("R2_BUCKET") or "nsi-slides"
    luc = datetime.now(VN).isoformat(timespec="minutes")
    # bản Gemini (nháp) không được đè bản Claude đã kiểm của cùng ngày
    if nguon == "gemini":
        try:
            h = c.head_object(Bucket=bucket, Key=f"daily/{ngay}.pptx")
            if (h.get("Metadata") or {}).get("nguon") == "claude":
                print("R2: đã có bản Claude cho ngày này → giữ nguyên, không đè bằng bản nháp")
                return False
        except Exception:  # noqa: BLE001 (chưa có file)
            pass
    c.upload_file(str(pptx), bucket, f"daily/{ngay}.pptx",
                  ExtraArgs={"ContentType": PPTX, "Metadata": {"nguon": nguon, "luc": luc}})
    c.put_object(Bucket=bucket, Key="daily/latest.json", ContentType="application/json",
                 Body=json.dumps({"ngay": ngay, "nguon": nguon, "luc": luc}).encode())
    print(f"R2: đã đẩy daily/{ngay}.pptx ({nguon})")
    return True
