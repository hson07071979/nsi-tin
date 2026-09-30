"""Ảnh chụp vĩ mô định lượng mỗi sáng + sổ nhật ký điểm-thời-gian (data/macro_daily.csv).

Nguyên tắc điểm-thời-gian: mỗi dòng sổ chỉ ghi những gì BIẾT ĐƯỢC lúc 7h sáng hôm đó.
Không sửa dòng cũ. Research sau này đọc sổ này để không nhìn trước.
"""
from __future__ import annotations

import csv
import statistics
from datetime import datetime, timedelta
from pathlib import Path

from .common import VN, http_get

YAHOO = {
    "dxy": "DX-Y.NYB",
    "us10y": "^TNX",
    "usdvnd": "VND=X",
    "brent": "BZ=F",
    "gold": "GC=F",
    "vix": "^VIX",
    "spx": "^GSPC",
}
COLS = ["date", "lnh_on", "lnh_1w", "lnh_nguon", "usdvnd", "dxy", "us10y", "brent", "gold", "vix", "spx", "vnindex"]


def _yahoo_closes(sym: str) -> list[tuple[datetime, float]]:
    r = http_get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                 params={"range": "3mo", "interval": "1d"}, tries=2)
    if r is None:
        return []
    try:
        res = r.json()["chart"]["result"][0]
        ts, cl = res["timestamp"], res["indicators"]["quote"][0]["close"]
        return [(datetime.fromtimestamp(t, VN), float(c)) for t, c in zip(ts, cl) if c is not None]
    except (KeyError, IndexError, TypeError, ValueError):
        return []


def _vnindex(end: datetime) -> list[tuple[datetime, float]]:
    now = int(end.timestamp())
    r = http_get("https://dchart-api.vndirect.com.vn/dchart/history",
                 params={"resolution": "D", "symbol": "VNINDEX", "from": now - 120 * 86400, "to": now}, tries=2)
    if r is None:
        return []
    try:
        j = r.json()
        return [(datetime.fromtimestamp(t, VN), float(c)) for t, c in zip(j["t"], j["c"])]
    except (KeyError, TypeError, ValueError):
        return []


def _chg(series: list[tuple[datetime, float]], n: int, pct: bool) -> float | None:
    if len(series) <= n:
        return None
    a, b = series[-1 - n][1], series[-1][1]
    if pct:
        return round((b / a - 1) * 100, 3) if a else None
    return round(b - a, 4)


def snapshot(end: datetime) -> dict:
    """Số liệu thị trường quốc tế + VN-Index, chỉ dùng phiên ĐÃ ĐÓNG trước 7h."""
    snap: dict = {"at": end.isoformat(timespec="minutes")}
    for key, sym in YAHOO.items():
        s = [x for x in _yahoo_closes(sym) if x[0] <= end]
        if not s:
            snap[key] = None
            continue
        snap[key] = round(s[-1][1], 4)
        snap[f"{key}_asof"] = s[-1][0].date().isoformat()
        if key == "us10y":
            c5, c20 = _chg(s, 5, False), _chg(s, 20, False)
            snap["us10y_chg5_bp"] = round(c5 * 100, 1) if c5 is not None else None
            snap["us10y_chg20_bp"] = round(c20 * 100, 1) if c20 is not None else None
        else:
            snap[f"{key}_chg5_pct"] = _chg(s, 5, True)
            snap[f"{key}_chg20_pct"] = _chg(s, 20, True)
    v = [x for x in _vnindex(end) if x[0].date() < end.date() or x[0] <= end]
    snap["vnindex"] = v[-1][1] if v else None
    snap["vnindex_chg5_pct"] = _chg(v, 5, True)
    snap["vnindex_chg20_pct"] = _chg(v, 20, True)
    return snap


def load_journal(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_journal(path: Path, row: dict) -> None:
    rows = [r for r in load_journal(path) if r.get("date") != row["date"]]
    rows.append({k: ("" if row.get(k) is None else row.get(k)) for k in COLS})
    rows.sort(key=lambda r: r["date"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)


def lnh_series(journal: list[dict], hist_path: Path) -> list[tuple[str, float]]:
    """Chuỗi LNH qua đêm: file lịch sử anh tải về (data/lnh_hist.csv: date,lnh_on) + sổ nhật ký."""
    d: dict[str, float] = {}
    if hist_path.exists():
        with hist_path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    d[r["date"][:10]] = float(str(r["lnh_on"]).replace(",", "."))
                except (KeyError, ValueError):
                    pass
    for r in journal:
        try:
            if r.get("lnh_on"):
                d[r["date"]] = float(r["lnh_on"])
        except ValueError:
            pass
    return sorted(d.items())


def lnh_features(series: list[tuple[str, float]], today: str) -> dict:
    s = [v for k, v in series if k <= today]
    f: dict = {"lnh_on": s[-1] if s else None, "lnh_n_obs": len(s)}
    if len(s) >= 6:
        f["lnh_on_chg5_bp"] = round((s[-1] - s[-6]) * 100, 1)
    if len(s) >= 21:
        f["lnh_on_chg20_bp"] = round((s[-1] - s[-21]) * 100, 1)
        f["abs_lnh_on_chg20_bp"] = abs(f["lnh_on_chg20_bp"])
        ma = statistics.mean(s[-21:-1])
        f["lnh_on_ma20"] = round(ma, 3)
        f["lnh_on_vs_ma20"] = round(s[-1] / ma, 3) if ma > 0 else None
        f["lnh_on_max20"] = max(s[-21:-1])
    return f


def to_features(snap: dict, lnh: dict) -> dict:
    f = {k: v for k, v in snap.items() if not k.endswith("_asof")}
    f.update(lnh)
    return f


def yesterday_str(end: datetime) -> str:
    return (end - timedelta(days=1)).date().isoformat()
