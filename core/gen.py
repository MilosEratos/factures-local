#!/usr/bin/env python3
"""Moteur de génération de factures PDF — standalone.

Page 612×792 pt (lettre), mise en page calibrée au pixel sur des PDF réels
(baselines en pt depuis le haut de la page).

Deux modes :
  - CLI  : python core/gen.py   (JSON sur stdin → PDF + aperçu PNG dans data/, JSON sur stdout)
  - import : from core.gen import build, load_config  (utilisé par server.py)

Toutes les données d'identité (vendeur, RIB, logo, mention TVA) viennent de
config.json — valeurs de démo, à remplacer par les vôtres.
"""
import sys
import os
import re
import json
import io
import unicodedata
import contextlib
import warnings

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = 612.0, 792.0
C_LINE = (0.871, 0.882, 0.886)
C_BOX = (0.957, 0.961, 0.961)
C_GREY = (0.502, 0.502, 0.502)
C_BLACK = (0, 0, 0)
C_WHITE = (1, 1, 1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --- polices : Arial si les TTF sont accessibles, sinon repli Helvetica ---
def _fonts():
    for d in (r"C:\Windows\Fonts", "/usr/share/fonts/truetype/msttcorefonts"):
        arial = os.path.join(d, "arial.ttf")
        arialbd = os.path.join(d, "arialbd.ttf")
        if os.path.exists(arial) and os.path.exists(arialbd):
            pdfmetrics.registerFont(TTFont("Arial", arial))
            pdfmetrics.registerFont(TTFont("Arial-Bold", arialbd))
            return
_fonts()
F_REG, F_BOLD = "Arial", "Arial-Bold"
if F_REG not in pdfmetrics.getRegisteredFontNames():
    F_REG, F_BOLD = "Helvetica", "Helvetica-Bold"


# --- positions mesurées (baselines, coordonnées du haut de la page) ---
HEADER_LINE_Y = 187.5
NUM_BL, DATE_BL, CLIENT_BL = 203.87, 220.87, 237.87
ADDR1_BL, ADDR2L_FIRST_BL, ADDR2L_PITCH = 254.87, 253.08, 10.8

TITLE_CENTER_Y, TITLE_SIZE, TITLE_PITCH = 228.76, 12.0, 14.4

BOX_X1 = 592.74
BOX_TOP, BOX_H = 216.50, 22.68
BOX_TEXT_BL = 230.92
BOX_PAD = 12.0

BAR_TOP, BAR_H = 269.03, 23.95
BAR_DESC_BL, BAR_UNITY_BL, BAR_COST_BL = 283.77, 284.31, 283.77
BAR_DESC_X, BAR_UNITY_X, BAR_COST_X = 25.50, 362.77, 574.0

ITEM_X, ITEM_DESC_BL, ITEM_PITCH, ITEM_SEP1 = 24.71, 310.80, 30.0, 321.75
QTY_C, AMT_R, DESC_MAX_W = 378.0, 574.0, 299.3

TOTAL_LABEL_R, TOTAL_VAL_R = 492.34, 574.0
TOTAL_BL_OFFSET, TOTAL_LINE_OFFSET = 20.33, 14.26
TOTAL_LINE_X0, TOTAL_LINE_X1 = 404.11, 612.50

RIB_X = 25.52
TVA_BL, TVA_X = 756.02, 306.0

LOGO_X, LOGO_TOP, LOGO_SIZE = 21.50, 25.00, 122.24


def load_config():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def T(c, x, bl, size, s, font=F_REG, align="left", color=C_BLACK):
    c.setFont(font, size)
    c.setFillColorRGB(*color)
    y = PAGE_H - bl
    w = pdfmetrics.stringWidth(s, font, size)
    if align == "right":
        x = x - w
    elif align == "center":
        x = x - w / 2
    c.drawString(x, y, s)
    return w


def hline(c, x0, x1, y, color=C_LINE, width=1.0):
    c.setStrokeColorRGB(*color)
    c.setLineWidth(width)
    c.line(x0, PAGE_H - y, x1, PAGE_H - y)


def rect(c, x, top, w, h, color):
    c.setFillColorRGB(*color)
    c.rect(x, PAGE_H - top - h, w, h, stroke=0, fill=1)


def fmt_eur(n):
    s = ("%d" % int(n)) if float(n) == int(n) else ("%.2f" % n)
    return s + " €"


def draw_line_desc(c, bl, desc, note):
    x = ITEM_X
    c.setFont(F_BOLD, 9)
    c.setFillColorRGB(*C_BLACK)
    y = PAGE_H - bl
    c.drawString(x, y, desc)
    x += pdfmetrics.stringWidth(desc, F_BOLD, 9)
    if not note:
        return
    max_x = ITEM_X + DESC_MAX_W
    if x + pdfmetrics.stringWidth(note, F_REG, 9) <= max_x:
        c.setFont(F_REG, 9)
        c.drawString(x, y, note)
        return
    main, paren = note, ""
    i = note.find(" (")
    if i > 0:
        main, paren = note[:i + 1], note[i + 1:]
    w_main = pdfmetrics.stringWidth(main, F_REG, 9)
    if paren:
        c.setFont(F_REG, 9)
        c.drawString(x, y, main)
        x += w_main
        room = max_x - x
        if room > 0:
            w_paren = pdfmetrics.stringWidth(paren, F_REG, 9)
            size = max(5.0, 9.0 * room / w_paren)
            c.setFont(F_REG, size)
            c.drawString(x, y, paren)
    else:
        room = max_x - x
        w_note = pdfmetrics.stringWidth(note, F_REG, 9)
        size = max(5.0, 9.0 * room / w_note)
        c.setFont(F_REG, size)
        c.drawString(x, y, note)


def build(data, out_path, config=None):
    """Génère la facture PDF dans out_path. Retourne le total."""
    if config is None:
        config = load_config()
    c = canvas.Canvas(out_path, pagesize=(PAGE_W, PAGE_H))

    logo_rel = config.get("logo", "")
    if logo_rel:
        logo_path = os.path.join(ROOT, logo_rel.replace("/", os.sep))
        if os.path.exists(logo_path):
            c.drawImage(logo_path, LOGO_X, PAGE_H - (LOGO_TOP + LOGO_SIZE),
                        width=LOGO_SIZE, height=LOGO_SIZE)

    for h in config.get("header", []):
        T(c, h["x"], h["bl"], h["size"], h["text"],
          F_BOLD if h.get("font") == "bold" else F_REG, "right")

    hline(c, 0, PAGE_W, HEADER_LINE_Y, C_LINE, 1.0)

    # bloc gauche : N°, date, client, adresse
    T(c, 25.35, NUM_BL, 10, "Facture N° %s" % data["number"])
    T(c, 25.35, DATE_BL, 10, "Le %s" % data["date"])
    w_client = T(c, 25.35, CLIENT_BL, 10, "Client : ")
    T(c, 25.35 + w_client, CLIENT_BL, 10, data["client_name"], F_BOLD)

    addr = data.get("client_addr", [])
    if len(addr) <= 1:
        for a in addr:
            T(c, 25.35, ADDR1_BL, 10, a)
    else:
        for i, a in enumerate(addr):
            T(c, 25.35, ADDR2L_FIRST_BL + i * ADDR2L_PITCH, 9, a)

    # titre (centré verticalement, 1re ligne en gras)
    TITLE_MAX_W = 200.0
    title = data.get("title", [])
    if title:
        wrapped = []
        for i, t in enumerate(title):
            font = F_BOLD if i == 0 else F_REG
            words = t.split()
            lines, cur = [], ""
            for w in words:
                test = (cur + " " + w).strip()
                if pdfmetrics.stringWidth(test, font, TITLE_SIZE) <= TITLE_MAX_W:
                    cur = test
                else:
                    if cur:
                        lines.append(cur)
                    cur = w
            if cur:
                lines.append(cur)
            wrapped.extend(lines)
        n = len(wrapped)
        first_bl = TITLE_CENTER_Y - (n - 1) * TITLE_PITCH / 2
        for i, t in enumerate(wrapped):
            font = F_BOLD if i == 0 else F_REG
            T(c, 306.0, first_bl + i * TITLE_PITCH, TITLE_SIZE, t, font, "center")

    # encadré Coût total (texte centré H + V)
    total = sum(float(l["amount"]) for l in data["lines"])
    total_str = "Coût total (EUR): " + fmt_eur(total)
    tw = pdfmetrics.stringWidth(total_str, F_BOLD, 10)
    box_w = tw + 2 * BOX_PAD
    box_x0 = BOX_X1 - box_w
    rect(c, box_x0, BOX_TOP, box_w, BOX_H, C_BOX)
    T(c, (box_x0 + BOX_X1) / 2, BOX_TEXT_BL, 10, total_str, F_BOLD, "center")

    # barre noire d'en-tête de tableau
    rect(c, 0, BAR_TOP, PAGE_W, BAR_H, C_BLACK)
    T(c, BAR_DESC_X, BAR_DESC_BL, 10, "Description", F_BOLD, "left", C_WHITE)
    T(c, BAR_UNITY_X, BAR_UNITY_BL, 10, "Unités", F_BOLD, "left", C_WHITE)
    T(c, BAR_COST_X, BAR_COST_BL, 10, "Coût", F_BOLD, "right", C_WHITE)

    # lignes d'items
    lines = data["lines"]
    for i, l in enumerate(lines):
        rt = ITEM_DESC_BL + i * ITEM_PITCH
        note = l.get("note", "")
        if note and not note.startswith(" "):
            note = " " + note
        draw_line_desc(c, rt, l["desc"], note)
        T(c, QTY_C, rt + 0.02, 10, str(int(l["qty"])) if float(l["qty"]) == int(l["qty"]) else str(l["qty"]), F_REG, "center")
        T(c, AMT_R, rt + 0.16, 10, fmt_eur(l["amount"]), F_REG, "right")
        hline(c, 1.57, 613.57, ITEM_SEP1 + i * ITEM_PITCH, C_LINE, 2.0)

    # total
    last_sep = ITEM_SEP1 + (len(lines) - 1) * ITEM_PITCH
    tot_bl = last_sep + TOTAL_BL_OFFSET
    T(c, TOTAL_LABEL_R, tot_bl, 10, "Total:", F_BOLD, "right")
    T(c, TOTAL_VAL_R, tot_bl, 10, fmt_eur(total), F_REG, "right")
    hline(c, TOTAL_LINE_X0, TOTAL_LINE_X1, tot_bl + TOTAL_LINE_OFFSET, C_LINE, 2.23)

    # RIB (valeurs de config.json)
    for r in config.get("rib", []):
        T(c, RIB_X, r["bl"], 10, r["text"], F_BOLD if r.get("bold") else F_REG)

    tva_note = config.get("tva_note", "")
    if tva_note:
        T(c, TVA_X, TVA_BL, 10, tva_note, F_REG, "center", C_GREY)

    c.showPage()
    c.save()
    return total


def make_preview(pdf_path):
    """Aperçu PNG (100 dpi) de la 1re page. Retourne le chemin ou None."""
    try:
        buf = io.StringIO()
        with warnings.catch_warnings(), contextlib.redirect_stderr(buf), \
                contextlib.redirect_stdout(buf):
            warnings.simplefilter("ignore")
            import fitz
            doc = fitz.open(pdf_path)
            png = pdf_path[:-4] + "_preview.png"
            doc[0].get_pixmap(dpi=100).save(png)
            return png
    except Exception as e:
        sys.stderr.write("preview: %s\n" % e)
        return None


def safe_name(s):
    """Nom de fichier plat : aucun '/', pas de tirets demi-chasse, accents retirés."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not ("\u0300" <= ch <= "\u036f"))
    s = re.sub(r'[/\\<>:"|?*\u2013\u2014]', "-", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def invoice_filename(number, date_str, client, title):
    """Nom de fichier : Invoice_N-<num>_<AAAA-MM-JJ>_<client>[-titre].pdf (date plate)."""
    dp = date_str.split("/")
    dkey = (dp[2] + "-" + dp[1] + "-" + dp[0]) if len(dp) == 3 else date_str.replace("/", "-")
    name = "Invoice_N-%s_%s_%s" % (number, dkey, safe_name(client))
    t = safe_name(" ".join(title)) if title else ""
    if t:
        name += "-" + t
    return name + ".pdf"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        # stdin en UTF-8 explicite : sur Windows, sys.stdin utilise l'encodage
        # console (cp1252) et corromprait les accents des noms de fichiers.
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        data = json.loads(raw) if raw.strip() else None
        if not isinstance(data, dict):
            print(json.dumps({"ok": False, "error": "aucune entrée JSON reçue"}))
            return
    except Exception as e:
        print(json.dumps({"ok": False, "error": "input JSON invalide: %s" % e}))
        return
    try:
        out_dir = os.path.join(ROOT, "data")
        os.makedirs(out_dir, exist_ok=True)
        out_name = os.path.basename(data.get("output") or invoice_filename(
            data["number"], data["date"], data["client_name"], data.get("title", [])))
        out_path = os.path.join(out_dir, out_name)
        total = build(data, out_path)
        preview = make_preview(out_path)
        print(json.dumps({"ok": True, "file": out_name,
                          "preview": (os.path.basename(preview) if preview else None),
                          "total": total}))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))


if __name__ == "__main__":
    main()
