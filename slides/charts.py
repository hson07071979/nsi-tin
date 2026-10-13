"""Vẽ chart cho slide video Nguyen Son Finance (theme mệnh Thủy: navy, xanh nước, bạc).

Sơn chốt 13/10/2026: KHÔNG vẽ Bollinger. Chart = nến ngày 6 tháng + MA20/50/200 + KL/TB20
+ vùng hỗ trợ/kháng cự do daily/tech.py tự tính (hộp mờ) + mốc trong bảng phân tích (đường kẻ, nổi hơn).
Nhãn giá nằm ở cột bên phải, tự giãn để không đè nhau.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

FONTS = Path(__file__).parent / "fonts"
for f in FONTS.glob("*.otf"):
    fm.fontManager.addfont(str(f))
plt.rcParams["font.family"] = "Inter"

BG = "#0F2342"
GRID = "#1E3A63"
TXT = "#C5D0DE"
MUTED = "#7F93B2"
UP = "#26C281"
DOWN = "#EF5466"
WATER = "#4FC3F7"
MA50C = "#E8EEF6"
MA200C = "#B48CFF"
WATCH = "#FFFFFF"
DARK = "#0A1A33"

LEVEL_STYLE = {"watch": (WATCH, "--", 1.4), "sup": (UP, ":", 1.7), "res": (DOWN, ":", 1.7),
               "conf": (WATER, "-.", 1.2), "ref": (MUTED, ":", 1.1)}
ZONE_COLOR = {"sup": UP, "res": DOWN, "box": WATER}


def fmt(v: float, idx: bool = False, dec: int | None = None) -> str:
    if dec is None:
        dec = 2
    s = f"{v:,.{dec}f}".replace(",", "#").replace(".", ",").replace("#", ".")
    if not idx and "," in s:
        s = s.rstrip("0").rstrip(",")
    return s


def _sma(c: np.ndarray, w: int) -> np.ndarray:
    out = np.full_like(c, np.nan)
    for i in range(w - 1, len(c)):
        out[i] = c[i - w + 1:i + 1].mean()
    return out


def auto_zones(zones: dict | None, close: float, n_each: int = 2) -> list[tuple]:
    """Vùng tự tính từ tech.analyse → (lo, hi, kind, label). Bỏ vùng dựng từ Bollinger (cờ 'bb')."""
    if not zones:
        return []
    out = []
    t = zones.get("vung_dang_test")
    if t and not t.get("bb"):
        out.append((t["tu"], t["den"], "box", "Vùng đang test"))
    for z in [z for z in zones.get("ho_tro_gan") or [] if not z.get("bb")][:n_each]:
        out.append((z["tu"], z["den"], "sup", "Hỗ trợ" + (" mạnh" if z.get("do_manh", 0) >= 4 else "")))
    for z in [z for z in zones.get("khang_cu_gan") or [] if not z.get("bb")][:n_each]:
        out.append((z["tu"], z["den"], "res", "Kháng cự" + (" mạnh" if z.get("do_manh", 0) >= 4 else "")))
    # vùng quá xa giá (>15%) làm nén trục giá → bỏ
    return [z for z in out if abs((z[0] + z[1]) / 2 / close - 1) <= 0.15]


def draw(sym: str, bars: list[dict], out: str | Path, *, levels=(), zones=(), size=(5.7, 3.85), dpi=220,
         n: int = 125, idx: bool = False, compact: bool = False, ngay: str = "") -> bool:
    """levels: (giá, kind, nhãn) kind ∈ watch|sup|res|conf|ref ; zones: (lo, hi, kind, nhãn) kind ∈ sup|res|box."""
    if len(bars) < 30:
        return False
    full_c = np.array([b["c"] for b in bars], float)
    ma20, ma50, ma200 = _sma(full_c, 20), _sma(full_c, 50), _sma(full_c, 200)
    bars = bars[-n:]
    s = slice(len(full_c) - len(bars), len(full_c))
    ma20, ma50, ma200 = ma20[s], ma50[s], ma200[s]
    o = np.array([b["o"] for b in bars], float)
    h = np.array([b["h"] for b in bars], float)
    lo = np.array([b["l"] for b in bars], float)
    c = np.array([b["c"] for b in bars], float)
    v = np.array([b.get("v") or 0 for b in bars], float)
    N = len(bars)
    pad = 4
    fig = plt.figure(figsize=size, dpi=dpi, facecolor=BG)
    AX = [0.14, 0.22, 0.58, 0.66] if compact else [0.07, 0.25, 0.68 if idx else 0.6, 0.62]
    ax = fig.add_axes(AX, facecolor=BG)
    av = fig.add_axes([AX[0], 0.07, AX[2], 0.15], facecolor=BG, sharex=ax)
    x = np.arange(N)
    ax.plot(x, ma20, color=WATER, lw=1.3, zorder=3)
    ax.plot(x, ma50, color=MA50C, lw=1.1, alpha=0.8, zorder=3)
    ax.plot(x, ma200, color=MA200C, lw=1.4, zorder=3)
    w = 0.62
    for i in range(N):
        col = UP if c[i] >= o[i] else DOWN
        ax.vlines(i, lo[i], h[i], color=col, lw=0.9, zorder=4)
        ax.add_patch(Rectangle((i - w / 2, min(o[i], c[i])), w, max(abs(c[i] - o[i]), (h[i] - lo[i]) * 0.02 + 1e-9),
                               facecolor=col, edgecolor=col, lw=0.4, zorder=5))
        av.bar(i, v[i], width=w, color=col, alpha=0.75)
    vma = np.convolve(v, np.ones(20) / 20, mode="full")[:N]
    vma[:19] = np.nan
    av.plot(x, vma, color=WATER, lw=1.0)

    pr = [lo.min(), h.max()] + [p for p, *_ in levels] + [z for a, b, *_ in zones for z in (a, b)]
    ymin, ymax = min(pr), max(pr)
    m = (ymax - ymin) * 0.05 or ymax * 0.02
    ax.set_ylim(ymin - m, ymax + m)
    ax.set_xlim(-1, N + pad)
    x0 = N - (30 if compact else 40)
    tags = []
    zf = (lambda q: fmt(q, True, 0)) if idx else (lambda q: fmt(q))
    for a, b, kind, lab in zones:
        col = ZONE_COLOR[kind]
        ax.add_patch(Rectangle((x0, a), N + pad - x0, max(b - a, (ymax - ymin) * 0.004), facecolor=col, alpha=0.18,
                               edgecolor=col, lw=0.8, zorder=2))
        # vùng chứa sẵn một mốc phân tích thì không gắn thêm nhãn (đỡ rối)
        if lab and not any(a * 0.997 <= p <= b * 1.003 for p, *_ in levels):
            tags.append(((a + b) / 2, col, f"{zf(a)}–{zf(b)}" if b - a > a * 0.002 else zf(a), lab, True))
    for p, kind, lab in levels:
        col, ls, lw = LEVEL_STYLE[kind]
        ax.hlines(p, x0, N + pad, colors=col, linestyles=ls, lw=lw, zorder=6)
        tags.append((p, col, fmt(p, idx), lab, False))
    tags.append((c[-1], UP if c[-1] >= o[-1] else DOWN, fmt(c[-1], idx), "Đóng cửa", False))

    yr = ax.get_ylim()
    fr = lambda q: (q - yr[0]) / (yr[1] - yr[0])  # noqa: E731
    tags.sort(key=lambda z: z[0])
    gap = 0.1 if compact else 0.078
    pos: list[float] = []
    for tg in tags:
        y = fr(tg[0])
        if pos and y - pos[-1] < gap:
            y = pos[-1] + gap
        pos.append(y)
    if pos and pos[-1] > 0.99:
        pos[-1] = 0.99
        for i in range(len(pos) - 2, -1, -1):
            if pos[i + 1] - pos[i] < gap:
                pos[i] = pos[i + 1] - gap
    fs = 9.5 if compact else 8.4
    for (p, col, ptxt, lab, iszone), y in zip(tags, pos):
        if compact and iszone:
            continue
        ax.plot([1.0, 1.012], [fr(p), y], transform=ax.transAxes, color=col, lw=0.7, clip_on=False)
        ax.annotate(f" {ptxt} ", xy=(1.012, y), xycoords="axes fraction", va="center", ha="left", fontsize=fs,
                    fontweight="bold", color=DARK, bbox=dict(boxstyle="round,pad=0.22", fc=col, ec="none"),
                    annotation_clip=False, zorder=9)
        if not compact:
            ax.annotate(lab, xy=(1.012, y), xycoords="axes fraction", xytext=(len(ptxt) * 4.75 + 14, 0),
                        textcoords="offset points", va="center", ha="left", fontsize=7.8,
                        color=col if col != WATCH else TXT, annotation_clip=False)
    for axx in (ax, av):
        axx.tick_params(colors=MUTED, labelsize=9 if compact else 8.2, length=0)
        for sp in axx.spines.values():
            sp.set_visible(False)
        axx.grid(True, color=GRID, lw=0.5, alpha=0.8)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
        lambda q, _: f"{q:,.0f}".replace(",", ".") if idx else fmt(q)))
    av.set_yticks([])
    plt.setp(ax.get_xticklabels(), visible=False)
    ticks, labs = [], []
    days = [dt.date.fromisoformat(b["d"]) for b in bars]
    for i, d in enumerate(days):
        if i > 2 and d.month != days[i - 1].month:
            ticks.append(i)
            labs.append(f"T{d.month}")
    av.set_xticks(ticks)
    av.set_xticklabels(labs)
    if compact:
        fig.text(AX[0], 0.95, sym, color=WATCH, fontsize=13, fontweight="bold", va="center")
    else:
        fig.text(AX[0], 0.965, sym, color=WATCH, fontsize=11, fontweight="bold", va="center")
        fig.text(AX[0], 0.91, f"nến ngày · 6 tháng · đến {ngay}", color=MUTED, fontsize=7.6, va="center")
        xx = AX[0] + (0.25 if idx else 0.30)
        for lab, col in (("MA20", WATER), ("MA50", MA50C), ("MA200", MA200C)):
            fig.text(xx, 0.965, "— " + lab, color=col, fontsize=7.8, fontweight="semibold", va="center")
            xx += 0.1 if idx else 0.12
    av.text(0.005, 0.92, "KL · TB20", transform=av.transAxes, color=MUTED, fontsize=6.5, va="top")
    fig.savefig(out, facecolor=BG, dpi=dpi)
    plt.close(fig)
    return True


def draw_line(name: str, series: list[tuple], out: str | Path, *, levels=(), unit: str = "", size=(5.6, 2.9),
              dpi=220) -> bool:
    """Chart 1 năm cho biến thế giới (DXY, Brent, US10Y…): đường giá + vài mốc ngang."""
    if len(series) < 20:
        return False
    xs = [t for t, _ in series]
    ys = np.array([v for _, v in series], float)
    fig = plt.figure(figsize=size, dpi=dpi, facecolor=BG)
    ax = fig.add_axes([0.08, 0.13, 0.7, 0.72], facecolor=BG)
    ax.plot(xs, ys, color=WATER, lw=1.6)
    ax.fill_between(xs, ys, ys.min() - (ys.max() - ys.min()) * 0.05, color=WATER, alpha=0.08)
    vals = list(ys) + [p for p, *_ in levels]
    lo_, hi_ = min(vals), max(vals)
    m = (hi_ - lo_) * 0.06 or hi_ * 0.02
    ax.set_ylim(lo_ - m, hi_ + m)
    yr = ax.get_ylim()
    tags = [(ys[-1], UP, "Hiện tại")] + [(p, LEVEL_STYLE[k][0], lab) for p, k, lab in levels]
    for p, k, lab in levels:
        col, ls, lw = LEVEL_STYLE[k]
        ax.axhline(p, color=col, ls=ls, lw=lw)
    tags.sort(key=lambda z: z[0])
    pos: list[float] = []
    for p, *_ in tags:
        y = (p - yr[0]) / (yr[1] - yr[0])
        if pos and y - pos[-1] < 0.1:
            y = pos[-1] + 0.1
        pos.append(min(y, 0.99))
    for (p, col, lab), y in zip(tags, pos):
        ax.annotate(f" {fmt(p, dec=2 if p < 1000 else 0)} ", xy=(1.01, y), xycoords="axes fraction", va="center",
                    ha="left", fontsize=8.5, fontweight="bold", color=DARK,
                    bbox=dict(boxstyle="round,pad=0.22", fc=col, ec="none"), annotation_clip=False)
        ax.annotate(lab, xy=(1.01, y), xycoords="axes fraction", xytext=(52, 0), textcoords="offset points",
                    va="center", fontsize=7.8, color=col if col != WATCH else TXT, annotation_clip=False)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.grid(True, color=GRID, lw=0.5)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("T%m"))
    fig.text(0.08, 0.93, name, color=WATCH, fontsize=11, fontweight="bold", va="center")
    fig.text(0.08 + 0.012 * len(name) + 0.03, 0.93, f"1 năm · {unit}", color=MUTED, fontsize=7.6, va="center")
    fig.savefig(out, facecolor=BG, dpi=dpi)
    plt.close(fig)
    return True
