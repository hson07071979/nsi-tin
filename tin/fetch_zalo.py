"""Đọc tin 5 nhóm Zalo do listener trên laptop đẩy lên repo (zalo/inbox/YYYY-MM-DD.jsonl)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from .common import VN, clean_text, khong_dau, parse_iso, read_json

RAC = re.compile(r"^(ok+|oke+|dạ+|vâng|ạ+|hi+|hihi+|haha+|kk+|\W+|\d+|cảm ơn.*|thanks?.*|tks)$", re.I)


def _is_rac(t: str) -> bool:
    t = t.strip()
    return len(t) < 12 or bool(RAC.match(t))


def load_zalo(root: Path, cfg_groups: dict, start: datetime, end: datetime) -> tuple[list[dict], dict]:
    inbox = root / "zalo" / "inbox"
    groups = {g["key"]: g["name"] for g in cfg_groups["groups"]}
    raw = []
    d = start.date() - timedelta(days=1)
    while d <= end.date():
        f = inbox / f"{d.isoformat()}.jsonl"
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                try:
                    m = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = datetime.fromtimestamp(int(m.get("ts", 0)) / 1000, VN)
                if start < ts <= end:
                    m["_ts"] = ts
                    raw.append(m)
        d += timedelta(days=1)

    # khử trùng theo msg_id (listener có thể đẩy trùng khi nối lại)
    seen, msgs = set(), []
    for m in sorted(raw, key=lambda x: x["_ts"]):
        k = m.get("msg_id") or (m.get("group_key"), m.get("ts"), m.get("text", "")[:40])
        if k in seen:
            continue
        seen.add(k)
        msgs.append(m)

    # gộp tin liên tiếp cùng người trong 3 phút (người ta hay chat ngắt dòng)
    merged: list[dict] = []
    for m in msgs:
        text = clean_text(m.get("text", ""))
        if m.get("links"):
            text += " " + " ".join(f"[{clean_text(l.get('title',''))}]({l.get('href','')})" for l in m["links"] if l)
        if not text.strip():
            continue
        last = merged[-1] if merged else None
        if (last and last["group_key"] == m.get("group_key") and last["from_id"] == m.get("from_id")
                and (m["_ts"] - last["_ts"]).total_seconds() <= 180):
            last["text"] += "\n" + text
            last["_ts"] = m["_ts"]
            continue
        merged.append({"group_key": m.get("group_key"), "from_id": m.get("from_id"),
                       "from_name": m.get("from_name") or "?", "text": text, "_ts": m["_ts"],
                       "_ts0": m["_ts"], "kind": m.get("kind", "text")})

    items = []
    per_group = {k: 0 for k in groups}
    for i, m in enumerate(merged):
        if _is_rac(m["text"]):
            continue
        per_group[m["group_key"]] = per_group.get(m["group_key"], 0) + 1
        items.append({
            "id": f"z{i:04d}", "group": m["group_key"], "src_name": groups.get(m["group_key"], m["group_key"]),
            "author": m["from_name"], "text": m["text"][:1500],
            "published": m["_ts0"].isoformat(timespec="minutes"),
            "score": 1 + min(3, len(m["text"]) // 250) + (2 if any(k in khong_dau(m["text"]) for k in
                     ("lai suat", "ty gia", "nhnn", "fed", "khoi ngoai", "margin", "canh bao", "khuyen nghi")) else 0),
        })

    hb = read_json(root / "zalo" / "heartbeat.json", {})
    hb_ts = parse_iso(hb.get("at"))
    status = {
        "so_tin_tho": len(msgs), "so_tin_dung": len(items), "theo_nhom": per_group,
        "heartbeat": hb.get("at"), "listener_version": hb.get("version"),
        "listener_song": bool(hb_ts and (end - hb_ts) <= timedelta(hours=2)),
        "nhom_da_nghe": hb.get("groups", {}),
    }
    return items, status
