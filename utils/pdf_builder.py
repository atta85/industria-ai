"""
Compact, professional PDF of the Verified Decision-Support Report (ReportLab,
pure Python). Tabular and side-by-side so it stays short: summary, ranked
root-cause table, diagrams, critical review, interpretation, evidence and
references. Diagrams are regenerated from the report data, so a saved report
can be re-exported later.
"""

import io
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from utils.diagrams import fishbone, likelihood_chart

NAVY = colors.HexColor("#1E293B")
INK = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#475569")
LINE = colors.HexColor("#E2E8F0")
INDIGO = colors.HexColor("#4F46E5")
INDIGO_SOFT = colors.HexColor("#EEF2FF")
INDIGO_TEXT = colors.HexColor("#3730A3")
GREEN, GREEN_SOFT = colors.HexColor("#047857"), colors.HexColor("#D1FAE5")
AMBER, AMBER_SOFT, AMBER_TEXT = colors.HexColor("#B45309"), colors.HexColor("#FEF3C7"), colors.HexColor("#92400E")
RED, RED_SOFT = colors.HexColor("#B91C1C"), colors.HexColor("#FEE2E2")
ROW_ALT = colors.HexColor("#F8FAFC")
CHIP = {"High": ("#FEE2E2", "#991B1B"), "Medium": ("#FEF3C7", "#92400E"), "Low": ("#E0F2FE", "#075985")}

W, H = A4
M = 15 * mm
CW = W - 2 * M

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MAP = {"→": "->", "←": "<-", "≥": ">=", "≤": "<=", "≈": "~", "−": "-",
        " ": " ", " ": " ", " ": " ", "​": "", "‑": "-", "✓": "", "✔": ""}


def _clean(v) -> str:
    out = []
    for ch in _CTRL.sub("", "" if v is None else str(v)):
        if ch in _MAP:
            out.append(_MAP[ch])
            continue
        try:
            ch.encode("cp1252")
            out.append(ch)
        except UnicodeEncodeError:
            pass
    return "".join(out)


def _t(v) -> str:
    return escape(_clean(v)).replace("\n", "<br/>")


def _styles():
    base = dict(fontName="Helvetica", textColor=INK)
    return {
        "body": ParagraphStyle("body", fontSize=9, leading=12.5, **base),
        "small": ParagraphStyle("small", fontSize=7.8, leading=10.5, fontName="Helvetica", textColor=MUTED),
        "cell": ParagraphStyle("cell", fontSize=8, leading=10.6, **base),
        "cellb": ParagraphStyle("cellb", fontSize=8, leading=10.6, fontName="Helvetica-Bold", textColor=INK),
        "head": ParagraphStyle("head", fontSize=8, leading=10.6, fontName="Helvetica-Bold", textColor=colors.white),
        "h1": ParagraphStyle("h1", fontSize=11.5, leading=14, fontName="Helvetica-Bold", textColor=NAVY,
                             spaceBefore=9, spaceAfter=4, keepWithNext=1),
        "h2": ParagraphStyle("h2", fontSize=8.6, leading=11, fontName="Helvetica-Bold", textColor=INDIGO_TEXT,
                             spaceAfter=2),
        "title": ParagraphStyle("title", fontSize=17, leading=21, fontName="Helvetica-Bold", textColor=colors.white),
        "sub": ParagraphStyle("sub", fontSize=8.8, leading=12, fontName="Helvetica", textColor=colors.HexColor("#CBD5E1")),
        "summary": ParagraphStyle("summary", fontSize=9.6, leading=13.6, fontName="Helvetica", textColor=colors.HexColor("#1E1B4B")),
    }


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(M, 11 * mm, W - M, 11 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(M, 7.5 * mm, "Industria-AI  |  Decision support only. Verify before acting.")
    canvas.drawRightString(W - M, 7.5 * mm, f"Report {doc._report_id}  |  Page {doc.page}")
    canvas.restoreState()


def _table(rows, widths, header=True, zebra=True):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.4, LINE),
             ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
             ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), NAVY))
    if zebra:
        style.append(("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, ROW_ALT]))
    t.setStyle(TableStyle(style))
    return t


def _box(flow, fill, edge, accent=False):
    t = Table([[flow]], colWidths=[CW])
    style = [("BACKGROUND", (0, 0), (-1, -1), fill), ("LEFTPADDING", (0, 0), (-1, -1), 10),
             ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 7),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]
    style.append(("LINEBEFORE", (0, 0), (0, -1), 3, edge) if accent else ("BOX", (0, 0), (-1, -1), 0.8, edge))
    t.setStyle(TableStyle(style))
    return t


def _bullets(items, st):
    items = [i for i in (items or []) if str(i).strip()]
    if not items:
        return Paragraph("<i>None stated.</i>", st["small"])
    return Paragraph("<br/>".join(f"&bull; {_t(i)}" for i in items), st["cell"])


def _img(png, width):
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(io.BytesIO(png)).getSize()
    return Image(io.BytesIO(png), width=width, height=width * ih / iw)


def build_pdf(r: dict, problem_label: str = "") -> bytes:
    st = _styles()
    rv = r.get("review", {})
    it = r.get("interpretation", {})
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=M, rightMargin=M, topMargin=13 * mm,
                            bottomMargin=16 * mm, title="Verified Decision-Support Report", author="Industria-AI")
    doc._report_id = r.get("report_id", "")
    s = []

    # Header band
    band = Table([[Paragraph("Verified Decision-Support Report", st["title"])],
                  [Paragraph(f"Industria-AI  |  Industrial problem analysis  |  {_t(r.get('industry'))}", st["sub"])]],
                 colWidths=[CW])
    band.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("LEFTPADDING", (0, 0), (-1, -1), 12),
                              ("TOPPADDING", (0, 0), (0, 0), 11), ("BOTTOMPADDING", (0, 1), (0, 1), 10),
                              ("LINEBELOW", (0, -1), (-1, -1), 3, INDIGO)]))
    s += [band, Spacer(1, 6)]

    # Status + meta
    accepted = str(r.get("decision", "")).upper() == "ACCEPTED"
    badge_c, badge_bg = (GREEN, GREEN_SOFT) if accepted else (RED, RED_SOFT)
    badge = Paragraph(f"<b>{_t(r.get('decision'))}</b><br/><font size=7>by human reviewer</font>",
                      ParagraphStyle("b", fontSize=10, leading=12, textColor=badge_c, alignment=1))
    meta = [[Paragraph("<b>Verified by</b>", st["cell"]), Paragraph(_t(r.get("verified_by")), st["cell"]),
             Paragraph("<b>Date</b>", st["cell"]), Paragraph(_t(r.get("generated_utc")), st["cell"])],
            [Paragraph("<b>Verification</b>", st["cell"]), Paragraph(_t(str(r.get("mode", "")).capitalize()), st["cell"]),
             Paragraph("<b>Specialists</b>", st["cell"]), Paragraph(_t(", ".join(r.get("specialists", []))), st["cell"])]]
    meta_t = Table(meta, colWidths=[22 * mm, 47 * mm, 22 * mm, CW - 33 * mm - 91 * mm])
    meta_t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 4),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 2)]))
    top = Table([[badge, meta_t]], colWidths=[33 * mm, CW - 33 * mm])
    top.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), badge_bg), ("BOX", (0, 0), (0, 0), 0.8, badge_c),
                             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (1, 0), (1, 0), 6)]))
    s += [top, Spacer(1, 7)]

    # Summary
    s.append(_box(Paragraph(f"<b>Summary.</b> {_t(rv.get('executive_summary') or 'Not available.')}"
                            f"<br/><font size=8 color='#3730A3'><b>Reviewer verdict:</b> {_t(rv.get('verdict', 'Not stated'))}</font>",
                            st["summary"]), INDIGO_SOFT, INDIGO, accent=True))
    if it.get("high_risk"):
        s += [Spacer(1, 5), _box(Paragraph(
            f"<b>Safety-relevant problem.</b> {_t(it.get('risk_note') or '')} Have a qualified engineer verify every action.",
            ParagraphStyle("w", fontSize=8.5, leading=11.5, textColor=AMBER_TEXT)), AMBER_SOFT, AMBER)]

    # Ranked root causes
    causes = rv.get("ranked_causes", [])
    s.append(Paragraph("1. Ranked root causes and actions", st["h1"]))
    rows = [[Paragraph(h, st["head"]) for h in ("#", "Root cause", "Likelihood", "Evidence", "Recommended action", "How to verify")]]
    chip_styles = []
    for i, c in enumerate(causes, 1):
        bg, fg = CHIP.get(c["likelihood"], CHIP["Medium"])
        rows.append([
            Paragraph(f"<b>{i}</b>", st["cell"]),
            Paragraph(f"<b>{_t(c['cause'])}</b><br/><font size=7 color='#475569'>{_t(c['category'])}</font>", st["cell"]),
            Paragraph(f"<b>{_t(c['likelihood'])}</b><br/>{c['likelihood_pct']}%",
                      ParagraphStyle("chip", fontSize=8, leading=10.5, textColor=colors.HexColor(fg), alignment=1)),
            Paragraph(_t(c.get("evidence")), st["cell"]),
            Paragraph(f"{_t(c.get('action'))}<br/><font size=7 color='#3730A3'><b>{_t(c.get('priority'))}</b></font>", st["cell"]),
            Paragraph(_t(c.get("verification")), st["cell"]),
        ])
        chip_styles.append(("BACKGROUND", (2, i), (2, i), colors.HexColor(bg)))
    if len(rows) == 1:
        rows.append([Paragraph("-", st["cell"]), Paragraph("No ranked causes were produced.", st["cell"])] +
                    [Paragraph("", st["cell"])] * 4)
    t = _table(rows, [7 * mm, 40 * mm, 19 * mm, 38 * mm, 39 * mm, CW - 143 * mm])
    t.setStyle(TableStyle(chip_styles + [("VALIGN", (2, 1), (2, -1), "MIDDLE")]))
    s.append(t)

    # Diagrams
    if causes:
        s.append(Paragraph("2. Cause map and likelihood", st["h1"]))
        fish = _img(fishbone(causes, problem_label or "Problem"), CW)
        bars = _img(likelihood_chart(causes), CW * 0.86)
        s.append(KeepTogether([fish, Spacer(1, 3), bars]))

    # Critical review, side by side
    s.append(Paragraph("3. Critical review", st["h1"]))
    rows = [[Paragraph("Critical findings", st["head"]), Paragraph("Alternative explanations", st["head"])],
            [_bullets(rv.get("critical_findings"), st), _bullets(rv.get("alternative_explanations"), st)],
            [Paragraph("Uncertainties", st["head"]), Paragraph("Risks of the proposed actions", st["head"])],
            [_bullets(rv.get("uncertainties"), st), _bullets(rv.get("risks"), st)]]
    t = _table(rows, [CW / 2, CW / 2], header=False, zebra=False)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("BACKGROUND", (0, 2), (-1, 2), NAVY)]))
    s.append(t)

    # Interpretation
    s.append(Paragraph("4. Problem and interpretation", st["h1"]))
    assumed = set(r.get("ai_assumed_fields") or [])

    def lab(name, key):
        tag = " <font size=6.5 color='#92400E'>(AI assumption)</font>" if key in assumed else ""
        return Paragraph(f"<b>{name}</b>{tag}", st["cell"])

    rows = [[Paragraph("<b>Problem statement</b>", st["cell"]), Paragraph(_t(r.get("problem_statement")), st["cell"])],
            [Paragraph("<b>Interpretation</b>", st["cell"]), Paragraph(_t(it.get("problem_summary")), st["cell"])],
            [lab("Objectives", "objectives"), _bullets(it.get("objectives"), st)],
            [lab("Constraints", "constraints"), _bullets(it.get("constraints"), st)],
            [lab("Available data", "available_data"), _bullets(it.get("available_data"), st)],
            [lab("Desired outcome", "desired_outcome"), Paragraph(_t(it.get("desired_outcome") or "Not stated"), st["cell"])],
            [Paragraph("<b>Assumptions</b>", st["cell"]), _bullets(it.get("assumptions"), st)],
            [Paragraph("<b>Missing information</b>", st["cell"]), _bullets(it.get("missing_information"), st)]]
    if r.get("data_profile"):
        rows.append([Paragraph("<b>Process data</b>", st["cell"]),
                     Paragraph(_t(r["data_profile"].get("summary")), st["cell"])])
    s.append(_table(rows, [36 * mm, CW - 36 * mm], header=False))

    # Evidence and references
    s.append(Paragraph("5. Evidence and references", st["h1"]))
    ev = r.get("evidence", [])
    if ev:
        rows = [[Paragraph(h, st["head"]) for h in ("Finding", "Type", "Source")]]
        for e in ev:
            cite = f" <b>[{e['citation']}]</b>" if e.get("citation") else ""
            kind = {"academic": "Academic", "web": "Web"}.get(e.get("source_type"), "Unverified")
            url = _clean(e.get("source_url", ""))
            title = _t(e.get("source_title") or "Source")
            src = (f'<link href="{escape(url, {chr(34): "&quot;"})}" color="#4F46E5"><u>{title}</u></link>'
                   if url.startswith("http") else title)
            rows.append([Paragraph(_t(e.get("finding")) + cite, st["cell"]), Paragraph(kind, st["cell"]),
                         Paragraph(src, st["cell"])])
        s.append(_table(rows, [CW * 0.55, CW * 0.12, CW * 0.33]))
    else:
        s.append(Paragraph("<i>No external evidence was available for this analysis.</i>", st["small"]))
    refs = r.get("references", [])
    s.append(Spacer(1, 5))
    s.append(Paragraph("References", st["h2"]))
    if refs:
        for x in refs:
            url = _clean(x.get("url", ""))
            link = (f' <link href="{escape(url, {chr(34): "&quot;"})}" color="#4F46E5"><u>{escape(url)}</u></link>'
                    if url.startswith("http") else "")
            s.append(Paragraph(f"[{x['number']}] {_t(x['text'])}{link}", st["cell"]))
    else:
        s.append(Paragraph("<i>No academic papers were cited.</i>", st["small"]))

    # Notes
    s.append(Spacer(1, 7))
    notes = [w for w in r.get("warnings", []) if w]
    s.append(_box(Paragraph("<br/>".join(f"&bull; {_t(w)}" for w in notes),
                            ParagraphStyle("n", fontSize=7.8, leading=10.6, textColor=AMBER_TEXT)), AMBER_SOFT, AMBER))

    doc.build(s, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
