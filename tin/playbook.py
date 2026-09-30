"""Chấm sổ luật vĩ mô MỀM. Kết quả là cờ + gợi ý, KHÔNG BAO GIỜ là lệnh chặn."""
from __future__ import annotations

OPS = {
    ">=": lambda a, b: a >= b, ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b, "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
}


def _cond(feat: dict, c: list) -> bool | None:
    field, op, val = c
    v = feat.get(field)
    if v is None or v == "":
        return None  # thiếu dữ liệu
    return OPS[op](float(v), float(val))


def eval_rule(rule: dict, feat: dict) -> str:
    """'bat' | 'tat' | 'thieu_du_lieu'."""
    khi = rule["khi"]
    if "all" in khi:
        rs = [_cond(feat, c) for c in khi["all"]]
        if any(r is False for r in rs):
            return "tat"
        return "bat" if all(r is True for r in rs) else "thieu_du_lieu"
    rs = [_cond(feat, c) for c in khi["any"]]
    if any(r is True for r in rs):
        return "bat"
    return "tat" if all(r is False for r in rs) else "thieu_du_lieu"


def evaluate(playbook: dict, feat: dict) -> dict:
    muc = playbook["muc"]
    flags = []
    for r in playbook["rules"]:
        st = eval_rule(r, feat)
        flags.append({"id": r["id"], "ten": r["ten"], "trang_thai": st, "muc": r["muc"],
                      "muc_ten": muc[r["muc"]]["ten"], "doc": r["doc"],
                      "vi_mo_to_vi_mo": r["vi_mo_to_vi_mo"], "goi_y_he_thong": r["goi_y_he_thong"],
                      "kiem_chung": r.get("kiem_chung", "giả thuyết — chưa kiểm bằng backtest")})
    bat = [f for f in flags if f["trang_thai"] == "bat"]
    top = max((muc[f["muc"]]["thu_tu"] for f in bat), default=0)
    ten_top = next((muc[k]["ten"] for k, v in muc.items() if v["thu_tu"] == top and any(f["muc"] == k for f in bat)),
                   "Bình thường")
    # cặp cờ nguy hiểm theo framework: tỷ giá căng + LNH sốc → NHNN mất room nới
    cap = {f["id"] for f in bat} >= {"TY_GIA_CANG", "LNH_SOC_NGAN"}
    return {"flags": flags, "so_co_bat": len(bat), "muc_cao_nhat": ten_top,
            "cap_ty_gia_lnh": cap,
            "loi_nhac": "Cờ mềm: gợi ý soi tay, không chặn lệnh, không hạ cỡ probe."}
