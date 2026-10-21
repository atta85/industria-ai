"""
Report diagrams, drawn with matplotlib and returned as PNG bytes so the same
images appear in the app and in the PDF:
  - fishbone (Ishikawa) diagram of the ranked root causes
  - likelihood bar chart of the ranked root causes
"""

import io
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

NAVY = "#1E293B"
INK = "#0F172A"
MUTED = "#64748B"
LINE = "#334155"
HEAD_FILL, HEAD_EDGE, HEAD_TEXT = "#FEE2E2", "#B91C1C", "#7F1D1D"
CAT_FILL, CAT_TEXT = "#EEF2FF", "#3730A3"
LIKELIHOOD_COLOR = {"High": "#3730A3", "Medium": "#6366F1", "Low": "#A5B4FC"}

TOP = ("People", "Machine", "Method")
BOTTOM = ("Material", "Measurement", "Environment")


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white", bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return buf.getvalue()


def _short(text, width, lines):
    wrapped = textwrap.wrap(str(text), width=width)
    if len(wrapped) > lines:
        wrapped = wrapped[:lines]
        wrapped[-1] = wrapped[-1].rstrip(".,; ")[: width - 1] + "…"
    return "\n".join(wrapped)


def fishbone(ranked_causes, problem_label="Problem") -> bytes:
    by_cat = {c: [] for c in TOP + BOTTOM}
    for i, rc in enumerate(ranked_causes, 1):
        by_cat.setdefault(rc.get("category", "Method"), []).append((i, rc.get("cause", "")))

    fig, ax = plt.subplots(figsize=(8.6, 3.9), dpi=170)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")

    spine_y, spine_end = 30, 79
    ax.plot([4, spine_end], [spine_y, spine_y], color=LINE, linewidth=2.2, solid_capstyle="round")
    ax.annotate("", xy=(spine_end + 1.2, spine_y), xytext=(spine_end - 2, spine_y),
                arrowprops=dict(arrowstyle="-|>", color=LINE, lw=2.2))
    ax.text(90.5, spine_y, _short(problem_label, 14, 3), ha="center", va="center", fontsize=8.5,
            color=HEAD_TEXT, fontweight="bold", linespacing=1.25,
            bbox=dict(boxstyle="round,pad=0.55", fc=HEAD_FILL, ec=HEAD_EDGE, lw=1.3))

    xs = (16, 40, 64)
    for row, cats in ((1, TOP), (-1, BOTTOM)):
        for x, cat in zip(xs, cats):
            causes = by_cat.get(cat, [])
            active = bool(causes)
            y_end = spine_y + row * 21
            x_top = x - 7
            ax.plot([x_top, x], [y_end, spine_y], color=LINE if active else "#CBD5E1", linewidth=1.5)
            ax.text(x_top, y_end + row * 3.2, cat, ha="center", va="center", fontsize=8.5,
                    color=CAT_TEXT if active else "#94A3B8", fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.35", fc=CAT_FILL if active else "#F8FAFC",
                              ec="#C7D2FE" if active else "#E2E8F0", lw=0.8))
            for k, (num, cause) in enumerate(causes[:2]):
                frac = 0.32 + 0.38 * k
                bx = x_top + (x - x_top) * frac
                by = y_end + (spine_y - y_end) * frac
                ax.plot([bx, bx + 2.2], [by, by], color=LINE, linewidth=1)
                ax.text(bx + 2.8, by, f"{num}. " + _short(cause, 24, 2), ha="left", va="center",
                        fontsize=6.8, color=INK, linespacing=1.15)
    return _png(fig)


def likelihood_chart(ranked_causes) -> bytes:
    items = list(ranked_causes)[:5]
    n = max(len(items), 1)
    fig, ax = plt.subplots(figsize=(7.4, 0.55 * n + 0.7), dpi=170)
    labels = [f"{i}. " + _short(rc.get("cause", ""), 38, 2) for i, rc in enumerate(items, 1)]
    values = [rc.get("likelihood_pct", 0) for rc in items]
    colors = [LIKELIHOOD_COLOR.get(rc.get("likelihood"), "#6366F1") for rc in items]
    y = list(range(len(items)))[::-1]
    ax.barh(y, values, color=colors, height=0.55, edgecolor="white", linewidth=1.5)
    for yy, v, rc in zip(y, values, items):
        ax.text(v + 1.5, yy, f"{v}%  {rc.get('likelihood', '')}", va="center", fontsize=8, color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8, color=INK)
    ax.set_xlim(0, 115)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.tick_params(axis="x", labelsize=7, colors=MUTED)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Estimated likelihood (%)", fontsize=8, color=MUTED)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#CBD5E1")
    ax.grid(axis="x", color="#E2E8F0", linewidth=0.6)
    ax.set_axisbelow(True)
    return _png(fig)
