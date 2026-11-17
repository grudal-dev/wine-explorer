"""Calculs du tableau de bord. Les visites sont des « visiteurs-jours » : l'empreinte change chaque jour."""

import re
from collections import Counter, defaultdict
from datetime import timedelta

from django.db.models import Avg, Count
from django.db.models.functions import ExtractHour
from django.utils import timezone

from .models import Event, PageView
from .tracking import source_family

PERIODS = {"1": "Aujourd'hui", "7": "7 jours", "30": "30 jours", "90": "90 jours", "365": "12 mois"}
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
BLINDTEST_ENDS = ("blindtest_won", "blindtest_lost", "blindtest_abandoned")


def normalize_path(path: str) -> str:
    return UUID_RE.sub("…", path)


def _pct(part, whole):
    return round(100 * part / whole) if whole else 0


def _delta(now, before):
    if not before:
        return None
    return round(100 * (now - before) / before)


def _ranked(counter: Counter, total: int, limit: int = 12):
    top = max(counter.values(), default=0)
    return [{"label": k or "—", "n": n, "pct": _pct(n, total), "bar": _pct(n, top)}
            for k, n in counter.most_common(limit)]


def period_bounds(key: str, today=None):
    today = today or timezone.localdate()
    days = int(key) if key in PERIODS else 30
    start = today - timedelta(days=days - 1)
    return start, today, start - timedelta(days=days), start - timedelta(days=1)


def _totals(start, end):
    pv = PageView.objects.filter(day__range=(start, end), status=200)
    per_visit = Counter(pv.values_list("day", "visitor"))
    visits = len(per_visit)
    views = sum(per_visit.values())
    bounces = sum(1 for n in per_visit.values() if n == 1)
    engaged = pv.filter(engaged_ms__isnull=False).aggregate(a=Avg("engaged_ms"))["a"]
    ev = Event.objects.filter(day__range=(start, end))
    games = ev.filter(name="blindtest_start").count()
    members = (pv.filter(user__isnull=False).values("user").distinct().count())
    return {"visits": visits, "views": views, "per_visit": round(views / visits, 1) if visits else 0,
            "bounce": _pct(bounces, visits), "engaged_s": round(engaged / 1000) if engaged else None,
            "games": games, "signups": ev.filter(name="signup").count(), "logins": ev.filter(name="login").count(),
            "members": members}


def dashboard(key: str = "30", today=None) -> dict:
    start, end, prev_start, prev_end = period_bounds(key, today)
    now, before = _totals(start, end), _totals(prev_start, prev_end)
    kpis = [
        {"label": "Visiteurs", "value": now["visits"], "delta": _delta(now["visits"], before["visits"]),
         "help": "visiteurs uniques par jour, additionnés"},
        {"label": "Pages vues", "value": now["views"], "delta": _delta(now["views"], before["views"])},
        {"label": "Pages par visite", "value": now["per_visit"],
         "delta": _delta(now["per_visit"], before["per_visit"])},
        {"label": "Rebond", "value": f"{now['bounce']} %", "delta": _delta(now["bounce"], before["bounce"]),
         "help": "visites d'une seule page", "inverse": True},
        {"label": "Temps moyen par page", "value": f"{now['engaged_s']} s" if now["engaged_s"] is not None else "—",
         "delta": _delta(now["engaged_s"] or 0, before["engaged_s"] or 0)},
        {"label": "Parties de blind test", "value": now["games"], "delta": _delta(now["games"], before["games"])},
        {"label": "Connexions", "value": now["logins"], "delta": _delta(now["logins"], before["logins"]),
         "help": "connexions à un compte (identifiant et mot de passe)"},
        {"label": "Membres actifs", "value": now["members"], "delta": _delta(now["members"], before["members"]),
         "help": "comptes différents ayant vu au moins une page connectés"},
        {"label": "Inscriptions", "value": now["signups"], "delta": _delta(now["signups"], before["signups"])},
    ]

    pv = PageView.objects.filter(day__range=(start, end), status=200)
    rows = list(pv.values_list("day", "visitor", "path", "is_entry", "source", "utm_campaign", "utm_source",
                               "utm_medium", "referrer_host", "device", "browser", "os", "browser_language",
                               "language"))
    visit_views = Counter((r[0], r[1]) for r in rows)
    entries = [r for r in rows if r[3]]
    visits = len(visit_views)

    # Événements par visite, pour relier une source à ce qu'elle produit (parties, victoires).
    events = list(Event.objects.filter(day__range=(start, end)).values_list("day", "visitor", "name", "props"))
    started = {(d, v) for d, v, n, _ in events if n == "blindtest_start"}
    won = {(d, v) for d, v, n, _ in events if n == "blindtest_won"}

    by_source = defaultdict(lambda: {"visits": 0, "views": 0, "bounces": 0, "players": 0, "winners": 0})
    for d, v, src in ((r[0], r[1], r[4]) for r in entries):
        s = by_source[src or "direct"]
        s["visits"] += 1
        s["views"] += visit_views[(d, v)]
        s["bounces"] += visit_views[(d, v)] == 1
        s["players"] += (d, v) in started
        s["winners"] += (d, v) in won
    top_visits = max((s["visits"] for s in by_source.values()), default=0)
    sources = sorted(
        ({"label": k, "family": source_family(k), "visits": s["visits"], "pct": _pct(s["visits"], visits),
          "bar": _pct(s["visits"], top_visits), "per_visit": round(s["views"] / s["visits"], 1),
          "bounce": _pct(s["bounces"], s["visits"]), "play": _pct(s["players"], s["visits"]),
          "win": _pct(s["winners"], s["visits"])} for k, s in by_source.items()),
        key=lambda x: -x["visits"])
    families = _ranked(Counter(source_family(r[4] or "direct") for r in entries), visits, 6)

    campaigns = Counter(" · ".join(x for x in (r[5], r[6], r[7]) if x) for r in entries if r[5] or r[6])

    # Pages : vues, visiteurs, temps et défilement moyens.
    page_stats = (pv.values("path").annotate(views=Count("id"), visitors=Count("visitor", distinct=True),
                                             engaged=Avg("engaged_ms"), scroll=Avg("scroll")))
    merged = defaultdict(lambda: {"views": 0, "visitors": 0, "eng": [], "scr": []})
    for p in page_stats:
        m = merged[normalize_path(p["path"])]
        m["views"] += p["views"]
        m["visitors"] += p["visitors"]
        if p["engaged"] is not None:
            m["eng"].append((p["engaged"], p["views"]))
        if p["scroll"] is not None:
            m["scr"].append((p["scroll"], p["views"]))

    def wavg(pairs, div=1):
        w = sum(n for _, n in pairs)
        return round(sum(x * n for x, n in pairs) / w / div) if w else None

    top_views = max((m["views"] for m in merged.values()), default=0)
    pages = sorted(({"label": k, "views": m["views"], "visitors": m["visitors"], "bar": _pct(m["views"], top_views),
                     "engaged_s": wavg(m["eng"], 1000), "scroll": wavg(m["scr"])} for k, m in merged.items()),
                   key=lambda x: -x["views"])[:25]

    # Courbe quotidienne.
    daily = {d: {"views": 0, "visitors": set()} for d in
             (start + timedelta(days=i) for i in range((end - start).days + 1))}
    for r in rows:
        daily[r[0]]["views"] += 1
        daily[r[0]]["visitors"].add(r[1])
    top_day = max((len(x["visitors"]) for x in daily.values()), default=0)
    logins_by_day = Counter(d for d, _, n, _ in events if n == "login")
    signups_by_day = Counter(d for d, _, n, _ in events if n == "signup")
    series = [{"day": d, "visitors": len(x["visitors"]), "views": x["views"], "logins": logins_by_day[d],
               "signups": signups_by_day[d], "h": _pct(len(x["visitors"]), top_day)} for d, x in daily.items()]

    hours_raw = dict(pv.annotate(h=ExtractHour("created_at")).values("h").annotate(n=Count("id")).values_list("h", "n"))
    top_h = max(hours_raw.values(), default=0)
    hours = [{"h": h, "n": hours_raw.get(h, 0), "pct": _pct(hours_raw.get(h, 0), top_h)} for h in range(24)]

    # Blind test : entonnoir et modes.
    bt_visits = {(r[0], r[1]) for r in rows if "/blind-test/" in r[2]}
    names = Counter(n for _, _, n, _ in events)
    finished = sum(names[n] for n in BLINDTEST_ENDS)
    funnel_top = max(len(bt_visits), 1)
    funnel = [
        {"label": "Visites du blind test", "n": len(bt_visits)},
        {"label": "Parties lancées", "n": names["blindtest_start"]},
        {"label": "Parties terminées", "n": finished},
        {"label": "Parties gagnées", "n": names["blindtest_won"]},
    ]
    for f in funnel:
        f["bar"] = min(100, _pct(f["n"], funnel_top))
    modes = Counter(p.get("mode", "?") for _, _, n, p in events if n == "blindtest_start")
    attempts = [p.get("attempts") for _, _, n, p in events if n == "blindtest_won" and p.get("attempts")]
    wines = Counter(p.get("wine", "?") for _, _, n, p in events if n in BLINDTEST_ENDS)
    wine_wins = Counter(p.get("wine", "?") for _, _, n, p in events if n == "blindtest_won")
    hardest = sorted(({"label": w, "n": n, "win": _pct(wine_wins[w], n)} for w, n in wines.items() if n >= 3),
                     key=lambda x: x["win"])[:10]

    recent_since = timezone.now() - timedelta(minutes=5)
    live = PageView.objects.filter(created_at__gte=recent_since).values("visitor").distinct().count()
    last = PageView.objects.select_related("user").order_by("-created_at")[:20]

    not_found = Counter(PageView.objects.filter(day__range=(start, end), status=404).values_list("path", flat=True))
    slow = (pv.values("path").annotate(ms=Avg("response_ms"), n=Count("id")).filter(n__gte=5).order_by("-ms")[:8])

    def counter(i, limit=10):
        return _ranked(Counter(r[i] for r in entries), len(entries), limit)

    return {
        "period": key if key in PERIODS else "30", "periods": PERIODS, "start": start, "end": end,
        "kpis": kpis, "series": series, "hours": hours, "sources": sources, "families": families,
        "campaigns": _ranked(campaigns, len(entries)),
        "referrers": _ranked(Counter(r[8] for r in entries if r[8]), len(entries), 10),
        "entry_pages": _ranked(Counter(normalize_path(r[2]) for r in entries), len(entries)),
        "pages": pages, "devices": counter(9, 4), "browsers": counter(10), "oses": counter(11),
        "languages": counter(12), "site_languages": counter(13, 4),
        "funnel": funnel, "modes": _ranked(modes, sum(modes.values()), 4),
        "avg_attempts": round(sum(attempts) / len(attempts), 1) if attempts else None,
        "hardest": hardest, "events": _ranked(names, sum(names.values()), 20),
        "live": live, "last": last, "not_found": _ranked(not_found, sum(not_found.values()), 10),
        "slow": [{"label": normalize_path(s["path"]), "ms": round(s["ms"]), "n": s["n"]} for s in slow],
    }
