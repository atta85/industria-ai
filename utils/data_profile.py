"""
Optional CSV upload. The statistics are computed by code (pandas), not by the
AI, and a compact text summary is passed to the agents. A trend chart is drawn
for the app and the report.
"""

import io

import pandas as pd

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 50_000
MAX_SUMMARY_CHARS = 1800


class DataError(Exception):
    pass


def load_csv(uploaded_bytes: bytes) -> pd.DataFrame:
    if len(uploaded_bytes) > MAX_BYTES:
        raise DataError("The file is larger than 5 MB. Upload a smaller extract.")
    for enc in ("utf-8", "latin-1"):
        try:
            df = pd.read_csv(io.BytesIO(uploaded_bytes), encoding=enc, nrows=MAX_ROWS, sep=None, engine="python")
            break
        except UnicodeDecodeError:
            continue
        except Exception as exc:  # noqa: BLE001
            raise DataError(f"The file could not be read as CSV ({exc.__class__.__name__}).") from exc
    else:
        raise DataError("The file encoding is not supported. Save it as UTF-8 CSV.")
    df = df.dropna(axis=1, how="all")
    if df.empty or df.shape[1] == 0:
        raise DataError("The file has no usable rows or columns.")
    for col in df.columns:
        if df[col].dtype == object:
            converted = pd.to_numeric(df[col].astype(str).str.replace(",", "").str.strip(), errors="coerce")
            if converted.notna().mean() >= 0.9:
                df[col] = converted
    return df


def _time_column(df):
    for col in df.columns:
        if df[col].dtype == object or "date" in str(col).lower() or "time" in str(col).lower():
            parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
            if parsed.notna().mean() >= 0.8:
                return col, parsed
    return None, None


def profile(df: pd.DataFrame) -> dict:
    numeric = df.select_dtypes("number")
    tcol, tvals = _time_column(df)
    lines = [f"Rows: {len(df)}, columns: {df.shape[1]}."]
    if tcol is not None:
        lines.append(f"Time column: {tcol} ({tvals.min():%Y-%m-%d} to {tvals.max():%Y-%m-%d}).")
    stats = []
    for col in list(numeric.columns)[:12]:
        s = numeric[col].dropna()
        if s.empty:
            continue
        half = len(s) // 2
        change = None
        if half >= 3:
            a, b = s.iloc[:half].mean(), s.iloc[half:].mean()
            if a != 0:
                change = (b - a) / abs(a) * 100
        stats.append({"column": str(col), "mean": s.mean(), "std": s.std(), "min": s.min(), "max": s.max(),
                      "missing_pct": df[col].isna().mean() * 100, "change_pct": change})
        trend = f", second half vs first half {change:+.1f}%" if change is not None else ""
        lines.append(f"{col}: mean {s.mean():.4g}, sd {s.std():.3g}, range {s.min():.4g} to {s.max():.4g}{trend}.")
    corr_lines = []
    if numeric.shape[1] >= 2:
        corr = numeric.iloc[:, :12].corr().abs()
        pairs = []
        cols = list(corr.columns)
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                v = corr.iloc[i, j]
                if pd.notna(v) and v >= 0.5:
                    pairs.append((v, cols[i], cols[j], numeric[cols[i]].corr(numeric[cols[j]])))
        for v, a, b, signed in sorted(pairs, reverse=True)[:5]:
            corr_lines.append(f"{a} vs {b}: r = {signed:+.2f}")
    if corr_lines:
        lines.append("Strongest correlations: " + "; ".join(corr_lines) + ".")
    other = [c for c in df.columns if c not in numeric.columns and c != tcol][:5]
    for col in other:
        top = df[col].astype(str).value_counts().head(3)
        lines.append(f"{col} (categories): " + ", ".join(f"{k} ({v})" for k, v in top.items()) + ".")
    summary = " ".join(lines)
    if len(summary) > MAX_SUMMARY_CHARS:
        summary = summary[:MAX_SUMMARY_CHARS].rsplit(" ", 1)[0] + " ..."
    return {"summary": summary, "rows": len(df), "columns": int(df.shape[1]), "stats": stats,
            "time_column": str(tcol) if tcol is not None else None, "correlations": corr_lines}


def trend_chart(df: pd.DataFrame):
    """PNG bytes: up to 4 numeric columns, each indexed to its own mean so
    different units share one axis honestly. None if nothing to plot."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    numeric = df.select_dtypes("number")
    cols = [c for c in numeric.columns if numeric[c].notna().sum() >= 5][:4]
    if not cols:
        return None
    tcol, tvals = _time_column(df)
    x = tvals if tcol is not None else range(len(df))
    colors = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
    fig, ax = plt.subplots(figsize=(7.2, 2.8), dpi=160)
    for c, color in zip(cols, colors):
        s = numeric[c]
        base = s.mean() if s.mean() else 1
        ax.plot(x, s / base * 100, color=color, linewidth=1.8, label=str(c)[:28])
    ax.axhline(100, color="#94A3B8", linewidth=0.8, linestyle="--")
    ax.set_ylabel("% of column average", fontsize=8, color="#475569")
    ax.tick_params(labelsize=7, colors="#475569")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#CBD5E1")
    ax.grid(axis="y", color="#E2E8F0", linewidth=0.6)
    ax.legend(fontsize=7, frameon=False, ncol=min(4, len(cols)), loc="upper left", bbox_to_anchor=(0, 1.18))
    fig.autofmt_xdate() if tcol is not None else None
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    return buf.getvalue()
