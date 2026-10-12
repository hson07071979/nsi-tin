"""Nguồn dữ liệu cho NSI Daily Market.

- VNDirect finfo (không cần token): VN-Index có sẵn breadth + khớp/thỏa thuận, giá từng mã, khối ngoại,
  tự doanh, chỉ số định giá (P/E, P/B), số cổ phiếu lưu hành.
- VNDirect dchart: nến lịch sử (đã điều chỉnh) — chỉ gọi khi kho nến chưa có hoặc phải dựng lại.
- Yahoo Finance: liên thị trường (dầu, DXY, lợi suất Mỹ, chứng khoán Mỹ/châu Á, hàng hóa).

Mọi hàm hỏng thì trả rỗng/None, không ném lỗi: một nguồn hỏng không được làm sập cả buổi.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

from tin.common import VN, http_get

FINFO = "https://api-finfo.vndirect.com.vn/v4"
DCHART = "https://dchart-api.vndirect.com.vn/dchart/history"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/"

TY = 1e9  # đồng → tỷ đồng


def _finfo(path: str, params: dict, tries: int = 3) -> list[dict]:
    r = http_get(f"{FINFO}/{path}", params=params, tries=tries, timeout=30)
    if r is None:
        return []
    try:
        d = r.json().get("data")
        return d if isinstance(d, list) else []
    except ValueError:
        return []


# ---------------------------------------------------------------- VN-Index
def vnindex_days(since: str, code: str = "VNINDEX") -> list[dict]:
    """Các phiên của chỉ số từ ngày `since`, mới nhất trước. Mỗi phiên có breadth, khớp, thỏa thuận."""
    rows = _finfo("vnmarket_prices", {"q": f"code:{code}~date:gte:{since}", "size": 400, "sort": "date:desc"})
    out = []
    for x in rows:
        out.append({
            "date": x.get("date"), "time": x.get("time"),
            "open": x.get("open"), "high": x.get("high"), "low": x.get("low"), "close": x.get("close"),
            "change": x.get("change"), "pct": x.get("pctChange"),
            "kl": x.get("accumulatedVol"),
            "gt_tong": _ty(x.get("accumulatedVal")), "gt_khop": _ty(x.get("nmValue")), "gt_thoa_thuan": _ty(x.get("ptValue")),
            "kl_khop": x.get("nmVolume"),
            "tang": _int(x.get("advances")), "giam": _int(x.get("declines")), "dung": _int(x.get("noChange")),
            "tran": _int(x.get("ceilingStocks")), "san": _int(x.get("floorStocks")),
        })
    return out


# ---------------------------------------------------------------- giá từng mã
def stock_prices_on(day: str, floors: tuple[str, ...] = ("HOSE", "HNX")) -> dict[str, dict]:
    """Giá phiên `day` của mọi cổ phiếu trên các sàn. Khóa = mã."""
    out: dict[str, dict] = {}
    for fl in floors:
        rows = _finfo("stock_prices", {"q": f"floor:{fl}~date:{day}~type:STOCK", "size": 2000})
        for x in rows:
            c = x.get("code")
            if not c:
                continue
            out[c] = {
                "san": fl, "date": x.get("date"), "time": x.get("time"),
                "tham_chieu": x.get("basicPrice"), "tran": x.get("ceilingPrice"), "san_gia": x.get("floorPrice"),
                "open": x.get("adOpen"), "high": x.get("adHigh"), "low": x.get("adLow"), "close": x.get("adClose"),
                "close_raw": x.get("close"), "pct": x.get("pctChange"),
                "kl": x.get("nmVolume"), "gt_khop": _ty(x.get("nmValue")), "gt_thoa_thuan": _ty(x.get("ptValue")),
            }
    return out


# ---------------------------------------------------------------- khối ngoại / tự doanh
def foreign_index(since: str, code: str = "VNINDEX") -> list[dict]:
    rows = _finfo("foreigns", {"q": f"code:{code}~tradingDate:gte:{since}", "size": 400, "sort": "tradingDate:desc"})
    return [{"date": x.get("tradingDate"), "mua": _ty(x.get("buyVal")), "ban": _ty(x.get("sellVal")),
             "rong": _ty(x.get("netVal"))} for x in rows]


def foreign_stocks(day: str) -> dict[str, float]:
    """Khối ngoại ròng (tỷ) từng mã HOSE+HNX trong phiên `day`."""
    out: dict[str, float] = {}
    for fl in ("HOSE", "HNX"):
        for x in _finfo("foreigns", {"q": f"tradingDate:{day}~type:STOCK~floor:{fl}", "size": 2000,
                                     "fields": "code,netVal"}):
            if x.get("code") and x.get("netVal") is not None:
                out[x["code"]] = round(x["netVal"] / TY, 2)
    return out


def prop_index(n: int = 25) -> list[dict]:
    rows = _finfo("proprietary_trading", {"q": "code:VNINDEX", "sort": "date:desc", "size": n})
    return [{"date": x.get("date"), "mua": _ty(x.get("buyingVal")), "ban": _ty(x.get("sellingVal")),
             "rong": _ty(x.get("netVal"))} for x in rows]


def prop_stocks(day: str) -> dict[str, float]:
    rows = _finfo("proprietary_trading", {"q": f"date:{day}~type:STOCK", "size": 500})
    return {x["code"]: round(x["netVal"] / TY, 2) for x in rows if x.get("code") and x.get("netVal") is not None}


# ---------------------------------------------------------------- định giá / số cổ phiếu
def ratios(codes: list[str]) -> dict[str, dict]:
    """P/E, P/B, số CP lưu hành, cao/thấp 52 tuần. Gọi theo lô 40 mã."""
    item = {"51006": "pe", "51012": "pb", "51004": "cp_luu_hanh", "51001": "cao_52t", "51002": "thap_52t"}
    out: dict[str, dict] = {}

    def lo(chunk):
        return _finfo("ratios/latest", {"filter": f"itemCode:{','.join(item)}", "where": f"code:{','.join(chunk)}",
                                        "order": "reportDate", "fields": "code,itemCode,value,reportDate"}, tries=2)

    chunks = [codes[i:i + 40] for i in range(0, len(codes), 40)]
    with ThreadPoolExecutor(4) as ex:
        for rows in ex.map(lo, chunks):
            for x in rows:
                k = item.get(str(x.get("itemCode")))
                if k and x.get("code") and x.get("value") is not None:
                    out.setdefault(x["code"], {})[k] = x["value"]
    return out


# ---------------------------------------------------------------- nến lịch sử
def dchart(sym: str, days: int = 450, end: datetime | None = None) -> list[dict]:
    end = end or datetime.now(VN)
    to = int(end.timestamp()) + 86400
    r = http_get(DCHART, params={"resolution": "D", "symbol": sym, "from": to - days * 86400 * 7 // 5, "to": to},
                 tries=3, timeout=30)
    if r is None:
        return []
    try:
        j = r.json()
        if j.get("s") != "ok":
            return []
        out = []
        for t, o, h, lo_, c, v in zip(j["t"], j["o"], j["h"], j["l"], j["c"], j["v"]):
            out.append({"d": datetime.fromtimestamp(t, VN).date().isoformat(),
                        "o": o, "h": h, "l": lo_, "c": c, "v": v})
        return out[-days:]
    except (KeyError, TypeError, ValueError):
        return []


# ---------------------------------------------------------------- liên thị trường
def yahoo(sym: str, rng: str = "3mo") -> dict | None:
    r = http_get(YAHOO + sym, params={"range": rng, "interval": "1d"}, tries=2, timeout=20)
    if r is None:
        return None
    try:
        res = r.json()["chart"]["result"][0]
        meta = res.get("meta", {})
        ts, cl = res["timestamp"], res["indicators"]["quote"][0]["close"]
        s = [(datetime.fromtimestamp(t, VN), float(c)) for t, c in zip(ts, cl) if c is not None]
        if not s:
            return None
        return {"series": s, "gia": meta.get("regularMarketPrice") or s[-1][1],
                "luc": datetime.fromtimestamp(meta["regularMarketTime"], VN).isoformat(timespec="minutes")
                if meta.get("regularMarketTime") else s[-1][0].isoformat(timespec="minutes")}
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def world(items: list[dict]) -> dict[str, dict]:
    def one(it):
        y = yahoo(it["sym"])
        if not y:
            return it["key"], {"ten": it["ten"], "thieu": True}
        s = y["series"]
        last = y["gia"]

        def chg(n):
            if len(s) <= n:
                return None
            a = s[-1 - n][1]
            return round((last / a - 1) * 100, 2) if a else None

        prev = s[-2][1] if len(s) >= 2 else None
        hi20 = max(v for _, v in s[-20:])
        lo20 = min(v for _, v in s[-20:])
        d = {"ten": it["ten"], "don_vi": it["don_vi"], "gia": round(last, 4), "luc_vn": y["luc"],
             "pct_1p": round((last / prev - 1) * 100, 2) if prev else None,
             "pct_5p": chg(5), "pct_20p": chg(20), "cao_20p": round(hi20, 4), "thap_20p": round(lo20, 4),
             "cao_3t": round(max(v for _, v in s), 4), "thap_3t": round(min(v for _, v in s), 4)}
        if it["key"] == "us10y" and prev:
            d["doi_bp_1p"] = round((last - prev) * 100, 1)
            d["doi_bp_20p"] = round((last - s[-21][1]) * 100, 1) if len(s) > 20 else None
        return it["key"], d

    with ThreadPoolExecutor(6) as ex:
        return dict(ex.map(one, items))


# ---------------------------------------------------------------- tiện ích
def _ty(v):
    return None if v is None else round(v / TY, 1)


def _int(v):
    return None if v is None else int(v)


def month_start(d: date) -> str:
    return d.replace(day=1).isoformat()


def days_ago(d: date, n: int) -> str:
    return (d - timedelta(days=n)).isoformat()
