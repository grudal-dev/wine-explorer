"""Référentiel des cépages : un cépage n'existe qu'une fois, ses noms locaux sont des synonymes.

Quand deux fiches se révèlent être le même cépage (Rolle et Vermentino, Nielluccio et
Sangiovese), la fiche qui disparaît est *fusionnée* dans celle qui reste : ses encépagements
passent sur la fiche gardée (parts additionnées si un vin portait les deux), son nom rejoint
les synonymes, puis elle est supprimée. Son ancienne adresse redirige vers la fiche gardée
(voir `grape_detail`).

Les fonctions prennent les classes de modèles en paramètre pour servir aussi bien dans une
migration (modèles historiques) que dans `load_seed`.
"""

from __future__ import annotations

# Fusions déjà faites, ancien slug → slug gardé. Rejouées par la migration 0002.
MERGED = {
    "rolle": "vermentino",       # Rolle (Provence), Vermentinu (Corse) : même cépage
    "nielluccio": "sangiovese",  # Nielluccio (Corse) : identité génétique avec le Sangiovese
}


def merge_grape(Grape, ProfileGrape, old, target) -> None:
    """Fusionne la fiche `old` dans `target` (deux instances de Grape), puis supprime `old`."""
    if old.pk == target.pk:
        return
    for link in ProfileGrape.objects.filter(grape=old):
        twin = ProfileGrape.objects.filter(profile_id=link.profile_id, grape=target).first()
        if twin:
            twin.share += link.share
            twin.save(update_fields=["share"])
            link.delete()
        else:
            link.grape = target
            link.save(update_fields=["grape"])
    synonyms = list(target.synonyms or [])
    for label in [old.name, *(old.synonyms or [])]:
        if label != target.name and label not in synonyms:
            synonyms.append(label)
    target.synonyms = synonyms
    target.save(update_fields=["synonyms"])
    old.delete()


def apply_known_merges(Grape, ProfileGrape) -> int:
    """Rejoue `MERGED` sur une base existante. Si la fiche gardée n'existe pas encore,
    l'ancienne est simplement renommée (elle prendra son vrai nom au prochain `load_seed`)."""
    done = 0
    for old_slug, new_slug in MERGED.items():
        old = Grape.objects.filter(slug=old_slug).first()
        if old is None:
            continue
        target = Grape.objects.filter(slug=new_slug).first()
        if target is None:
            old.synonyms = [*(old.synonyms or []), old.name]
            old.slug, old.name = new_slug, new_slug.replace("-", " ").title()
            old.save(update_fields=["slug", "name", "synonyms"])
        else:
            merge_grape(Grape, ProfileGrape, old, target)
        done += 1
    return done
