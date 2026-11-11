"""« Chaud-froid » : retrouver un vin mystère à la manière de Cémantix.

Le joueur propose n'importe quelle entité du graphe : un arôme, un cépage, une région, une
appellation, une molécule, un autre vin. Chaque proposition reçoit une « température », la
proximité (cosinus × 100) entre elle et le vin mystère dans l'espace appris par le réseau de
graphe (apps/embeddings), et un rang parmi toutes les entités. On gagne en proposant le vin.

Rien n'est stocké en base : la partie vit dans la session (vin mystère compris, donc jamais
envoyé au navigateur avant la fin).
"""

from __future__ import annotations

import hashlib
import random
from datetime import date

from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop

from apps.catalog.models import WineProfile
from apps.embeddings.nodes import describe
from apps.embeddings.space import Space
from apps.explorer.graph import search_nodes

SESSION_KEY = "hotcold"
TOP = 100  # les 100 entités les plus proches du vin ont droit à une jauge de rang
WARM_SHARE = 0.4  # « tiède » : dans les 40 % d'entités les plus proches

# (rang maximal, émoji, libellé) du plus chaud au plus froid ; la suite dépend du signe du cosinus.
BANDS = [(5, "😱", gettext_noop("brûlant")), (20, "🔥", gettext_noop("très chaud")), (TOP, "🥵", gettext_noop("chaud"))]


class HotColdError(ValueError):
    pass


def _playable(sp: Space) -> list[str]:
    return sorted(p for p in WineProfile.objects.values_list("slug", flat=True) if f"profile:{p}" in sp)


def daily_secret(day: date, sp: Space) -> str:
    slugs = _playable(sp)
    if not slugs:
        raise HotColdError(_("Aucun vin jouable : lancez train_embeddings."))
    # Sel différent de celui du blind test : les deux défis du jour ne portent pas sur le même vin.
    digest = hashlib.sha256(f"terroirs-chaud-froid-{day.isoformat()}".encode()).hexdigest()
    return slugs[int(digest, 16) % len(slugs)]


def new_state(mode: str, day: date, sp: Space, exclude: str = "") -> dict:
    if mode == "daily":
        secret = daily_secret(day, sp)
    else:
        slugs = [s for s in _playable(sp) if s != exclude] or _playable(sp)
        if not slugs:
            raise HotColdError(_("Aucun vin jouable : lancez train_embeddings."))
        secret = random.choice(slugs)
    return {"mode": mode, "day": day.isoformat(), "secret": secret, "guesses": [], "over": ""}


def current_state(session, today: date, sp: Space) -> dict:
    """La partie en cours ; à défaut, ou si le défi du jour a changé, le défi d'aujourd'hui."""
    state = session.get(SESSION_KEY)
    stale = (not state or f"profile:{state.get('secret')}" not in sp
             or (state.get("mode") == "daily" and state.get("day") != today.isoformat()))
    if stale:
        state = new_state("daily", today, sp)
        session[SESSION_KEY] = state
    return state


def resolve(text: str, choice: str, sp: Space) -> str:
    """Identifiant de l'entité proposée : celle choisie dans la liste, sinon la meilleure pour la saisie."""
    if choice and choice in sp:
        return choice
    text = (text or "").strip()[:80]
    if not text:
        raise HotColdError(_("Proposez un arôme, un cépage, une région, une appellation, une molécule ou un vin."))
    for hit in search_nodes(text, limit=8):
        if hit["id"] in sp:
            return hit["id"]
    raise HotColdError(_("« %(text)s » n'est pas dans le graphe.") % {"text": text})


def score(secret_id: str, node_id: str, sp: Space) -> dict:
    """Température, rang et émoji d'une proposition."""
    info = describe(node_id) or {"id": node_id, "label": node_id, "type": "", "type_label": ""}
    if node_id == secret_id:
        return {**info, "temperature": 100.0, "rank": 0, "emoji": "🥳", "band": _("trouvé"), "found": True,
                "gauge": 100}
    sim = sp.similarity(secret_id, node_id) or 0.0
    rank = sp.ranks(secret_id).get(node_id, len(sp.ids))
    for limit, emoji, label in BANDS:
        if rank <= limit:
            band = (emoji, _(label))
            break
    else:
        if rank <= WARM_SHARE * len(sp.ids):
            band = ("😎", _("tiède"))
        else:
            band = ("🧊", _("froid")) if sim > 0 else ("🥶", _("glacial"))
    return {
        **info, "temperature": round(100 * sim, 1), "rank": rank, "emoji": band[0], "band": band[1],
        "found": False, "gauge": max(0, round(100 * (TOP - rank + 1) / TOP)) if rank <= TOP else 0,
    }


def play(state: dict, text: str, choice: str, sp: Space) -> dict:
    """Ajoute une proposition à la partie et rend son évaluation."""
    if state["over"]:
        raise HotColdError(_("La partie est terminée."))
    node_id = resolve(text, choice, sp)
    if node_id in state["guesses"]:
        label = (describe(node_id) or {}).get("label", node_id)
        raise HotColdError(_("Vous avez déjà proposé « %(label)s ».") % {"label": label})
    state["guesses"].append(node_id)
    result = score(f"profile:{state['secret']}", node_id, sp)
    if result["found"]:
        state["over"] = "won"
    return result


def board(state: dict, sp: Space) -> dict:
    """Tout ce que la page affiche : propositions classées, dernière proposition, solution si finie."""
    secret_id = f"profile:{state['secret']}"
    rows = []
    for n, node_id in enumerate(state["guesses"], start=1):
        rows.append({**score(secret_id, node_id, sp), "n": n})
    last = rows[-1] if rows else None
    ranked = sorted(rows, key=lambda r: (-r["temperature"], r["n"]))
    out = {"rows": ranked, "last": last, "count": len(rows), "over": state["over"], "mode": state["mode"],
           "best": ranked[0] if ranked else None, "top": TOP, "total": len(sp.ids) - 1}
    if state["over"]:
        out["answer"] = describe(secret_id)
        guessed = set(state["guesses"])
        out["closest"] = [
            {**score(secret_id, other, sp), "guessed": other in guessed}
            for other, _sim in sp.neighbours(secret_id, k=15)
        ]
    return out
