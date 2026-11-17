import csv
import json

from django.contrib import admin
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.template.response import TemplateResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import stats
from .models import PageView
from .tracking import IGNORE_COOKIE, forget_device, record_engagement, set_ignore_cookie


def dashboard(request):
    """Tableau de bord, servi dans l'administration (réservé à l'équipe)."""
    context = {**admin.site.each_context(request), "title": "Statistiques de visite",
               "ignored": request.COOKIES.get(IGNORE_COOKIE) == "1",
               **stats.dashboard(request.GET.get("p", "30"))}
    return TemplateResponse(request, "admin/analytics/dashboard.html", context)


def export_csv(request):
    start, end, *_ = stats.period_bounds(request.GET.get("p", "30"))
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="pages-vues-{start}-{end}.csv"'
    response.write("﻿")  # Excel reconnaît l'UTF-8
    fields = ["created_at", "visitor", "path", "query", "status", "is_entry", "source", "referrer_host",
              "utm_source", "utm_medium", "utm_campaign", "utm_content", "device", "browser", "os",
              "browser_language", "language", "response_ms", "engaged_ms", "scroll"]
    writer = csv.writer(response, delimiter=";")
    writer.writerow(fields)
    for row in PageView.objects.filter(day__range=(start, end)).order_by("created_at").values_list(*fields).iterator():
        writer.writerow(row)
    return response


@csrf_exempt  # envoyé par navigator.sendBeacon ; ne modifie qu'une durée et un défilement
@require_POST
def engagement(request):
    if len(request.body) > 1024:
        return HttpResponseBadRequest()
    try:
        data = json.loads(request.body or b"{}")
        path = str(data["p"])[:300]
        ms = int(data["t"])
        scroll = int(data["s"]) if data.get("s") is not None else None
    except (ValueError, KeyError, TypeError):
        return HttpResponseBadRequest()
    record_engagement(request, path, ms, scroll)
    return HttpResponse(status=204)


def ignore_device(request):
    """`/stats/ne-pas-me-compter/` : à ouvrir une fois dans chaque navigateur de l'équipe (téléphone, appli…)."""
    if request.method == "POST":
        if request.POST.get("action") == "compter":
            response = render(request, "analytics/ignore.html", {"ignored": False, "done": True})
            response.delete_cookie(IGNORE_COOKIE)
            return response
        removed = forget_device(request)
        response = render(request, "analytics/ignore.html", {"ignored": True, "done": True, "removed": removed})
        set_ignore_cookie(response, request)
        return response
    return render(request, "analytics/ignore.html", {"ignored": request.COOKIES.get(IGNORE_COOKIE) == "1"})
