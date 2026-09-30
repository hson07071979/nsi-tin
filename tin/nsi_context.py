"""Bối cảnh từ Nguyễn Sơn Invest (tuỳ chọn): đèn thị trường + mã đang cầm + watchlist.
Đọc qua URL cấu hình trong secrets (NSI_THRESHOLDS_URL, NSI_PORTFOLIO_URL). Hỏng thì bỏ qua, không làm sập."""
from __future__ import annotations

import os
import re

from .common import http_get

SYM = re.compile(r"^[A-Z0-9]{3}$")


def _walk_syms(obj, keys=("sym", "ma", "symbol", "code", "ticker"), out=None):
    out = out if out is not None else set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys and isinstance(v, str) and SYM.match(v):
                out.add(v)
            else:
                _walk_syms(v, keys, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_syms(v, keys, out)
    return out


def _find(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find(v, key)
            if r is not None:
                return r
    return None


def load() -> dict:
    ctx: dict = {}
    hdr = {}
    if os.environ.get("NSI_READ_TOKEN"):
        hdr = {"Authorization": f"Bearer {os.environ['NSI_READ_TOKEN']}", "Accept": "application/vnd.github.raw"}
    u = os.environ.get("NSI_THRESHOLDS_URL")
    if u:
        r = http_get(u, headers=hdr, tries=2)
        if r is not None:
            try:
                j = r.json()
                rl = _find(j, "regime_live")
                ctx["den_thi_truong"] = (rl or {}).get("state") if isinstance(rl, dict) else _find(j, "regime")
                ctx["asof"] = _find(j, "asof")
                wl = _find(j, "watchlist")
                if wl is not None:
                    ctx["watchlist"] = sorted(_walk_syms(wl))[:40]
            except ValueError:
                pass
    u = os.environ.get("NSI_PORTFOLIO_URL")
    if u:
        r = http_get(u, headers=hdr, tries=2)
        if r is not None:
            try:
                ctx["dang_cam"] = sorted(_walk_syms(r.json()))[:30]
            except ValueError:
                pass
    return ctx
