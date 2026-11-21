"""Dessins SVG de la page Comparer : jauge de proximité, toile de la bouche, face-à-face des arômes.

Les couleurs des deux vins viennent des variables CSS `--duel-a` et `--duel-b` ; tout le reste
reprend la palette du site. Les SVG sont produits côté serveur (aucune bibliothèque de dessin) et
les textes venus de la base sont échappés.
"""

from __future__ import annotations

import math
from html import escape

from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from .compare import Nose

INK, INK2, INK3 = "#23262F", "#50545E", "#686C75"
PAPER, RULE, TRACK = "#F8F8F4", "#D4D4CB", "#E7E6DE"
A, B = "var(--duel-a)", "var(--duel-b)"
SANS, SERIF = "Inter, system-ui, sans-serif", "Fraunces, Georgia, serif"

R = {3: 9, 2: 6.5, 1: 4.5}
FW = {3: 600, 2: 500, 1: 400}
FC = {3: INK, 2: INK, 1: INK2}


def _pt(cx, cy, r, deg):
    a = math.radians(deg)
    return cx + r * math.sin(a), cy - r * math.cos(a)


def _arc(cx, cy, r, a0, a1):
    x0, y0 = _pt(cx, cy, r, a0)
    x1, y1 = _pt(cx, cy, r, a1)
    return f"M{x0:.2f} {y0:.2f} A{r:.2f} {r:.2f} 0 {1 if a1 - a0 > 180 else 0} 1 {x1:.2f} {y1:.2f}"


def _stroke(d, color, w, cap="round"):
    return f'<path d="{d}" fill="none" style="stroke: {color}" stroke-width="{w:.2f}" stroke-linecap="{cap}"/>'


def _text(x, y, s, size, *, anchor="start", weight=400, color=INK, family=SANS, italic=False, spacing=None):
    extra = ' font-style="italic"' if italic else ""
    extra += f' letter-spacing="{spacing}"' if spacing else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-family="{family}" font-size="{size}" '
            f'font-weight="{weight}"{extra} style="fill: {color}">{escape(s)}</text>')


def _svg(body, w, h, label=None, cls=""):
    role = f'role="img" aria-label="{escape(label)}"' if label else 'aria-hidden="true"'
    klass = f' class="{cls}"' if cls else ""
    return mark_safe(f'<svg {role}{klass} viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}">{body}</svg>')


# ── jauge de proximité ────────────────────────────────────────────────────
def gauge(value: int, word: str, size: int = 300):
    r, sw = size * 0.42, size * 0.05
    cx, cy = size / 2, r + sw
    h = cy + sw * 0.6
    p = [_stroke(_arc(cx, cy, r, -90, 90), TRACK, sw)]
    if value:
        p.append(_stroke(_arc(cx, cy, r, -90, -90 + 1.8 * value), INK, sw))
    for t in (0, 25, 50, 75, 100):
        x0, y0 = _pt(cx, cy, r - sw * 1.3, -90 + 1.8 * t)
        x1, y1 = _pt(cx, cy, r - sw * 2.0, -90 + 1.8 * t)
        p.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" style="stroke: {INK3}" stroke-width="1"/>')
    mx, my = _pt(cx, cy, r, -90 + 1.8 * value)
    k = sw * 0.9
    p.append(f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="{k + 3:.1f}" style="fill: {PAPER}"/>')
    p.append(f'<path d="M{mx:.1f} {my - k:.1f} A{k:.1f} {k:.1f} 0 0 0 {mx:.1f} {my + k:.1f} Z" style="fill: {A}"/>')
    p.append(f'<path d="M{mx:.1f} {my - k:.1f} A{k:.1f} {k:.1f} 0 0 1 {mx:.1f} {my + k:.1f} Z" style="fill: {B}"/>')
    p.append(_text(cx, cy - size * 0.09, str(value), round(size * 0.24), anchor="middle", weight=600, family=SERIF))
    p.append(_text(cx, cy - size * 0.005, word.upper(), round(size * 0.05), anchor="middle", weight=600, color=INK2, spacing="2.5"))
    label = _("Proximité %(value)s sur 100 : %(word)s") % {"value": value, "word": word.lower()}
    return _svg("".join(p), size, h, label, "duel-gauge")


# ── toile de la bouche (radar) ───────────────────────────────────────────
def radar(mouth: list[dict], name_a: str, name_b: str, size: int = 340):
    """Une seule toile pour les deux vins : un axe par critère (0 à 5), A et B superposés."""
    n = len(mouth)
    pad_x, pad_y = 92, 42
    w, h = size + 2 * pad_x, size + 2 * pad_y
    cx, cy, r = w / 2, h / 2, size / 2
    angles = [360 * k / n for k in range(n)]
    p = []
    for level in range(1, 6):  # anneaux 1 à 5
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (_pt(cx, cy, r * level / 5, a) for a in angles))
        p.append(f'<polygon points="{pts}" fill="{PAPER if level == 5 else "none"}" '
                 f'style="stroke: {RULE if level == 5 else TRACK}" stroke-width="1"/>')
    for a in angles:
        x, y = _pt(cx, cy, r, a)
        p.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x:.1f}" y2="{y:.1f}" style="stroke: {TRACK}" stroke-width="1"/>')
    for key, color in (("a", A), ("b", B)):
        pts = [_pt(cx, cy, r * m[key] / 5, a) for m, a in zip(mouth, angles, strict=True)]
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        p.append(f'<polygon points="{poly}" style="fill: {color}; stroke: {color}" fill-opacity=".16" '
                 f'stroke-width="2.5" stroke-linejoin="round"/>')
        p += [f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" style="fill: {color}"/>' for x, y in pts]
    for m, a in zip(mouth, angles, strict=True):
        x, y = _pt(cx, cy, r + 22, a)
        anchor = "middle" if a in (0, 180) else ("start" if a < 180 else "end")
        dy = -6 if a == 0 else (14 if a == 180 else -2)
        p.append(_text(x, y + dy, m["label"], 15, anchor=anchor, weight=600))
        p.append(f'<text x="{x:.1f}" y="{y + dy + 19:.1f}" text-anchor="{anchor}" font-family="{SERIF}" font-weight="600" '
                 f'font-size="15"><tspan style="fill: {A}">{m["a"]}</tspan><tspan dx="4" style="fill: {RULE}">/</tspan>'
                 f'<tspan dx="4" style="fill: {B}">{m["b"]}</tspan></text>')
    label = _("En bouche, sur 5 : ") + " ; ".join(
        _("%(name)s %(a)s pour %(wa)s, %(b)s pour %(wb)s") % {"name": m["label"].lower(), "a": m["a"], "wa": name_a,
                                                                "b": m["b"], "wb": name_b} for m in mouth)
    return _svg("".join(p), w, h, label, "duel-radar")


# ── taches de vin ─────────────────────────────────────────────────────────
def _blob(cx, cy, rx, ry, seed, wobble=0.07, n=14):
    pts = []
    for k in range(n):
        t = 2 * math.pi * k / n
        f = 1 + wobble * (math.sin(3 * t + seed) * 0.6 + math.sin(5 * t + seed * 1.7) * 0.4)
        pts.append((cx + rx * f * math.cos(t), cy + ry * f * math.sin(t)))
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f} "
    for i in range(n):  # Catmull-Rom → Bézier : contour fermé et lisse
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f} "
    return d + "Z"


def _stain(cx, cy, rx, ry, color, seed):
    """Une tache aquarellée et l'anneau laissé par le pied du verre."""
    return "".join([
        f'<path d="{_blob(cx, cy, rx, ry, seed, 0.09)}" style="fill: {color}; fill-opacity: 0.07"/>',
        f'<path d="{_blob(cx + rx * 0.025, cy - ry * 0.03, rx * 0.9, ry * 0.88, seed + 1.3, 0.07)}" style="fill: {color}; fill-opacity: 0.06"/>',
        f'<path d="{_blob(cx, cy + ry * 0.02, rx * 0.947, ry * 0.937, seed + 0.6, 0.05, 18)}" fill="none" style="stroke: {color}; stroke-opacity: 0.28" stroke-width="2.2"/>',
        f'<path d="{_blob(cx - rx * 0.013, cy, rx * 0.967, ry * 0.963, seed + 2.2, 0.04, 18)}" fill="none" style="stroke: {color}; stroke-opacity: 0.14" stroke-width="4.5"/>',
    ])


def _pill(x, y, label, size=16, h=34):
    w = max(96, len(label) * size * 0.56 + 30)
    return (w, f'<rect x="{x - w / 2:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" height="{h}" rx="{h / 2}" style="fill: #FFFFFF; stroke: {RULE}"/>'
               + _text(x, y + size * 0.34, label, size, anchor="middle", weight=500))


def _nose_label(nose: Nose, name_a: str, name_b: str) -> str:
    def names(items):
        return ", ".join(x.name for x in items) or "—"
    return (_("Au nez. Seulement %(a)s : %(only_a)s. En commun : %(common)s. Seulement %(b)s : %(only_b)s.")
            % {"a": name_a, "b": name_b, "only_a": names(nose.only_a), "common": names(nose.common),
               "only_b": names(nose.only_b)})


def nose_wide(nose: Nose, name_a: str, name_b: str):
    """Ordinateur : les deux vins face à face, chacun dans sa tache ; le commun au centre."""
    W = 1040
    cx = W / 2
    xa, xb = 330, W - 330
    fs = {3: 22, 2: 18, 1: 15}
    step_a, step_b, step_c = 62, 56, 54
    rows = max(len(nose.only_a) * step_a, len(nose.only_b) * step_b, len(nose.common) * step_c, 3 * step_c)
    top = 60
    mid = top + 30 + rows / 2
    H = mid + rows / 2 + 120
    p = [_stain(cx - 215, mid, 300, max(190, rows / 2 + 80), A, 0.4),
         _stain(cx + 215, mid, 300, max(190, rows / 2 + 80), B, 2.1)]
    head_y = mid - rows / 2 - 20
    p.append(_text(xa + 10, head_y, name_a.upper(), 12, anchor="end", weight=600, color=A, spacing="1.8"))
    p.append(_text(xb - 10, head_y, name_b.upper(), 12, anchor="start", weight=600, color=B, spacing="1.8"))

    def ys(n, step):
        return [mid - (n - 1) * step / 2 + i * step for i in range(n)]

    ya = dict(zip((x.slug for x in nose.only_a), ys(len(nose.only_a), step_a), strict=True))
    yb = dict(zip((x.slug for x in nose.only_b), ys(len(nose.only_b), step_b), strict=True))
    # liens « arômes voisins » : un trait pointillé qui passe sous le centre
    bottom = mid + rows / 2
    for k, (sa, sb) in enumerate(nose.neighbours):
        y1, y2 = ya[sa], yb[sb]
        dip = bottom + 40 + 22 * k
        p.append(f'<path d="M{xa + 16} {y1:.1f} C{xa + 150} {dip:.1f}, {xb - 150} {dip + 20:.1f}, {xb - 16} {y2:.1f}" fill="none" '
                 f'style="stroke: {INK3}" stroke-width="1" stroke-dasharray="2 5" stroke-linecap="round"/>')
    if nose.neighbours:
        p.append(_text(cx, bottom + 92 + 22 * (len(nose.neighbours) - 1), _("arômes voisins"), 14, anchor="middle",
                       color=INK2, family=SERIF, italic=True))
    for x in nose.only_a:
        y = ya[x.slug]
        p.append(f'<circle cx="{xa}" cy="{y:.1f}" r="{R[x.a]}" style="fill: {A}"/>')
        p.append(_text(xa - 22, y + fs[x.a] * 0.35, x.name, fs[x.a], anchor="end", weight=FW[x.a], color=FC[x.a]))
    for x in nose.only_b:
        y = yb[x.slug]
        p.append(f'<circle cx="{xb}" cy="{y:.1f}" r="{R[x.b]}" style="fill: {B}"/>')
        p.append(_text(xb + 22, y + fs[x.b] * 0.35, x.name, fs[x.b], anchor="start", weight=FW[x.b], color=FC[x.b]))
    if nose.common:
        p.append(_text(cx, head_y, _("EN COMMUN"), 12, anchor="middle", weight=600, color=INK3, spacing="1.8"))
        for x, y in zip(nose.common, ys(len(nose.common), step_c), strict=True):
            w, pill = _pill(cx, y, x.name)
            p.append(f'<line x1="{xa + 40}" y1="{y:.1f}" x2="{cx - w / 2 - 12:.1f}" y2="{y:.1f}" style="stroke: {A}" stroke-width="1.2" opacity="0.45"/>')
            p.append(f'<line x1="{cx + w / 2 + 12:.1f}" y1="{y:.1f}" x2="{xb - 40}" y2="{y:.1f}" style="stroke: {B}" stroke-width="1.2" opacity="0.45"/>')
            p.append(f'<circle cx="{xa + 40}" cy="{y:.1f}" r="{R[x.a] * 0.75:.1f}" style="fill: {A}"/>')
            p.append(f'<circle cx="{xb - 40}" cy="{y:.1f}" r="{R[x.b] * 0.75:.1f}" style="fill: {B}"/>')
            p.append(pill)
    else:
        p.append(_text(cx, mid + 5, _("aucun arôme en commun"), 15, anchor="middle", color=INK2, family=SERIF, italic=True))
    return _svg("".join(p), W, H, _nose_label(nose, name_a, name_b), "duel-nose duel-nose--wide")


def nose_narrow(nose: Nose, name_a: str, name_b: str):
    """Téléphone : le vin A en haut, le vin B en bas ; le commun là où les taches se touchent."""
    W = 346
    cx = W / 2
    fs = {3: 22, 2: 18, 1: 15}
    step = 38

    def column(items, side, y0):
        out = []
        for k, x in enumerate(items):
            i = getattr(x, side)
            y = y0 + k * step
            r = R[i] * 0.85
            gap = 2 * r + 9
            width = len(x.name) * fs[i] * 0.52 + gap
            x0 = cx - width / 2
            out.append(f'<circle cx="{x0 + r:.1f}" cy="{y - fs[i] * 0.33:.1f}" r="{r:.1f}" style="fill: {A if side == "a" else B}"/>')
            out.append(_text(x0 + gap, y, x.name, fs[i], weight=FW[i], color=FC[i]))
        return out

    # rangées d'étiquettes communes, autant que la largeur en tient
    rows, row, used = [], [], 0
    for x in nose.common:
        w = max(96, len(x.name) * 15 * 0.56 + 26)
        if row and used + w + 10 > W:
            rows.append(row)
            row, used = [], 0
        row.append((x, w))
        used += w + 10
    if row:
        rows.append(row)

    ha = 70 + max(1, len(nose.only_a)) * step
    hc = 40 + max(1, len(rows)) * 44
    hb = 70 + max(1, len(nose.only_b)) * step
    H = ha + hc + hb + 40
    p = [_stain(cx, ha / 2 + 18, 178, ha / 2 + 40, A, 0.4),
         _stain(cx, ha + hc + hb / 2 - 10, 178, hb / 2 + 40, B, 2.1)]
    p.append(_text(cx, 40, name_a.upper(), 11, anchor="middle", weight=600, color=A, spacing="1.8"))
    p += column(nose.only_a, "a", 80)
    yc = ha + 22
    p.append(_text(cx, yc, _("EN COMMUN"), 11, anchor="middle", weight=600, color=INK3, spacing="1.8"))
    if rows:
        for r_i, r in enumerate(rows):
            y = yc + 30 + r_i * 44
            total = sum(w for _x, w in r) + 10 * (len(r) - 1)
            x = cx - total / 2
            for item, w in r:
                p.append(_pill(x + w / 2, y, item.name, 15, 30)[1])
                x += w + 10
    else:
        p.append(_text(cx, yc + 32, _("aucun arôme en commun"), 14, anchor="middle", color=INK2, family=SERIF, italic=True))
    yb0 = ha + hc
    p.append(_text(cx, yb0 + 40, name_b.upper(), 11, anchor="middle", weight=600, color=B, spacing="1.8"))
    p += column(nose.only_b, "b", yb0 + 80)
    if nose.neighbours:
        by = {x.slug: x.name for x in nose.only_a + nose.only_b}
        pairs = " ; ".join(f"{by[a]} ≈ {by[b]}" for a, b in nose.neighbours)
        p.append(_text(cx, H - 6, _("Arômes voisins : %(pairs)s") % {"pairs": pairs}, 13, anchor="middle",
                       color=INK2, family=SERIF, italic=True))
    return _svg("".join(p), W, H, _nose_label(nose, name_a, name_b), "duel-nose duel-nose--narrow")
