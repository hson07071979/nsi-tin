"""Client Gemini REST (không cần SDK).

Bản 2 (30-09 tối) sau lần chạy thật đầu tiên: model cố định trong danh sách bị Google khai tử
("gemini-2.5-flash-lite is no longer available to new users") và lượt lọc tin thất bại không rõ lý do.
- Tự dò model: lấy MỌI model gemini-*-flash* key đang dùng được, xếp bản mới nhất lên đầu.
- Hạn ra 65k token + giảm 'thinking' để JSON không bị cắt cụt vì model nghĩ hết ngân sách.
- Ghi lỗi của TỪNG model vào thông báo (hiện trên trang) để lần sau biết ngay hỏng ở đâu.
"""
from __future__ import annotations

import json
import os
import re
import time

import requests

API = "https://generativelanguage.googleapis.com/v1beta"
_FLASH = re.compile(r"^gemini-(\d+(?:\.\d+)?)-flash(-lite)?(?:-preview(?:-[\w-]+)?)?(?:-\d{2,})?$")
_BO = ("image", "tts", "audio", "live", "embedding", "exp", "thinking")


class GeminiError(RuntimeError):
    pass


def rank_models(names: list[str]) -> list[str]:
    """Chỉ giữ gemini-X-flash[-lite][-preview…]; xếp: bản số lớn trước, flash trước lite, bản chính thức trước preview."""
    ok = []
    for n in names:
        if any(b in n for b in _BO):
            continue
        m = _FLASH.match(n)
        if not m:
            continue
        ver = float(m.group(1))
        lite = bool(m.group(2))
        preview = "preview" in n
        ok.append(((-ver, lite, preview, len(n)), n))
    return [n for _, n in sorted(ok)]


class Gemini:
    def __init__(self, key: str | None = None, rpm: int | None = None, models: list[str] | None = None):
        self.key = key or os.environ.get("GEMINI_API_KEY", "")
        if not self.key:
            raise GeminiError("thiếu GEMINI_API_KEY")
        self.gap = 60.0 / float(rpm or os.environ.get("GEMINI_RPM", 8))
        self._last = 0.0
        self.calls = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.no_thinking_cfg: set[str] = set()
        env_models = os.environ.get("GEMINI_MODELS")
        self.models = models or (env_models.split(",") if env_models else self._pick())

    def _pick(self) -> list[str]:
        have: list[str] = []
        try:
            url, params = f"{API}/models", {"key": self.key, "pageSize": 1000}
            r = requests.get(url, params=params, timeout=20)
            have = [m["name"].split("/")[-1] for m in r.json().get("models", [])
                    if "generateContent" in m.get("supportedGenerationMethods", [])]
        except Exception:  # noqa: BLE001
            pass
        chosen = rank_models(have)[:7] or ["gemini-2.5-flash"]   # 12/10: 4→7 để còn model lite dự phòng
        # 12/10/2026: để dành model tốt nhất cho NSI Daily Market buổi chiều (viết script cần nó nhất).
        # Bản tin sáng chạy bằng các model kế tiếp; model tốt nhất chỉ dùng khi các model kia hỏng hết.
        if os.environ.get("GEMINI_DE_DANH_CHIEU") == "1" and len(chosen) > 1:
            chosen = chosen[1:] + chosen[:1]
        print(f"  [gemini] model: {chosen}")
        return chosen

    def _wait(self):
        dt = time.time() - self._last
        if dt < self.gap:
            time.sleep(self.gap - dt)
        self._last = time.time()

    @staticmethod
    def _thinking(model: str) -> dict:
        # Gemini 3.x dùng thinkingLevel; 2.5 dùng thinkingBudget. Để thấp: việc này là tóm tắt/phân tích có khuôn.
        if re.match(r"gemini-[3-9]", model):
            return {"thinkingLevel": "low"}
        if model.startswith("gemini-2.5"):
            return {"thinkingBudget": 1024}
        return {}

    def json(self, system: str, prompt: str, *, temperature: float = 0.4, max_out: int = 8192) -> dict:
        errs: dict[str, str] = {}
        for model in self.models:
            gen = {"temperature": temperature, "maxOutputTokens": 65536, "responseMimeType": "application/json"}
            th = self._thinking(model)
            if th and model not in self.no_thinking_cfg:
                gen["thinkingConfig"] = th
            body = {"systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": gen}
            for attempt in range(4):
                self._wait()
                try:
                    r = requests.post(f"{API}/models/{model}:generateContent", params={"key": self.key},
                                      json=body, timeout=300)
                except requests.RequestException as e:
                    errs[model] = f"mạng: {str(e)[:120]}"
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
                        errs[model] = f"trả rỗng ({(j.get('promptFeedback') or {}).get('blockReason') or j.get('candidates', [{}])[0].get('finishReason')})"
                        break
                    out = parse_json_loose(text)
                    if out is not None:
                        self.calls += 1
                        out.setdefault("_model", model)
                        return out
                    errs[model] = f"JSON hỏng (finishReason={cand.get('finishReason')}, {len(text)} ký tự)"
                    gen["temperature"] = 0.2
                    continue
                msg = r.text[:220].replace("\n", " ")
                errs[model] = f"HTTP {r.status_code}: {msg}"
                if r.status_code == 400 and "thinking" in r.text.lower() and "thinkingConfig" in gen:
                    self.no_thinking_cfg.add(model)       # model không nhận tham số thinking → bỏ đi, thử lại
                    gen.pop("thinkingConfig", None)
                    continue
                if r.status_code == 429:
                    if "PerDay" in r.text or "per day" in r.text.lower():
                        break  # hết hạn mức ngày của model này → sang model sau
                    m = re.search(r'"retryDelay":\s*"(\d+)s"', r.text)
                    time.sleep(min(int(m.group(1)) + 2 if m else 20 * (attempt + 1), 90))
                    continue
                if r.status_code in (500, 502, 503, 504):
                    time.sleep(8 * (attempt + 1))
                    continue
                break  # 400/403/404 → model này không dùng được
        raise GeminiError(" | ".join(f"{k}: {v}" for k, v in errs.items()) or "không gọi được Gemini")


def parse_json_loose(text: str):
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        v = json.loads(text)
        return v if isinstance(v, dict) else {"items": v}
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None
