"""Test de cohérence « niveau du vin » (commande de développement, ne modifie rien).

    python manage.py probe_level --seeds 3

Entraîne le modèle avec chaque prise en compte du niveau (voir train_embeddings.LEVEL_MODES) et
vérifie, sur plusieurs graines, des comparaisons qu'un amateur jugerait évidentes :
  - cas « niveau » : deux grands vins de même famille doivent être plus proches qu'un grand vin et
    un vin simple de la même région (Pauillac / Margaux > Margaux / Bordeaux Supérieur) ;
  - cas « garde-fous » : le style doit toujours primer sur le prix (Margaux reste plus proche d'un
    Bordeaux Supérieur que d'un Sauternes ou d'un Barolo).
"""

import json
import random

from django.core.management.base import BaseCommand

from . import train_embeddings as te

# (A, B, C, D) : on attend sim(A, B) > sim(C, D).
LEVEL_CASES = [
    ("pauillac-rouge", "margaux-rouge", "margaux-rouge", "bordeaux-superieur-rouge"),
    ("saint-julien-rouge", "pauillac-rouge", "pauillac-rouge", "bordeaux-superieur-rouge"),
    ("pomerol-rouge", "saint-emilion-grand-cru-rouge", "pomerol-rouge", "bordeaux-superieur-rouge"),
    ("pessac-leognan-rouge", "margaux-rouge", "pessac-leognan-rouge", "bordeaux-superieur-rouge"),
    ("vosne-romanee-rouge", "gevrey-chambertin-rouge", "vosne-romanee-rouge", "mercurey-rouge"),
    ("hermitage-rouge", "cote-rotie-rouge", "hermitage-rouge", "crozes-hermitage-rouge"),
    ("chateauneuf-du-pape-rouge", "gigondas-rouge", "chateauneuf-du-pape-rouge", "cotes-du-rhone-rouge"),
    ("moulin-a-vent-rouge", "morgon-rouge", "moulin-a-vent-rouge", "beaujolais-rouge"),
    ("brunello-di-montalcino-rouge", "vino-nobile-di-montepulciano-rouge", "brunello-di-montalcino-rouge", "chianti-classico-rouge"),
    ("sauternes-blanc", "tokaji-aszu", "sauternes-blanc", "monbazillac-blanc"),
    ("porto-vintage", "porto-late-bottled-vintage", "porto-vintage", "porto-ruby"),
]
GUARD_CASES = [
    ("margaux-rouge", "bordeaux-superieur-rouge", "margaux-rouge", "sauternes-blanc"),
    ("margaux-rouge", "pauillac-rouge", "margaux-rouge", "barolo-rouge"),
    ("pauillac-rouge", "saint-estephe-rouge", "pauillac-rouge", "hermitage-rouge"),
    ("bordeaux-superieur-rouge", "margaux-rouge", "bordeaux-superieur-rouge", "beaujolais-rouge"),
    ("cotes-du-rhone-rouge", "chateauneuf-du-pape-rouge", "cotes-du-rhone-rouge", "beaujolais-rouge"),
    ("chablis-blanc", "meursault-blanc", "chablis-blanc", "pauillac-rouge"),
    ("muscadet-sevre-et-maine-blanc", "picpoul-de-pinet-blanc", "muscadet-sevre-et-maine-blanc", "corton-charlemagne-blanc"),
    ("gevrey-chambertin-rouge", "chambolle-musigny-rouge", "gevrey-chambertin-rouge", "pauillac-rouge"),
]


class Command(BaseCommand):
    help = "Compare les prises en compte du niveau (prix, garde) sur des cas de cohérence."

    def add_arguments(self, parser):
        parser.add_argument("--seeds", type=int, default=3)
        parser.add_argument("--modes", default=",".join(te.LEVEL_MODES))
        parser.add_argument("--json", default="", help="Écrire le détail dans ce fichier.")

    def handle(self, *args, seeds, modes, json: str = "", **options):
        import numpy as np
        import torch
        from django.utils import translation

        from apps.explorer.graph import full_graph

        translation.activate("fr")
        cmd = te.Command()
        graph = full_graph()
        base_ids = sorted(graph.nodes)
        base_types = [graph.nodes[i].type for i in base_ids]
        base_index = {n: i for i, n in enumerate(base_ids)}
        base_edges = [(base_index[e.source], base_index[e.target], e.kind, te.edge_weight(e))
                      for e in graph.edges if not (e.kind == "molecule" and e.tier == "universal")]
        missing = {x for case in LEVEL_CASES + GUARD_CASES for x in case if f"profile:{x}" not in base_index}
        if missing:
            self.stderr.write(f"Vins inconnus, cas ignorés : {sorted(missing)}")
        cases = {"niveau": [c for c in LEVEL_CASES if not set(c) & missing],
                 "garde-fou": [c for c in GUARD_CASES if not set(c) & missing]}

        report = {}
        for mode in modes.split(","):
            ids, types, edges = list(base_ids), list(base_types), list(base_edges)
            index = dict(base_index)
            if mode in ("nodes", "both"):
                cmd._add_level_nodes(ids, index, types, edges)
            aux = cmd._profile_targets(ids, index)
            aux["level_on"] = mode in ("aux", "both")
            sims = []
            for k in range(seeds):
                random.seed(te.SEED + k)
                z, _ = cmd._train(torch, ids, types, edges, aux, te.EPOCHS, te.SEED + k)
                z = z.numpy()
                sims.append(lambda a, b, z=z: float(z[index[f"profile:{a}"]] @ z[index[f"profile:{b}"]]))
            rows = {}
            for group, lst in cases.items():
                rows[group] = []
                for a, b, c, d in lst:
                    gaps = [s(a, b) - s(c, d) for s in sims]
                    rows[group].append({"case": f"{a} ~ {b}  >  {c} ~ {d}",
                                        "ab": np.mean([s(a, b) for s in sims]), "cd": np.mean([s(c, d) for s in sims]),
                                        "gap": float(np.mean(gaps)), "ok": sum(g > 0 for g in gaps), "n": len(gaps)})
            report[mode] = rows
            ok = {g: sum(r["ok"] for r in rs) for g, rs in rows.items()}
            tot = {g: sum(r["n"] for r in rs) for g, rs in rows.items()}
            self.stdout.write(self.style.SUCCESS(
                f"[{mode}] niveau {ok['niveau']}/{tot['niveau']} · garde-fous {ok['garde-fou']}/{tot['garde-fou']}"))
            for group, rs in rows.items():
                for r in rs:
                    self.stdout.write(f"   {group:9} {r['ok']}/{r['n']}  {r['ab']:.3f} vs {r['cd']:.3f}  {r['case']}")
        if json:
            with open(json, "w", encoding="utf-8") as fh:
                fh.write(__import__("json").dumps(report, ensure_ascii=False, indent=1, default=float))
