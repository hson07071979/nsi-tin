"""Cào tab TIN WEB: RSS + trang danh sách (fisc.vn) + bảng lãi suất LNH của NHNN."""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

from .common import VN, clean_text, http_get, khong_dau, now_vn, parse_iso

# Từ khoá để ưu tiên / lọc tin khi quá nhiều (không dấu).
KW_MANH = [
    "lai suat", "lien ngan hang", "ty gia", "nhnn", "ngan hang nha nuoc", "omo", "tin phieu",
    "fed", "fomc", "lam phat", "cpi", "gdp", "tin dung", "trai phieu", "loi suat", "usd",
    "khoi ngoai", "ban rong", "mua rong", "margin", "nang hang", "vn-index", "vnindex",
    "thue quan", "xuat khau", "fdi", "dau tu cong", "gia dau", "gia vang", "chung khoan",
    "interest rate", "inflation", "treasury", "yield", "dollar", "tariff", "oil", "recession",
    "loi nhuan", "ket qua kinh doanh", "co tuc", "phat hanh", "tang von", "thoai von", "ipo",
]
KW_BO = ["xo so", "bong da", "showbiz", "hoa hau", "tu vi", "phong thuy", "the thao"]


def _id(url: str, title: str) -> str:
    return hashlib.sha1((url or title).encode("utf-8")).hexdigest()[:12]


def _date(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
        return d if d.tzinfo else d.replace(tzinfo=VN)
    except (TypeError, ValueError):
        pass
    return parse_iso(s.replace("Z", "+00:00"))


def diem_lien_quan(text: str) -> int:
    t = khong_dau(text)
    if any(k in t for k in KW_BO):
        return -5
    return sum(2 if k in ("lai suat", "ty gia", "lien ngan hang", "nhnn", "fed") else 1
               for k in KW_MANH if k in t)


def parse_rss(xml_text: str) -> list[dict]:
    """RSS 2.0 hoặc Atom → [{title, url, summary, published}]. Không phụ thuộc feedparser."""
    xml_text = re.sub(r"^[^<]+", "", xml_text or "")
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except ET.ParseError:
        # một số báo VN để ký tự điều khiển lạ trong CDATA
        xml_text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", xml_text)
        try:
            root = ET.fromstring(xml_text.encode("utf-8"))
        except ET.ParseError:
            return []
    out = []
    ns_atom = "{http://www.w3.org/2005/Atom}"
    items = root.iter("item")
    got = False
    for it in items:
        got = True
        out.append({
            "title": clean_text(it.findtext("title")),
            "url": (it.findtext("link") or "").strip(),
            "summary": clean_text(it.findtext("description"), 500),
            "published": _date(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date")),
        })
    if not got:
        for it in root.iter(f"{ns_atom}entry"):
            link = it.find(f"{ns_atom}link")
            out.append({
                "title": clean_text(it.findtext(f"{ns_atom}title")),
                "url": link.get("href", "") if link is not None else "",
                "summary": clean_text(it.findtext(f"{ns_atom}summary") or it.findtext(f"{ns_atom}content"), 500),
                "published": _date(it.findtext(f"{ns_atom}published") or it.findtext(f"{ns_atom}updated")),
            })
    return [o for o in out if o["title"]]


_META = re.compile(r'<meta[^>]+(?:property|name)=["\']([^"\']+)["\'][^>]+content=["\']([^"\']*)["\']', re.I)


def parse_article(html_text: str) -> dict:
    meta = {k.lower(): v for k, v in _META.findall(html_text or "")}
    title = meta.get("og:title") or clean_text((re.search(r"<title>(.*?)</title>", html_text, re.S | re.I) or [None, ""])[1])
    # KHÔNG dùng og:updated_time: nhiều trang để giờ render trang → bài cũ thành "vừa đăng"
    pub = _date(meta.get("article:published_time") or meta.get("pubdate") or meta.get("datepublished"))
    # fisc.vn (và vài web khác) để published_time = giờ render trang → không tin mốc nằm trong 15 phút gần nhất
    if pub and (now_vn() - pub).total_seconds() < 900:
        pub = None
    if not pub:  # fisc.vn: ngày nằm trong đường dẫn ảnh upload/YYYY/MM/DD
        m = re.search(r"/upload/(20\d\d)/(\d\d)/(\d\d)/", meta.get("og:image", ""))
        if m:
            pub = datetime(int(m[1]), int(m[2]), int(m[3]), 8, 0, tzinfo=VN)
    if not pub:  # JSON-LD để cuối: nhiều trang (fisc) để ngày của cả website, không phải của bài
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html_text or "")
        if m:
            pub = _date(m.group(1))
    body = ""
    m = re.search(r"<article[^>]*>(.*?)</article>", html_text, re.S | re.I)
    if m:
        body = clean_text(m.group(1), 3000)
    else:
        ps = re.findall(r"<p[^>]*>(.*?)</p>", html_text, re.S | re.I)
        body = clean_text(" ".join(ps), 3000)
    return {"title": clean_text(title), "summary": clean_text(meta.get("og:description"), 500),
            "body": body, "published": pub}


def parse_sbv_lnh(html_text: str) -> dict | None:
    """Bảng 'Lãi suất bình quân liên ngân hàng' NHNN. Trả {'qua_dem': x, '1_tuan': y, 'ngay': 'dd/mm/yyyy'}.
    Làm theo kiểu dò chữ vì trang NHNN hay đổi khuôn — sai thì trả None, không đoán."""
    t = clean_text(html_text)
    tk = khong_dau(t)
    out = {}
    for key, pat in (("qua_dem", r"qua dem\s+([0-9]+[.,][0-9]+)"), ("1_tuan", r"1 tuan\s+([0-9]+[.,][0-9]+)"),
                     ("2_tuan", r"2 tuan\s+([0-9]+[.,][0-9]+)"), ("1_thang", r"1 thang\s+([0-9]+[.,][0-9]+)")):
        m = re.search(pat, tk)
        if m:
            v = float(m.group(1).replace(",", "."))
            if 0 < v < 30:
                out[key] = v
    m = re.search(r"ngay ap dung\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})", tk) or re.search(r"(\d{1,2}/\d{1,2}/20\d\d)", tk)
    if m:
        out["ngay"] = m.group(1)
    return out if "qua_dem" in out else None


def fetch_web(cfg: dict, start: datetime, end: datetime, seen: set[str]) -> tuple[list[dict], dict, list[dict]]:
    """Trả (items, lnh, nhat_ky_nguon)."""
    items, log, lnh = [], [], None
    for src in cfg["web"]:
        n_ok = 0
        err = None
        try:
            if src["type"] == "rss":
                r = http_get(src["url"])
                if r is None:
                    err = "không tải được"
                else:
                    r.encoding = r.encoding or "utf-8"
                    for e in parse_rss(r.text):
                        pub = e["published"]
                        if pub and not (start < pub <= end):
                            continue
                        iid = _id(e["url"], e["title"])
                        if not pub and iid in seen:
                            continue
                        score = diem_lien_quan(e["title"] + " " + e["summary"])
                        if src.get("keywords_required") and score <= 0:
                            continue
                        items.append({"id": "w" + iid, "src": src["id"], "src_name": src["name"],
                                      "group": src["group"], "title": e["title"], "url": e["url"],
                                      "summary": e["summary"], "published": pub.astimezone(VN).isoformat(timespec="minutes") if pub else None,
                                      "score": score})
                        n_ok += 1
            elif src["type"] == "html_list":
                r = http_get(src["url"])
                if r is None:
                    err = "không tải được"
                else:
                    links = list(dict.fromkeys(re.findall(src["link_regex"], r.text)))
                    # bài mới nhất thường có mã p lớn nhất
                    links.sort(key=lambda u: int((re.search(r"p(\d+)\.html", u) or [0, 0])[1]), reverse=True)
                    for u in links[: src.get("max_articles", 8)]:
                        iid = _id(u, "")
                        if iid in seen:
                            continue
                        a = http_get(u)
                        if a is None:
                            continue
                        art = parse_article(a.text)
                        if art["published"] is None or art["published"] < start - timedelta(hours=24):
                            continue  # không rõ ngày hoặc bài cũ → bỏ (tránh lần chạy đầu dội cả kho bài cũ)
                        items.append({"id": "w" + iid, "src": src["id"], "src_name": src["name"],
                                      "group": src["group"], "title": art["title"], "url": u,
                                      "summary": art["summary"], "body": art["body"] if src.get("fetch_body") else "",
                                      "published": art["published"].isoformat(timespec="minutes") if art["published"] else None,
                                      "score": diem_lien_quan(art["title"] + " " + art["body"][:800]) + 3})
                        n_ok += 1
            elif src["type"] == "sbv_lnh":
                r = http_get(src["url"], timeout=30, tries=2)
                if r is None:
                    err = "NHNN không phản hồi (hay chặn IP nước ngoài) — lấy số LNH từ tin báo"
                else:
                    lnh = parse_sbv_lnh(r.text)
                    if lnh:
                        lnh["nguon"] = "sbv"
                        n_ok = 1
                    else:
                        err = "đọc được trang nhưng không thấy bảng"
        except Exception as e:  # một nguồn hỏng không được làm sập cả buổi
            err = f"lỗi {type(e).__name__}: {str(e)[:120]}"
        log.append({"id": src["id"], "name": src["name"], "group": src["group"], "n": n_ok, "err": err})
        print(f"  web {src['id']:<10} {n_ok:>3} tin" + (f"  ⚠ {err}" if err else ""))
    # khử trùng theo tiêu đề không dấu (cùng tin nhiều báo đăng lại)
    uniq, keys = [], set()
    for it in sorted(items, key=lambda x: -x["score"]):
        k = khong_dau(it["title"])[:70]
        if k in keys:
            continue
        keys.add(k)
        uniq.append(it)
    return uniq, lnh, log


# ---------- thân bài: chỉ lấy cho các tin nằm trong TOP chủ đề (không lấy cả 140 tin) ----------
def extract_body(html_text: str, limit: int = 4000) -> str:
    """Lấy khối chữ dày nhất trang (bài báo), bỏ menu/quảng cáo. Không đúng 100% nhưng đủ để AI hiểu 'tin đó là gì'."""
    try:
        from bs4 import BeautifulSoup  # noqa: PLC0415
    except ImportError:
        return clean_text(" ".join(re.findall(r"<p[^>]*>(.*?)</p>", html_text or "", re.S | re.I)), limit)
    soup = BeautifulSoup(html_text or "", "lxml")
    for t in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript", "figure", "iframe"]):
        t.decompose()
    best, best_sc = None, 0
    for el in soup.find_all(["article", "div", "section"]):
        txt = sum(len(p.get_text(" ", strip=True)) for p in el.find_all("p") if len(p.get_text(strip=True)) > 40)
        sc = txt - 30 * len(el.find_all("a"))
        if sc > best_sc:
            best, best_sc = el, sc
    if best is None:
        return ""
    ps = [p.get_text(" ", strip=True) for p in best.find_all("p")]
    ps = [p for p in ps if len(p) > 40 and not re.search(r"(bản quyền|ghi rõ nguồn|giấy phép|chịu trách nhiệm|copyright)", p, re.I)]
    return clean_text(" ".join(ps), limit)


def fetch_bodies(items: list[dict], ids: list[str], max_n: int = 40) -> int:
    """Gắn it['body'] cho các tin web thuộc TOP chủ đề. Trả số bài lấy được."""
    by = {it["id"]: it for it in items}
    n = 0
    for i in ids[:max_n]:
        it = by.get(i)
        if not it or it.get("body") or not it.get("url", "").startswith("http"):
            continue
        r = http_get(it["url"], tries=2, timeout=20)
        if r is None:
            continue
        r.encoding = r.apparent_encoding if not r.encoding or r.encoding.lower() == "iso-8859-1" else r.encoding
        b = extract_body(r.text)
        if len(b) > 200:
            it["body"] = b
            n += 1
    return n
