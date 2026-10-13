"""Đẩy PPTX lên Cloudflare Workers KV (miễn phí, không cần thẻ). Trang quản trị /daily đọc lại qua KV binding SLIDES.

Sơn chọn KV thay R2 ngày 13/10/2026 vì tài khoản chưa bật R2 (bật R2 phải đăng ký gói tính tiền).
Giới hạn KV miễn phí: 1 GB, 1.000 lượt ghi/ngày, mỗi giá trị tối đa 25 MiB — PPT ~4 MB nên dư.

Secrets cần trong repo (Settings → Secrets → Actions):
  CF_ACCOUNT_ID, CF_KV_NAMESPACE_ID, CF_API_TOKEN (token quyền "Workers KV Storage: Edit")
Thiếu secret → bỏ qua upload, không làm hỏng workflow (file vẫn có trong Artifacts của lượt chạy).

Khóa trong KV:
  daily/<ngày>.pptx   metadata: {nguon: gemini | claude, luc}
  daily/latest        {"ngay", "nguon", "luc"}
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

VN = timezone(timedelta(hours=7))
API = "https://api.cloudflare.com/client/v4/accounts/{acc}/storage/kv/namespaces/{ns}"


def _cfg():
    acc, ns, tok = (os.environ.get(k) for k in ("CF_ACCOUNT_ID", "CF_KV_NAMESPACE_ID", "CF_API_TOKEN"))
    if not (acc and ns and tok):
        return None
    return API.format(acc=acc, ns=ns), {"Authorization": f"Bearer {tok}"}


def _meta(base: str, h: dict, key: str) -> dict:
    r = requests.get(f"{base}/metadata/{key}", headers=h, timeout=30)
    if r.status_code != 200:
        return {}
    return (r.json() or {}).get("result") or {}


def put(ngay: str, pptx: Path, nguon: str) -> bool:
    c = _cfg()
    if c is None:
        print("KV: thiếu secret → bỏ qua upload")
        return False
    base, h = c
    key = f"daily/{ngay}.pptx"
    # bản Gemini (nháp) không được đè bản Claude đã kiểm của cùng ngày
    if nguon == "gemini" and _meta(base, h, key).get("nguon") == "claude":
        print("KV: đã có bản Claude cho ngày này → giữ nguyên, không đè bằng bản nháp")
        return False
    luc = datetime.now(VN).isoformat(timespec="minutes")
    meta = {"nguon": nguon, "luc": luc}
    with open(pptx, "rb") as f:
        r = requests.put(f"{base}/values/{key}", headers=h, timeout=120,
                         files={"value": (pptx.name, f, "application/octet-stream"),
                                "metadata": (None, json.dumps(meta), "application/json")})
    if not r.ok:
        raise RuntimeError(f"KV ghi {key} lỗi {r.status_code}: {r.text[:200]}")
    r = requests.put(f"{base}/values/daily/latest", headers=h, timeout=30,
                     data=json.dumps({"ngay": ngay, **meta}).encode())
    if not r.ok:
        raise RuntimeError(f"KV ghi daily/latest lỗi {r.status_code}: {r.text[:200]}")
    print(f"KV: đã đẩy {key} ({nguon})")
    return True
