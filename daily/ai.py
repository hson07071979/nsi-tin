"""Gọi Gemini cho NSI Daily Market.

Hai cách chạy để so (anh Sơn chọn 12/10/2026), cùng một bộ FACT:
  cach_2_buoc : lượt 1 phân tích 9 tầng → lượt 2 viết lời thoại từ bản phân tích
  cach_1_luot : một lượt vừa phân tích vừa viết
Trang hiện "Bản 1 / Bản 2" xáo ngẫu nhiên; cách chạy chỉ lộ khi bấm "Xem cách chạy".
"""
from __future__ import annotations

import os
import random
import re
import time

import requests

from tin.gemini import API, Gemini, GeminiError, parse_json_loose, rank_models

from . import prompts

_PRO = re.compile(r"^gemini-(\d+(?:\.\d+)?)-pro(?:-preview(?:-[\w-]+)?)?(?:-\d{2,})?$")


def pick_models(key: str) -> list[str]:
    """Ưu tiên bản pro mới nhất (viết hay hơn) rồi tới flash. Pro hết hạn mức free → tự rơi về flash."""
    env = os.environ.get("DAILY_MODELS")
    if env:
        return [m.strip() for m in env.split(",") if m.strip()]
    have: list[str] = []
    try:
        r = requests.get(f"{API}/models", params={"key": key, "pageSize": 1000}, timeout=20)
        have = [m["name"].split("/")[-1] for m in r.json().get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", [])]
    except Exception:  # noqa: BLE001
        pass
    pros = []
    for n in have:
        m = _PRO.match(n)
        if m and not any(b in n for b in ("image", "tts", "audio", "live", "exp")):
            pros.append(((-float(m.group(1)), "preview" in n, len(n)), n))
    chosen = [n for _, n in sorted(pros)[:1]] + rank_models(have)[:3]
    return chosen or ["gemini-2.5-flash"]


class GeminiDaily(Gemini):
    """Như Gemini của nsi-tin, thêm 3 thứ cho việc viết script dài:
    - nghĩ kỹ hơn (DAILY_THINKING, mặc định medium);
    - model nào hỏng cứng (hết hạn mức ngày, 4xx) thì gạch khỏi danh sách cho cả lần chạy → không đốt thời gian thử lại;
    - ghi nhật ký từng lượt (model, giây, lỗi) để trang /daily và log Actions thấy được.
    """

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.chet: set[str] = set()
        self.nhat_ky: list[str] = []

    @staticmethod
    def _thinking(model: str) -> dict:
        lv = os.environ.get("DAILY_THINKING", "medium")
        if re.match(r"gemini-[3-9]", model):
            return {"thinkingLevel": lv}
        if model.startswith("gemini-2.5"):
            return {"thinkingBudget": {"low": 1024, "medium": 4096, "high": 8192}.get(lv, 4096)}
        return {}

    def json(self, system: str, prompt: str, *, temperature: float = 0.4, max_out: int = 8192) -> dict:  # noqa: C901
        errs: dict[str, str] = {}
        for model in [m for m in self.models if m not in self.chet]:
            gen = {"temperature": temperature, "maxOutputTokens": 65536, "responseMimeType": "application/json"}
            th = self._thinking(model)
            if th and model not in self.no_thinking_cfg:
                gen["thinkingConfig"] = th
            body = {"systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": gen}
            for attempt in range(3):
                self._wait()
                t0 = time.time()
                try:
                    r = requests.post(f"{API}/models/{model}:generateContent", params={"key": self.key},
                                      json=body, timeout=420)
                except requests.RequestException as e:
                    errs[model] = f"mạng: {str(e)[:120]}"
                    self._log(model, t0, errs[model])
                    time.sleep(5 * (attempt + 1))
                    continue
                if r.status_code == 200:
                    j = r.json()
                    u = j.get("usageMetadata", {})
                    self.tokens_in += u.get("promptTokenCount", 0)
                    self.tokens_out += u.get("candidatesTokenCount", 0)
                    try:
                        cand = j["candidates"][0]
                        text = "".join(p.get("text", "") for p in cand["content"]["parts"])
                    except (KeyError, IndexError):
                        errs[model] = "trả rỗng"
                        self._log(model, t0, errs[model])
                        break
                    out = parse_json_loose(text)
                    if out is not None:
                        self.calls += 1
                        out["_model"] = model
                        self._log(model, t0, f"ok, ra {u.get('candidatesTokenCount', 0)} token")
                        return out
                    errs[model] = f"JSON hỏng (finishReason={cand.get('finishReason')}, {len(text)} ký tự)"
                    self._log(model, t0, errs[model])
                    gen["temperature"] = 0.2
                    continue
                msg = r.text[:200].replace("\n", " ")
                errs[model] = f"HTTP {r.status_code}: {msg}"
                self._log(model, t0, errs[model])
                if r.status_code == 400 and "thinking" in r.text.lower() and "thinkingConfig" in gen:
                    self.no_thinking_cfg.add(model)
                    gen.pop("thinkingConfig", None)
                    continue
                if r.status_code == 429:
                    if "PerDay" in r.text or "per day" in r.text.lower() or "limit: 0" in r.text:
                        self.chet.add(model)          # hết hạn mức ngày / không có hạn mức free → bỏ hẳn
                        break
                    m = re.search(r'"retryDelay":\s*"(\d+)s"', r.text)
                    time.sleep(min(int(m.group(1)) + 2 if m else 20 * (attempt + 1), 75))
                    continue
                if r.status_code in (500, 502, 503, 504):
                    time.sleep(8 * (attempt + 1))
                    continue
                self.chet.add(model)                  # 400/403/404: model không dùng được với key này
                break
        raise GeminiError(" | ".join(f"{k}: {v}" for k, v in errs.items()) or "không gọi được Gemini")

    def _log(self, model: str, t0: float, msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {model} {round(time.time() - t0)}s — {msg}"
        self.nhat_ky.append(line)
        print("  [gemini]", line, flush=True)


def new_client() -> GeminiDaily:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise GeminiError("thiếu GEMINI_API_KEY")
    return GeminiDaily(key=key, rpm=int(os.environ.get("GEMINI_RPM", 8)), models=pick_models(key))


# ------------------------------------------------------------------ kiểm khuôn
def _so_chu(script: dict) -> int:
    return sum(len(str(p.get("loi_thoai", "")).split()) for p in (script or {}).get("phan", []) or [])


def check_script(script: dict) -> list[str]:
    loi = []
    if not isinstance(script, dict) or not script.get("phan"):
        return ["thiếu lời thoại"]
    n = _so_chu(script)
    if n < 1800:
        loi.append(f"lời thoại ngắn ({n} chữ, cần ~3.000 cho 20 phút)")
    tk = script.get("tiktok") or []
    if len(tk) < 3:
        loi.append(f"chỉ có {len(tk)} clip TikTok")
    # "khối ngoại mua vào/bán ra" là mô tả hợp lệ nên không cấm; cấm lời khuyên hành động và độ chắc tuyệt đối
    cam = re.compile(r"(?<!\w)(chắc chắn sẽ|100%|cài SL|giải ngân|margin|chốt lời|nên mua|nên bán|canh mua|canh bán)(?!\w)",
                     re.I)
    for p in script["phan"]:
        m = cam.search(str(p.get("loi_thoai", "")))
        if m:
            loi.append(f"phần '{p.get('ten')}' có cụm cấm: '{m.group(0)}'")
    return loi


def check_phan_tich(pt: dict) -> list[str]:
    need = ["signature", "ky_thuat_chi_so", "regime", "nganh", "luan_diem_chinh", "phien_toi"]
    return [f"phân tích thiếu '{k}'" for k in need if not (pt or {}).get(k)]


def _sua_script(g: GeminiDaily, script: dict, loi: list[str], fc: dict) -> dict:
    """Một lượt sửa khi lời thoại hụt chữ / dính cụm cấm."""
    p = (f"Lời thoại dưới đây chưa đạt: {'; '.join(loi)}.\nSửa lại cho đạt (giữ nội dung, viết dài đủ ~3.000 chữ nếu thiếu, "
         f"thay cụm cấm bằng cách nói mốc theo dõi + điểm dừng riêng). Số liệu chỉ lấy từ FACT.\n"
         f"LỜI THOẠI: {prompts._j(script)}\nFACT: {prompts._j(fc)}\nTrả JSON đúng khuôn: {prompts._j(prompts.KHUON_SCRIPT)}")
    try:
        out = g.json(prompts.LUAT, p, temperature=0.6)
        return out if out.get("phan") else script
    except GeminiError:
        return script


# ------------------------------------------------------------------ hai cách chạy
def cach_2_buoc(g: GeminiDaily, fc: dict, so: dict) -> dict:
    res: dict = {"cach": "cach_2_buoc", "loi": []}
    try:
        pt = g.json(prompts.LUAT, prompts.prompt_phan_tich(fc, so), temperature=0.4)
    except GeminiError as e:
        res["loi"].append(f"bước phân tích: {str(e)[:300]}")
        return res
    res["phan_tich"] = pt
    res["loi"] += check_phan_tich(pt)
    try:
        sc = g.json(prompts.LUAT, prompts.prompt_script_tu_phan_tich(fc, so, pt), temperature=0.75)
    except GeminiError as e:
        res["loi"].append(f"bước viết lời thoại: {str(e)[:300]}")
        return res
    loi = check_script(sc)
    if loi:
        sc = _sua_script(g, sc, loi, fc)
        loi = check_script(sc)
    res["script"] = sc
    res["loi"] += loi
    res["model"] = pt.get("_model")
    return res


def cach_1_luot(g: GeminiDaily, fc: dict, so: dict) -> dict:
    res: dict = {"cach": "cach_1_luot", "loi": []}
    try:
        out = g.json(prompts.LUAT, prompts.prompt_mot_luot(fc, so), temperature=0.65)
    except GeminiError as e:
        res["loi"].append(str(e)[:300])
        return res
    res["phan_tich"] = out.get("phan_tich") or {}
    sc = out.get("script") or {}
    res["loi"] += check_phan_tich(res["phan_tich"])
    loi = check_script(sc)
    if loi:
        sc = _sua_script(g, sc, loi, fc)
        loi = check_script(sc)
    res["script"] = sc
    res["loi"] += loi
    res["model"] = out.get("_model")
    return res


def chay_hai_ban(fc: dict, so: dict) -> tuple[list[dict], dict]:
    g = new_client()
    ket = [cach_2_buoc(g, fc, so), cach_1_luot(g, fc, so)]
    random.shuffle(ket)
    for i, b in enumerate(ket, 1):
        b["nhan"] = f"Bản {i}"
    ai = {"models": g.models, "so_luot": g.calls, "token_vao": g.tokens_in, "token_ra": g.tokens_out,
          "nhat_ky": g.nhat_ky[-30:]}
    return ket, ai


def viet_lai(fc: dict, so: dict, view: str, pt_cu: dict | None) -> tuple[dict, dict]:
    g = new_client()
    res: dict = {"loi": []}
    try:
        out = g.json(prompts.LUAT, prompts.prompt_viet_lai(fc, so, view, pt_cu), temperature=0.65)
    except GeminiError as e:
        res["loi"].append(str(e)[:300])
        return res, {"so_luot": g.calls, "nhat_ky": g.nhat_ky[-30:]}
    sc = out.get("script") or {}
    loi = check_script(sc)
    if loi:
        sc = _sua_script(g, sc, loi, fc)
        loi = check_script(sc)
    res.update({"thesis_check": out.get("thesis_check") or [], "view_sau_phan_bien": out.get("view_sau_phan_bien"),
                "script": sc, "du_bao_moi": out.get("du_bao_moi") or [], "model": out.get("_model")})
    res["loi"] += loi
    return res, {"models": g.models, "so_luot": g.calls, "token_vao": g.tokens_in, "token_ra": g.tokens_out,
                 "nhat_ky": g.nhat_ky[-30:]}
