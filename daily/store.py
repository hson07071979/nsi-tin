"""Kho nến: cào lịch sử MỘT LẦN, sau đó mỗi ngày chỉ nối thêm cây nến của phiên.

Nến lưu ở .cache/daily_nen/<MÃ>.json (không commit; workflow giữ bằng actions/cache).
Khi nào dựng lại từ đầu (gọi dchart):
  - chưa có kho, hoặc kho quá ngắn;
  - kho thiếu phiên (lần chạy trước bị hỏng/nghỉ);
  - giá tham chiếu hôm nay lệch giá đóng cửa trong kho > 0,3% → có chia cổ tức/thưởng/phát hành,
    nến cũ phải được điều chỉnh lại.
"""
from __future__ import annotations

import json
from pathlib import Path

from tin.common import ROOT

from . import sources

KHO = ROOT / ".cache" / "daily_nen"
LECH_TOI_DA = 0.003


def _path(sym: str) -> Path:
    return KHO / f"{sym}.json"


def load(sym: str) -> list[dict]:
    try:
        return json.loads(_path(sym).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save(sym: str, bars: list[dict]) -> None:
    KHO.mkdir(parents=True, exist_ok=True)
    _path(sym).write_text(json.dumps(bars, separators=(",", ":")), encoding="utf-8")


def update(sym: str, today: str, prev_session: str | None, bar_today: dict | None, keep: int = 300,
           ly_do: list | None = None) -> list[dict]:
    """Trả chuỗi nến đã có phiên `today` (nếu phiên hôm nay có giao dịch).

    bar_today: dict giá phiên của finfo (open/high/low/close đã điều chỉnh, kl, tham_chieu).
    prev_session: ngày phiên liền trước theo VN-Index — để phát hiện kho thiếu phiên.
    """
    bars = load(sym)
    can_dung_lai = False
    why = ""
    if len(bars) < 60:
        can_dung_lai, why = True, "kho trống/ngắn"
    else:
        last = bars[-1]
        if last["d"] == today:
            bars = bars[:-1]
            last = bars[-1] if bars else None
        if last and prev_session and last["d"] < prev_session:
            can_dung_lai, why = True, f"kho thiếu phiên (cuối {last['d']})"
        elif last and bar_today and bar_today.get("tham_chieu") and last["c"]:
            ref = bar_today["tham_chieu"]
            if abs(last["c"] / ref - 1) > LECH_TOI_DA:
                can_dung_lai, why = True, f"giá tham chiếu {ref} lệch nến cũ {last['c']} (quyền?)"
    if can_dung_lai:
        fresh = sources.dchart(sym, days=keep + 5)
        if fresh:
            bars = [b for b in fresh if b["d"] < today]
            if ly_do is not None:
                ly_do.append(f"{sym}: dựng lại kho — {why}")
        elif ly_do is not None:
            ly_do.append(f"{sym}: cần dựng lại ({why}) nhưng dchart không trả dữ liệu")
    if bar_today and bar_today.get("close") and (bar_today.get("kl") or 0) > 0:
        bars.append({"d": today, "o": bar_today.get("open") or bar_today["close"],
                     "h": bar_today.get("high") or bar_today["close"], "l": bar_today.get("low") or bar_today["close"],
                     "c": bar_today["close"], "v": bar_today.get("kl") or 0})
    elif bar_today and bar_today.get("tham_chieu") and bars and bars[-1]["d"] < today:
        # cả phiên không khớp lệnh: ghi nến phẳng ở giá tham chiếu để kho không bị "thiếu phiên"
        ref = bar_today["tham_chieu"]
        bars.append({"d": today, "o": ref, "h": ref, "l": ref, "c": ref, "v": 0})
    elif bar_today is None and bars and bars[-1]["d"] != today:
        # finfo chưa có giá mã này → thử dchart (nó có nến trong ngày sau giờ đóng cửa)
        fresh = sources.dchart(sym, days=5)
        if fresh and fresh[-1]["d"] == today:
            bars.append(fresh[-1])
    bars = bars[-keep:]
    if bars:
        save(sym, bars)
    return bars


def index_bars(today: str, idx_days: list[dict], keep: int = 300) -> list[dict]:
    """Nến VN-Index: lịch sử từ dchart (mỗi lần 1 lượt gọi), phiên hôm nay ghi đè bằng số finfo."""
    bars = sources.dchart("VNINDEX", days=keep + 5)
    if not bars:
        bars = [{"d": x["date"], "o": x["open"], "h": x["high"], "l": x["low"], "c": x["close"], "v": x["kl"] or 0}
                for x in reversed(idx_days) if x.get("close")]
    t = next((x for x in idx_days if x.get("date") == today), None)
    if t and t.get("close"):
        bars = [b for b in bars if b["d"] != today]
        bars.append({"d": today, "o": t["open"], "h": t["high"], "l": t["low"], "c": t["close"], "v": t.get("kl") or 0})
    return bars[-keep:]
