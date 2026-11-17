"""Enregistrement des pages vues et des événements. Ne lève jamais d'exception vers la page servie."""

import hashlib
import logging
import re
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.utils import timezone

from .models import Event, PageView

log = logging.getLogger(__name__)

BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|archiver|facebookexternalhit|meta-externalagent|embedly|preview|monitor|uptime|"
    r"pingdom|lighthouse|pagespeed|headless|phantom|curl|wget|python|httpx|go-http|java/|okhttp|axios|node-fetch|"
    r"scrapy|semrush|ahrefs|mj12|dataforseo|bytespider|gptbot|claudebot|perplexity|ccbot",
    re.I,
)

# Navigateurs intégrés des applications : TikTok et Instagram n'envoient souvent aucun `Referer`,
# on les reconnaît à leur signature.
IN_APP = [
    ("tiktok", re.compile(r"musical_ly|BytedanceWebview|TikTok|trill_", re.I)),
    ("instagram", re.compile(r"Instagram", re.I)),
    ("facebook", re.compile(r"FBAN|FBAV|FB_IAB", re.I)),
    ("snapchat", re.compile(r"Snapchat", re.I)),
    ("linkedin", re.compile(r"LinkedInApp", re.I)),
    ("pinterest", re.compile(r"Pinterest", re.I)),
]

REFERRERS = [
    ("google", re.compile(r"(^|\.)google\.")),
    ("bing", re.compile(r"(^|\.)bing\.com$")),
    ("duckduckgo", re.compile(r"duckduckgo\.com$")),
    ("qwant", re.compile(r"qwant\.com$")),
    ("ecosia", re.compile(r"ecosia\.org$")),
    ("yahoo", re.compile(r"(^|\.)yahoo\.")),
    ("chatgpt", re.compile(r"chatgpt\.com$|openai\.com$")),
    ("perplexity", re.compile(r"perplexity\.ai$")),
    ("tiktok", re.compile(r"tiktok\.com$")),
    ("instagram", re.compile(r"instagram\.com$")),
    ("facebook", re.compile(r"facebook\.com$|fb\.me$|messenger\.com$")),
    ("x", re.compile(r"^t\.co$|twitter\.com$|(^|\.)x\.com$")),
    ("youtube", re.compile(r"youtube\.com$|youtu\.be$")),
    ("linkedin", re.compile(r"linkedin\.com$|lnkd\.in$")),
    ("reddit", re.compile(r"reddit\.com$")),
    ("pinterest", re.compile(r"pinterest\.")),
    ("whatsapp", re.compile(r"whatsapp\.com$")),
    ("e-mail", re.compile(r"mail\.|outlook\.|gmail")),
]

SEARCH = {"google", "bing", "duckduckgo", "qwant", "ecosia", "yahoo"}
SOCIAL = {"tiktok", "instagram", "facebook", "x", "youtube", "linkedin", "reddit", "pinterest", "snapchat",
          "whatsapp"}

SKIP_PREFIXES = ("/admin/", "/static/", "/media/", "/api/", "/i18n/", "/jsi18n/", "/en/jsi18n/", "/stats/",
                 "/robots.txt", "/sitemap.xml", "/favicon")


def _conf(name, default):
    return getattr(settings, name, default)


def is_bot(ua: str) -> bool:
    return not ua or bool(BOT_RE.search(ua))


def client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "")


def visitor_id(request, day) -> str:
    raw = f"{settings.SECRET_KEY}|{day.isoformat()}|{client_ip(request)}|{request.META.get('HTTP_USER_AGENT', '')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def parse_ua(ua: str) -> tuple[str, str, str]:
    """(appareil, navigateur, système), assez précis pour un tableau de bord."""
    if re.search(r"iPad|Tablet|Android(?!.*Mobile)", ua):
        device = "tablette"
    elif re.search(r"Mobi|iPhone|Android", ua):
        device = "mobile"
    else:
        device = "ordinateur"
    browser = "autre"
    for app, rx in IN_APP:
        if rx.search(ua):
            browser = f"{app} (appli)"
            break
    else:
        for name, rx in (("Edge", r"Edg/"), ("Opera", r"OPR/|Opera"), ("Samsung", r"SamsungBrowser"),
                         ("Firefox", r"Firefox|FxiOS"), ("Chrome", r"Chrome|CriOS"), ("Safari", r"Safari")):
            if re.search(rx, ua):
                browser = name
                break
    os_name = "autre"
    for name, rx in (("iOS", r"iPhone|iPad|iPod"), ("Android", r"Android"), ("Windows", r"Windows"),
                     ("macOS", r"Mac OS X|Macintosh"), ("ChromeOS", r"CrOS"), ("Linux", r"Linux")):
        if re.search(rx, ua):
            os_name = name
            break
    return device, browser, os_name


def referrer_host(request) -> str:
    """Domaine d'origine s'il est extérieur au site, sinon chaîne vide."""
    ref = request.META.get("HTTP_REFERER", "")
    if not ref:
        return ""
    host = (urlsplit(ref).hostname or "").lower().removeprefix("www.").removeprefix("m.").removeprefix("l.")
    own = request.get_host().split(":")[0].lower().removeprefix("www.")
    return "" if not host or host == own else host


def classify(utm_source: str, ua: str, host: str) -> str:
    if utm_source:
        return utm_source.lower()[:40]
    for app, rx in IN_APP:
        if rx.search(ua):
            return app
    if host:
        for name, rx in REFERRERS:
            if rx.search(host):
                return name
        return "autre site"
    return "direct"


def source_family(source: str) -> str:
    if source in SEARCH:
        return "recherche"
    if source in SOCIAL:
        return "réseaux sociaux"
    if source in {"direct", ""}:
        return "direct"
    return "autre"


def should_track(request) -> bool:
    if not _conf("ANALYTICS_ENABLED", True):
        return False
    if request.META.get("HTTP_DNT") == "1" or request.META.get("HTTP_SEC_GPC") == "1":
        return False  # refus exprimé par le navigateur
    if is_bot(request.META.get("HTTP_USER_AGENT", "")):
        return False
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.is_staff and not _conf("ANALYTICS_TRACK_STAFF", False):
        return False
    return True


def record_pageview(request, response, elapsed_ms: int) -> None:
    try:
        path = request.path
        if request.method != "GET" or path.startswith(SKIP_PREFIXES):
            return
        if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
            return  # fragment HTMX, pas une page
        if "text/html" not in response.get("Content-Type", "") or not (200 <= response.status_code < 300
                                                                        or response.status_code == 404):
            return
        if not should_track(request):
            return
        now = timezone.now()
        day = timezone.localdate(now)
        ua = request.META.get("HTTP_USER_AGENT", "")
        vid = visitor_id(request, day)
        g = request.GET
        host = referrer_host(request)
        is_entry = not PageView.objects.filter(day=day, visitor=vid).exists()
        device, browser, os_name = parse_ua(ua)
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        PageView.objects.create(
            day=day, visitor=vid, user=user, path=path[:300], query=request.META.get("QUERY_STRING", "")[:300],
            status=response.status_code, language=getattr(request, "LANGUAGE_CODE", "")[:8],
            browser_language=request.META.get("HTTP_ACCEPT_LANGUAGE", "").split(",")[0].split(";")[0][:16],
            is_entry=is_entry, source=classify(g.get("utm_source", ""), ua, host) if is_entry else "",
            referrer_host=host[:120], referrer=request.META.get("HTTP_REFERER", "")[:500] if host else "",
            utm_source=g.get("utm_source", "")[:80], utm_medium=g.get("utm_medium", "")[:80],
            utm_campaign=g.get("utm_campaign", "")[:120], utm_content=g.get("utm_content", "")[:120],
            device=device, browser=browser, os=os_name, response_ms=min(elapsed_ms, 600_000),
        )
        purge_if_due(day)
    except Exception:  # la mesure ne doit jamais casser une page
        log.exception("analytics: page vue non enregistrée")


def track(request, name: str, **props) -> None:
    """Événement métier (partie lancée, gagnée, inscription…). À appeler depuis les vues."""
    try:
        if not should_track(request):
            return
        day = timezone.localdate()
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        Event.objects.create(day=day, visitor=visitor_id(request, day), user=user, name=name[:40],
                             path=request.path[:300], props=props)
    except Exception:
        log.exception("analytics: événement %s non enregistré", name)


def record_engagement(request, path: str, engaged_ms: int, scroll: int | None) -> bool:
    """Complète la dernière page vue de ce visiteur (envoyé par le navigateur en quittant la page)."""
    if not should_track(request):
        return False
    day = timezone.localdate()
    since = timezone.now() - timedelta(hours=2)
    pv = (PageView.objects.filter(day=day, visitor=visitor_id(request, day), path=path[:300], created_at__gte=since)
          .order_by("-created_at").first())
    if pv is None:
        return False
    pv.engaged_ms = max(pv.engaged_ms or 0, min(engaged_ms, 4 * 3600 * 1000))
    if scroll is not None:
        pv.scroll = max(pv.scroll or 0, min(max(scroll, 0), 100))
    pv.save(update_fields=["engaged_ms", "scroll"])
    return True


_last_purge = {"day": None}


def purge(today=None) -> int:
    today = today or timezone.localdate()
    limit = today - timedelta(days=int(_conf("ANALYTICS_RETENTION_DAYS", 395)))
    n = PageView.objects.filter(day__lt=limit).delete()[0]
    return n + Event.objects.filter(day__lt=limit).delete()[0]


def purge_if_due(day) -> None:
    """Une purge par jour et par processus, sans tâche planifiée."""
    if _last_purge["day"] != day:
        _last_purge["day"] = day
        purge(day)
