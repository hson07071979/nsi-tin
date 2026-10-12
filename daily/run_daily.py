"""NSI Daily Market — chạy sau phiên.

python -m daily.run_daily                 chạy thật (đồng hồ ảo gọi 15:20)
python -m daily.run_daily --gac           gác: hôm nay đã có bản đạt/một phần thì thoát
python -m daily.run_daily --dry           cào + dựng FACT + dựng prompt, không gọi AI
python -m daily.run_daily --viet-lai      đọc view ở biến DAILY_VIEW (hoặc --view "...") → THESIS CHECK + viết lại

Ra: out/daily/<ngày>.json, out/daily/latest.json, out/daily/index.json, data/daily/so_du_bao.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from tin.common import ROOT, iso, now_vn, read_json, write_json

from . import facts as F
from . import forecast, prompts, sources

OUT = ROOT / "out" / "daily"


def _co_phien_hom_nay(today: str) -> bool | None:
    """dchart cập nhật nến VN-Index ngay trong phiên → hôm nay không có nến = ngày nghỉ.
    None = không hỏi được (mạng hỏng) — không kết luận."""
    b = sources.dchart("VNINDEX", days=5)
    if not b:
        return None
    return b[-1]["d"] == today


def _cho_du_lieu(today: str, phut: int, nhip: int, log: list[str]) -> None:
    """Chờ VNDirect công bố đủ phiên (chỉ số + khối ngoại). Hết giờ thì chạy với phần đã có."""
    if _co_phien_hom_nay(today) is False:
        log.append("dchart không có nến VN-Index hôm nay → ngày nghỉ, không chờ")
        return
    han = time.time() + phut * 60
    while True:
        d = sources.vnindex_days(today)
        f = sources.foreign_index(today)
        co_idx = bool(d) and d[0]["date"] == today and (d[0].get("time") or "") >= "14:45"
        co_nn = bool(f) and f[0]["date"] == today
        if co_idx and co_nn:
            log.append(f"đủ dữ liệu lúc {now_vn():%H:%M}")
            return
        if time.time() >= han:
            log.append(f"hết {phut} phút chờ: chỉ số {'có' if co_idx else 'CHƯA'}, khối ngoại {'có' if co_nn else 'CHƯA'}")
            return
        if now_vn().hour < 14 or (now_vn().hour == 14 and now_vn().minute < 45):
            log.append("chạy trước 14:45 — không chờ, dùng số đang có")
            return
        time.sleep(nhip)


def _closes(fct: dict) -> dict[str, float]:
    c = {"VNINDEX": fct["vnindex"]["dong_cua"]}
    for r in fct.get("ma", []):
        if r.get("dong_cua"):
            c[r["ma"]] = r["dong_cua"]
    return c


def _ghi(today: str, res: dict) -> None:
    write_json(OUT / f"{today}.json", res)
    # ngày nghỉ / hỏng nguồn không đè latest.json — trang vẫn mở bản của phiên gần nhất
    if res.get("trang_thai_chay") not in ("khong_phien", "loi_du_lieu") or not (OUT / "latest.json").exists():
        write_json(OUT / "latest.json", res)
    idx = [x for x in read_json(OUT / "index.json", []) if x.get("ngay") != today]
    idx.append({"ngay": today, "trang_thai_chay": res.get("trang_thai_chay"), "xong_luc": res.get("xong_luc"),
                "so_lan_viet_lai": len(res.get("viet_lai") or [])})
    write_json(OUT / "index.json", sorted(idx, key=lambda x: x["ngay"], reverse=True)[:400])


def chay(a, cfg: dict) -> int:
    t0 = time.time()
    now = now_vn()
    today = now.date().isoformat()
    log: list[str] = []
    cur = read_json(OUT / f"{today}.json", None)
    if a.gac and cur and cur.get("trang_thai_chay") in ("dat", "mot_phan"):
        print(f"GÁC: {today} đã có bản ({cur['trang_thai_chay']}) — thoát.")
        return 0
    if now.weekday() >= 5 and not a.ep:
        print("Cuối tuần — không có phiên.")
        return 0
    cd = cfg.get("cho_du_lieu", {})
    _cho_du_lieu(today, cd.get("phut_toi_da", 25), cd.get("nhip_giay", 60), log)

    print("1) Dựng FACT")
    fct = F.collect(now.date(), cfg, log)
    if fct.get("loi_nguon"):
        res = {"ngay": today, "trang_thai_chay": "loi_du_lieu", "xong_luc": iso(now_vn()), "nhat_ky": log[-40:],
               "ghi_chu": "Không đọc được VN-Index từ VNDirect (mạng/nguồn hỏng). Lần gác sau sẽ thử lại."}
        _ghi(today, res)
        print(res["ghi_chu"])
        return 2
    if fct.get("khong_phien"):
        res = {"ngay": today, "trang_thai_chay": "khong_phien", "xong_luc": iso(now_vn()),
               "ghi_chu": f"Không có phiên hôm nay (phiên gần nhất {fct.get('phien_gan_nhat')}) — nghỉ lễ hoặc VNDirect chưa có số."}
        _ghi(today, res)
        print(res["ghi_chu"])
        return 0

    print("2) Chấm sổ dự báo")
    so_rows = forecast.load()
    vua_cham = forecast.check(so_rows, today, _closes(fct))
    so = forecast.summary(so_rows, today)
    fc = prompts.compact(fct)

    res = {
        "ngay": today, "bat_dau_luc": iso(now), "fc": fc, "nhat_ky": log[-40:],
        "so_du_bao": so, "ban": [], "viet_lai": (cur or {}).get("viet_lai", []) if cur and cur.get("ngay") == today else [],
        "trang_thai_chay": "dang_chay",
    }
    if a.dry:
        res["trang_thai_chay"] = "dry"
        res["kich_thuoc_prompt_ky_tu"] = {"phan_tich": len(prompts.prompt_phan_tich(fc, so)),
                                          "mot_luot": len(prompts.prompt_mot_luot(fc, so))}
    else:
        from tin.gemini import GeminiError  # noqa: PLC0415
        from . import ai  # noqa: PLC0415
        print("3) Gemini: hai cách chạy")
        try:
            ban, meta = ai.chay_hai_ban(fc, so, cfg.get("ai_phut_toi_da", 32), cfg.get("cach_chay"))
            res["ban"], res["ai"] = ban, meta
            # chạy lại trong ngày (gác/bấm tay) thì thay dòng sổ của lần trước, không cộng dồn
            so_rows[:] = [r for r in so_rows if not (r.get("ngay_ghi") == today and r.get("ban") in ("cach_2_buoc", "cach_1_luot"))]
            for b in ban:
                forecast.add(so_rows, today, (b.get("phan_tich") or {}).get("du_bao_moi"), b["cach"])
            ok = [b for b in ban if (b.get("script") or {}).get("phan")]
            sach = [b for b in ok if not b.get("loi")]
            res["trang_thai_chay"] = "dat" if sach and len(sach) == len(ban) else "mot_phan" if ok else "loi_ai"
        except GeminiError as e:
            res["ai"] = {"loi": str(e)[:300]}
            res["trang_thai_chay"] = "loi_ai"
        except Exception as e:  # noqa: BLE001 — lỗi lạ vẫn phải ghi ra trang, không im lặng
            res["ai"] = {"loi": f"{type(e).__name__}: {str(e)[:300]}"}
            res["trang_thai_chay"] = "loi_ai"
    # chạy lại trong ngày mà AI hỏng thì GIỮ bản tốt đã có, chỉ ghi chú lỗi của lần chạy lại
    if res["trang_thai_chay"] == "loi_ai" and cur and cur.get("ngay") == today and \
            any((b.get("script") or {}).get("phan") for b in cur.get("ban") or []):
        loi_moi = res.get("ai")
        res["ban"], res["trang_thai_chay"] = cur["ban"], cur.get("trang_thai_chay", "mot_phan")
        res["ai"] = cur.get("ai")
        res["lan_chay_lai_loi"] = {"luc": iso(now_vn()), "ai": loi_moi}
    forecast.save(so_rows)
    res["so_du_bao"]["vua_cham_hom_nay"] = vua_cham or res["so_du_bao"]["vua_cham_hom_nay"]
    res["xong_luc"] = iso(now_vn())
    res["chay_giay"] = round(time.time() - t0)
    _ghi(today, res)
    print(json.dumps({k: res.get(k) for k in ("trang_thai_chay", "xong_luc", "chay_giay")}, ensure_ascii=False))
    return 0 if res["trang_thai_chay"] in ("dat", "mot_phan", "dry", "khong_phien") else 2


def viet_lai(a, cfg: dict) -> int:
    view = (a.view or os.environ.get("DAILY_VIEW") or "").strip()
    if not view:
        print("Thiếu view (DAILY_VIEW rỗng).")
        return 2
    ngay = (a.ngay or os.environ.get("DAILY_NGAY") or "").strip()
    cur = read_json(OUT / f"{ngay}.json", None) if ngay else read_json(OUT / "latest.json", None)
    if not cur or not cur.get("fc"):
        print("Chưa có bản tự động để viết lại — chạy bản chiều trước.")
        return 2
    today = cur["ngay"]
    from . import ai  # noqa: PLC0415
    pt_cu = next((b.get("phan_tich") for b in cur.get("ban", []) if b.get("cach") == "cach_2_buoc"), None)
    kq, meta = ai.viet_lai(cur["fc"], cur.get("so_du_bao") or {}, view, pt_cu)
    so_rows = forecast.load()
    forecast.add(so_rows, today, kq.get("du_bao_moi"), "viet_lai")
    forecast.save(so_rows)
    cur.setdefault("viet_lai", []).append({"luc": iso(now_vn()), "view": view[:2500], "ket_qua": kq, "ai": meta})
    cur["viet_lai"] = cur["viet_lai"][-10:]
    _ghi(today, cur) if today == now_vn().date().isoformat() else write_json(OUT / f"{today}.json", cur)
    print(json.dumps({"viet_lai": "xong", "loi": kq.get("loi")}, ensure_ascii=False))
    return 0 if (kq.get("script") or {}).get("phan") else 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gac", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--ep", action="store_true", help="chạy cả cuối tuần (để thử)")
    ap.add_argument("--viet-lai", action="store_true")
    ap.add_argument("--view")
    ap.add_argument("--ngay")
    a = ap.parse_args(argv)
    cfg = read_json(ROOT / "config" / "daily.json", {})
    if a.viet_lai:
        return viet_lai(a, cfg)
    return chay(a, cfg)


if __name__ == "__main__":
    sys.exit(main())
