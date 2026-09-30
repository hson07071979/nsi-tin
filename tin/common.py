"""Tiện ích chung: giờ VN, gọi mạng có thử lại, làm sạch chữ, đọc/ghi JSON."""
from __future__ import annotations

import html
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

VN = timezone(timedelta(hours=7))
ROOT = Path(__file__).resolve().parent.parent
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def now_vn() -> datetime:
    """Giờ VN hiện tại. Cho phép ép giờ khi test: NSI_TIN_NOW=2026-09-30T07:00."""
    fake = os.environ.get("NSI_TIN_NOW")
    if fake:
        d = datetime.fromisoformat(fake)
        return d if d.tzinfo else d.replace(tzinfo=VN)
    return datetime.now(VN)


def http_get(url: str, *, timeout: int = 25, tries: int = 3, headers: dict | None = None,
             params: dict | None = None) -> requests.Response | None:
    """GET có thử lại. Hỏng hết thì trả None (nguồn lỗi không được làm sập cả buổi sáng)."""
    h = {"User-Agent": UA, "Accept-Language": "vi,en;q=0.8"}
    if headers:
        h.update(headers)
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=h, params=params, timeout=timeout)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
            if r.status_code in (403, 404):
                break
        except requests.RequestException as e:  # noqa: PERF203
            last = str(e)[:160]
        time.sleep(1.5 * (i + 1))
    print(f"  [mạng] hỏng {url} — {last}")
    return None


_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def clean_text(s: str | None, limit: int | None = None) -> str:
    if not s:
        return ""
    s = html.unescape(_TAG.sub(" ", s))
    s = _WS.sub(" ", s).strip()
    if limit and len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0] + "…"
    return s


def khong_dau(s: str) -> str:
    """Bỏ dấu tiếng Việt + chữ thường, để so khớp tên nhóm / từ khoá."""
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return _WS.sub(" ", s.lower()).strip()


def read_json(path: Path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def iso(d: datetime | None) -> str | None:
    return d.astimezone(VN).isoformat(timespec="minutes") if d else None


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=VN)
    except ValueError:
        return None
