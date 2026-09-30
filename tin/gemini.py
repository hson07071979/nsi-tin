"""Client Gemini REST (không cần SDK). Tự chọn model flash tốt nhất đang có, giãn nhịp theo hạn mức free tier,
thử lại khi 429/5xx, ép trả JSON."""
from __future__ import annotations

import json
import os
import re
import time

import requests

API = "https://generativelanguage.googleapis.com/v1beta"
# Ưu tiên từ trên xuống; model nào key không có quyền thì tự bỏ qua.
PREF = ["gemini-3-flash", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-flash-preview",
        "gemini-2.0-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash-lite"]


class GeminiError(RuntimeError):
    pass


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
        env_models = os.environ.get("GEMINI_MODELS")
        self.models = models or (env_models.split(",") if env_models else self._pick())

    def _pick(self) -> list[str]:
        try:
            r = requests.get(f"{API}/models", params={"key": self.key, "pageSize": 200}, timeout=20)
            have = {m["name"].split("/")[-1] for m in r.json().get("models", [])
                    if "generateContent" in m.get("supportedGenerationMethods", [])}
        except Exception:  # noqa: BLE001
            have = set()
        chosen = [m for m in PREF if m in have] or ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
        print(f"  [gemini] model: {chosen[:3]}")
        return chosen

    def _wait(self):
        dt = time.time() - self._last
        if dt < self.gap:
            time.sleep(self.gap - dt)
        self._last = time.time()

    def json(self, system: str, prompt: str, *, temperature: float = 0.4, max_out: int = 8192) -> dict:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_out,
                                 "responseMimeType": "application/json"},
        }
        last = None
        for model in self.models:
            for attempt in range(4):
                self._wait()
                try:
                    r = requests.post(f"{API}/models/{model}:generateContent", params={"key": self.key},
                                      json=body, timeout=180)
                except requests.RequestException as e:
                    last = str(e)[:200]
                    time.sleep(5 * (attempt + 1))
                    continue
                if r.status_code == 200:
                    self.calls += 1
                    j = r.json()
                    u = j.get("usageMetadata", {})
                    self.tokens_in += u.get("promptTokenCount", 0)
                    self.tokens_out += u.get("candidatesTokenCount", 0)
                    try:
                        text = "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"])
                    except (KeyError, IndexError):
                        last = f"trả rỗng: {json.dumps(j)[:200]}"
                        break
                    out = parse_json_loose(text)
                    if out is not None:
                        out.setdefault("_model", model)
                        return out
                    last = "JSON hỏng"
                    body["generationConfig"]["temperature"] = 0.2
                    continue
                last = f"HTTP {r.status_code}: {r.text[:200]}"
                if r.status_code == 429:
                    m = re.search(r'"retryDelay":\s*"(\d+)s"', r.text)
                    wait = int(m.group(1)) + 2 if m else 20 * (attempt + 1)
                    if "PerDay" in r.text or "per day" in r.text.lower():
                        break  # hết hạn mức ngày của model này → sang model sau
                    time.sleep(min(wait, 90))
                    continue
                if r.status_code in (500, 502, 503, 504):
                    time.sleep(8 * (attempt + 1))
                    continue
                break  # 400/403/404 → model này không dùng được
        raise GeminiError(last or "không gọi được Gemini")


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
