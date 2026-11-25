"""Apprend une représentation vectorielle de chaque entité du graphe (commande de développement).

    python manage.py train_embeddings             # évalue, entraîne sur tout le graphe, écrit le fichier
    python manage.py train_embeddings --evaluate  # évaluation seule (liens masqués), n'écrit rien

Demande PyTorch et scikit-learn (`pip install torch scikit-learn`), qui ne sont PAS des
dépendances du site : le résultat, apps/embeddings/data/embeddings.json, est versionné et le
site se contente de le lire. À relancer quand les données changent (nouveaux vins, nouvelles
règles moléculaires).

Le modèle
---------
Un réseau de neurones sur graphe relationnel (R-GCN, Schlichtkrull et al. 2018) à deux couches :
chaque nœud part d'un vecteur appris, puis agrège deux fois les vecteurs de ses voisins, avec
une transformation propre à chaque type de relation (profil → cépage, profil → arôme, appellation
→ région…) et à chaque sens. Les poids des arêtes (part d'encépagement, intensité de l'arôme,
force du lien moléculaire) pondèrent l'agrégation.

Deux objectifs appris ensemble :
  1. prédiction de liens (décodeur DistMult, échantillonnage négatif) : deux nœuds reliés
     doivent avoir des vecteurs compatibles, deux nœuds tirés au hasard non ;
  2. pour les vins, retrouver la couleur, le style et la structure en bouche (corps, acidité,
     tanins, sucrosité) à partir du vecteur : la bouche compte autant que le nez.

Évaluation honnête : 15 % des liens vin → arôme, vin → cépage et vin → molécule sont masqués
pendant un entraînement, et cela six fois de suite avec des liens différents ; on mesure
si le modèle les classe devant des liens tirés au
hasard (AUC), puis si Le Nez retrouve mieux un vin dont on a masqué un arôme avec la proximité
apprise qu'avec le simple repli par famille (rang réciproque moyen). Le modèle final est ensuite
réentraîné sur tout le graphe.

Attentive FP (option `--molecular`, désactivée)
------------------------------------------------
Essai du 20/11/2026 : le vecteur de départ de chaque molécule calculé par Attentive FP (Xiong et al.
2019, J. Med. Chem. 63:8749) sur son graphe atomique RDKit, entraîné avec le reste. Sur 3 graines ×
6 découpages : AUC 0,933 → 0,936 (+0,003), vin → molécule 0,961 → 0,964, Le Nez 0,514 → 0,510 (sans
gain) ; molécule « nouvelle » (`--cold`, tous ses liens vers les vins masqués) : 0,409 → 0,416, au
niveau du hasard dans les deux cas. 45 molécules, c'est trop peu pour apprendre le lien structure →
rôle dans le vin : gain non significatif, l'option reste à « none ». À refaire si la base de molécules
grandit (import Wikidata). Demande `pip install rdkit torch_geometric`.

Limite à garder en tête : les profils sont rédigés à la main. Le modèle apprend la structure de
ces fiches, pas la chimie de vrais vins.
"""

import json
import random
from collections import defaultdict
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.embeddings.space import DATA_FILE

DIM_HIDDEN = 64
DIM_OUT = 32
EPOCHS = 400
NEGATIVES = 5
LEARNING_RATE = 0.01
WEIGHT_DECAY = 1e-4
AUX_WEIGHT = 0.5
HELD_OUT = 0.15
FOLDS = 6
SEED = 20261111
EVAL_KINDS = ("aroma", "grape", "molecule")
MOLECULAR_MODES = ("none", "afp-add", "afp-only")
PERPLEXITY = 5  # carte des goûts : petits groupes séparés (15 avant le 20/11 : deux gros blocs)
MOLECULAR = "none"
# Niveau d'un vin (prix, garde) : sans lui, Margaux ressemblait plus à un Bordeaux Supérieur qu'à un Pauillac.
#   none  : le modèle ignore le niveau ;
#   aux   : il doit retrouver le prix et la garde à partir du vecteur (objectif auxiliaire, comme la bouche) ;
#   nodes : chaque vin est relié à une gamme de prix et à une durée de garde (nœuds « level », jamais écrits) ;
#   both  : les deux.
LEVEL_MODES = ("none", "aux", "nodes", "both")
LEVEL = "nodes"   # choix du 21/11/2026 après probe_level (27/33 cas « niveau », 24/24 garde-fous)
PRICE_TIERS = (12, 25, 50, 100)   # € : prix médian de la fiche
AGING_TIERS = (3, 7, 15)          # ans : garde médiane


def edge_weight(edge) -> float:
    """Poids d'une arête, ramené entre 0 et 1."""
    if edge.kind == "grape":
        return max(0.05, min(1.0, edge.weight))      # part d'encépagement
    if edge.kind == "aroma":
        return edge.weight / 3                       # intensité 1 à 3
    if edge.kind == "molecule":
        return edge.weight / 3
    return 1.0


class Command(BaseCommand):
    help = "Entraîne le réseau de graphe et écrit apps/embeddings/data/embeddings.json."

    def add_arguments(self, parser):
        parser.add_argument("--evaluate", action="store_true", help="Évaluer sans écrire le fichier.")
        parser.add_argument("--epochs", type=int, default=EPOCHS)
        parser.add_argument("--seed", type=int, default=SEED)
        parser.add_argument("--folds", type=int, default=FOLDS, help="Nombre de découpages d'évaluation.")
        parser.add_argument("--reproject", action="store_true",
                            help="Recalculer seulement la carte 2D à partir des vecteurs déjà écrits (sans entraîner).")
        parser.add_argument("--perplexity", type=float, default=PERPLEXITY,
                            help="Perplexité du t-SNE de la carte : plus elle est basse, plus les groupes sont petits.")
        parser.add_argument("--cold", action="store_true",
                            help="Évaluation « molécule nouvelle » : tous les liens vin → molécule de 20 %% des "
                                 "molécules sont masqués ; n'écrit rien.")
        parser.add_argument("--level", choices=LEVEL_MODES, default=LEVEL,
                            help="Prise en compte du niveau du vin (prix, garde) : voir LEVEL_MODES.")
        parser.add_argument("--molecular", choices=MOLECULAR_MODES, default=MOLECULAR,
                            help="Vecteur de départ des molécules : appris seul (none), ou calculé par Attentive FP "
                                 "sur leur graphe atomique, ajouté (afp-add) ou à la place (afp-only).")

    def handle(self, *args, evaluate, epochs, seed, folds, molecular=MOLECULAR, cold=False, reproject=False,
               perplexity=PERPLEXITY, level=LEVEL, **options):
        try:
            import numpy as np
            import torch
        except ImportError as exc:
            raise CommandError("PyTorch et NumPy sont requis : pip install torch scikit-learn") from exc
        from django.utils import translation

        from apps.explorer.graph import full_graph

        if reproject:
            payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            vectors = np.array(payload["vectors"])
            xy = self._project(np, vectors, payload["types"], payload["meta"].get("seed", seed), perplexity)
            payload["xy"] = [[round(float(x), 4), round(float(y), 4)] for x, y in xy]
            payload["meta"]["perplexity"] = perplexity
            DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Carte recalculée (perplexité {perplexity}) dans {DATA_FILE}."))
            return

        translation.activate("fr")
        graph = full_graph()
        ids = sorted(graph.nodes)
        index = {node_id: i for i, node_id in enumerate(ids)}
        types = [graph.nodes[i].type for i in ids]
        # Le socle commun (esters de fermentation de tous les vins) ne distingue rien : on l'écarte.
        edges = [(index[e.source], index[e.target], e.kind, edge_weight(e))
                 for e in graph.edges if not (e.kind == "molecule" and e.tier == "universal")]
        if len(edges) < 100:
            raise CommandError("Graphe vide : lancez d'abord `python manage.py load_seed`.")
        if level in ("nodes", "both"):
            self._add_level_nodes(ids, index, types, edges)
        aux = self._profile_targets(ids, index)
        aux["level_on"] = level in ("aux", "both")
        mol = self._molecular_graphs(torch, ids) if molecular != "none" else None
        if mol is not None:
            mol["mode"] = molecular
            self.stdout.write(f"Attentive FP ({molecular}) : {len(mol['rows'])} graphes moléculaires.")
        self.stdout.write(f"Graphe : {len(ids)} nœuds, {len(edges)} arêtes, {len({e[2] for e in edges})} relations.")

        if cold:
            self._cold(torch, ids, types, edges, aux, epochs, seed, folds, mol)
            return

        # 1. Évaluation sur liens masqués, répétée sur plusieurs découpages : un seul découpage
        #    ne laisse qu'une cinquantaine d'arômes masqués, trop peu pour comparer les replis.
        candidates = [k for k, e in enumerate(edges) if e[2] in EVAL_KINDS]
        aucs, totals, cases, masked = [], defaultdict(float), 0, 0
        kind_aucs = defaultdict(list)
        for fold in range(folds):
            rng = random.Random(seed + fold)
            held = set(rng.sample(candidates, int(len(candidates) * HELD_OUT)))
            train = [e for k, e in enumerate(edges) if k not in held]
            test = [edges[k] for k in sorted(held)]
            z, decoder = self._train(torch, ids, types, train, aux, epochs, seed + fold, mol)
            aucs.append(self._auc(torch, z, decoder, test, types, edges, seed + fold))
            for kind in EVAL_KINDS:
                kind_aucs[kind].append(self._auc(torch, z, decoder, [e for e in test if e[2] == kind],
                                                 types, edges, seed + fold))
            fold_mrr = self._nose_mrr(np, z.numpy(), ids, index, test)
            for name in ("embedding", "family", "none"):
                totals[name] += fold_mrr.get(name, 0.0) * fold_mrr["n"]
            cases += fold_mrr["n"]
            masked += len(test)
        auc = sum(aucs) / len(aucs)
        mrr = {**{k: v / max(cases, 1) for k, v in totals.items()}, "n": cases, "folds": folds}
        self.stdout.write(self.style.SUCCESS(
            f"{folds} découpages, {masked} liens masqués : AUC {auc:.3f} (0,5 = hasard). "
            f"Le Nez, arôme masqué ({cases} cas) : rang réciproque moyen {mrr['embedding']:.3f} avec la "
            f"proximité apprise, {mrr['none']:.3f} sans repli, {mrr['family']:.3f} avec le repli par famille."
        ))
        self.stdout.write("AUC par relation : " + ", ".join(
            f"vin → {k} {sum(v) / len(v):.3f}" for k, v in kind_aucs.items()))
        if evaluate:
            return

        # 2. Modèle final sur tout le graphe, projection 2D, écriture
        z, _decoder = self._train(torch, ids, types, edges, aux, epochs, seed, mol)
        keep = [i for i, t in enumerate(types) if t != "level"]  # les gammes ne servent qu'à l'entraînement
        ids, types = [ids[i] for i in keep], [types[i] for i in keep]
        vectors = z.numpy()[keep]
        xy = self._project(np, vectors, types, seed, perplexity)
        payload = {
            "meta": {
                "trained": date.today().isoformat(),
                "model": "R-GCN 2 couches + DistMult" + ("" if mol is None else f" + Attentive FP ({molecular})"),
                "dim": DIM_OUT, "nodes": len(ids), "edges": len(edges), "epochs": epochs, "seed": seed,
                "auc_held_out": round(auc, 3), "perplexity": perplexity, "level": level,
                "nose_mrr": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in mrr.items()},
            },
            "ids": ids,
            "types": types,
            "vectors": [[round(float(x), 4) for x in row] for row in vectors],
            "xy": [[round(float(x), 4), round(float(y), 4)] for x, y in xy],
        }
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        from apps.nose import predictor

        predictor.reset()
        self.stdout.write(self.style.SUCCESS(f"{len(ids)} vecteurs de dimension {DIM_OUT} écrits dans {DATA_FILE}."))

    # ------------------------------------------------------------------
    def _cold(self, torch, ids, types, edges, aux, epochs, seed, folds, mol):
        """Molécule « nouvelle » : on cache tous ses liens vers les vins, puis on mesure si le modèle
        les retrouve (AUC). Seule sa structure (Attentive FP) et ses liens vers la nature restent."""
        molecules = sorted({e[1] for e in edges if e[2] == "molecule"})
        aucs = []
        for fold in range(folds):
            rng = random.Random(seed + 100 + fold)
            hidden = set(rng.sample(molecules, max(1, len(molecules) // 5)))
            train = [e for e in edges if not (e[2] == "molecule" and e[1] in hidden)]
            test = [e for e in edges if e[2] == "molecule" and e[1] in hidden]
            z, decoder = self._train(torch, ids, types, train, aux, epochs, seed + fold, mol)
            aucs.append(self._auc(torch, z, decoder, test, types, edges, seed + fold))
        self.stdout.write(self.style.SUCCESS(
            f"Molécule nouvelle, {folds} découpages : AUC vin → molécule {sum(aucs) / len(aucs):.3f} "
            f"({', '.join(f'{a:.3f}' for a in aucs)})."))

    @staticmethod
    def _molecular_graphs(torch, ids) -> dict:
        """Graphe atomique de chaque molécule (RDKit), pour Attentive FP (Xiong et al. 2019).

        Atomes : élément, degré, charge, hybridation, aromaticité, hydrogènes, cycle (21 traits).
        Liaisons : simple, double, triple, aromatique, conjuguée, en cycle (6 traits).
        """
        try:
            from rdkit import Chem, RDLogger
            from torch_geometric.data import Batch, Data
        except ImportError as exc:
            raise CommandError("Attentive FP demande RDKit et PyTorch Geometric : "
                               "pip install rdkit torch_geometric") from exc
        from apps.molecules.models import Molecule

        RDLogger.DisableLog("rdApp.*")
        hyb = Chem.rdchem.HybridizationType
        bt = Chem.rdchem.BondType

        def one_hot(value, choices):
            return [1.0 if value == c else 0.0 for c in choices]

        def atom_features(a):
            return (one_hot(a.GetSymbol(), ["C", "N", "O", "S"]) + [0.0 if a.GetSymbol() in "CNOS" else 1.0]
                    + one_hot(min(a.GetDegree(), 4), [0, 1, 2, 3, 4]) + [float(a.GetFormalCharge())]
                    + one_hot(a.GetHybridization(), [hyb.SP, hyb.SP2, hyb.SP3]) + [float(a.GetIsAromatic())]
                    + one_hot(min(a.GetTotalNumHs(), 3), [0, 1, 2, 3]) + [float(a.IsInRing())]
                    + [0.0])  # réserve : 21 traits

        def bond_features(b):
            return one_hot(b.GetBondType(), [bt.SINGLE, bt.DOUBLE, bt.TRIPLE, bt.AROMATIC]) + [
                float(b.GetIsConjugated()), float(b.IsInRing())]

        smiles = dict(Molecule.objects.values_list("slug", "smiles"))
        rows, graphs = [], []
        for i, node_id in enumerate(ids):
            kind, slug = node_id.split(":", 1)
            if kind != "molecule" or not smiles.get(slug):
                continue
            m = Chem.MolFromSmiles(smiles[slug])
            if m is None:
                continue
            x = torch.tensor([atom_features(a) for a in m.GetAtoms()])
            src, dst, attr = [], [], []
            for b in m.GetBonds():
                u, v, f = b.GetBeginAtomIdx(), b.GetEndAtomIdx(), bond_features(b)
                src += [u, v]; dst += [v, u]; attr += [f, f]  # noqa: E702
            edge_index = torch.tensor([src, dst], dtype=torch.long) if src else torch.zeros(2, 0, dtype=torch.long)
            edge_attr = torch.tensor(attr) if attr else torch.zeros(0, 6)
            graphs.append(Data(x=x, edge_index=edge_index, edge_attr=edge_attr))
            rows.append(i)
        return {"rows": torch.tensor(rows), "batch": Batch.from_data_list(graphs), "x_dim": 21, "e_dim": 6}

    @staticmethod
    def _profile_targets(ids, index) -> dict:
        """Couleur, style et structure en bouche de chaque profil (objectif auxiliaire)."""
        from apps.catalog.models import Color, Style, WineProfile

        import math

        rows, structure, colors, styles, levels = [], [], [], [], []
        for p in WineProfile.objects.all():
            node = f"profile:{p.slug}"
            if node not in index:
                continue
            rows.append(index[node])
            structure.append([p.body / 5, p.acidity / 5, p.tannin / 5, p.sweetness / 5])
            colors.append(Color.values.index(p.color))
            styles.append(Style.values.index(p.style))
            price, aging = _medians(p)
            levels.append([min(1.0, math.log1p(price) / math.log1p(300)), min(1.0, aging / 30)])
        return {"rows": rows, "structure": structure, "colors": colors, "styles": styles, "levels": levels,
                "n_colors": len(Color.values), "n_styles": len(Style.values)}

    @staticmethod
    def _add_level_nodes(ids, index, types, edges) -> None:
        """Relie chaque vin à sa gamme de prix et à sa durée de garde (nœuds ajoutés en place)."""
        from bisect import bisect_right

        from apps.catalog.models import WineProfile

        def node(name):
            if name not in index:
                index[name] = len(ids)
                ids.append(name)
                types.append("level")
            return index[name]

        for p in WineProfile.objects.all():
            src = index.get(f"profile:{p.slug}")
            if src is None:
                continue
            price, aging = _medians(p)
            edges.append((src, node(f"level:prix-{bisect_right(PRICE_TIERS, price)}"), "level_price", 1.0))
            edges.append((src, node(f"level:garde-{bisect_right(AGING_TIERS, aging)}"), "level_aging", 1.0))

    @staticmethod
    def _train(torch, ids, types, edges, aux, epochs, seed, mol=None):
        """Entraîne l'encodeur et rend (vecteurs normés, décodeur)."""
        from torch import nn
        from torch.nn import functional as F  # noqa: N812

        torch.manual_seed(seed)
        rng = random.Random(seed)
        n = len(ids)
        kinds = sorted({e[2] for e in edges})
        rel = {k: i for i, k in enumerate(kinds)}
        type_names = sorted(set(types))
        type_idx = torch.tensor([type_names.index(t) for t in types])

        # Une matrice d'adjacence normalisée par relation et par sens (agrégation en moyenne pondérée).
        adjacency = []
        for kind in kinds:
            for forward in (True, False):
                a = torch.zeros(n, n)
                for s, t, k, w in edges:
                    if k == kind:
                        if forward:
                            a[s, t] += w
                        else:
                            a[t, s] += w
                adjacency.append(a / a.sum(dim=1, keepdim=True).clamp(min=1e-6))

        class Encoder(nn.Module):
            def __init__(self):
                super().__init__()
                self.node = nn.Embedding(n, DIM_HIDDEN)
                self.kind = nn.Embedding(len(type_names), DIM_HIDDEN)
                self.self1 = nn.Linear(DIM_HIDDEN, DIM_HIDDEN)
                self.rel1 = nn.ModuleList(nn.Linear(DIM_HIDDEN, DIM_HIDDEN, bias=False) for _ in adjacency)
                self.self2 = nn.Linear(DIM_HIDDEN, DIM_OUT)
                self.rel2 = nn.ModuleList(nn.Linear(DIM_HIDDEN, DIM_OUT, bias=False) for _ in adjacency)
                self.drop = nn.Dropout(0.2)
                self.afp = None
                if mol is not None:
                    from torch_geometric.nn.models import AttentiveFP

                    self.afp = AttentiveFP(in_channels=mol["x_dim"], hidden_channels=64, out_channels=DIM_HIDDEN,
                                           edge_dim=mol["e_dim"], num_layers=2, num_timesteps=2, dropout=0.1)

            def forward(self):
                h = self.node.weight + self.kind(type_idx)
                if self.afp is not None:
                    b = mol["batch"]
                    m = self.afp(b.x, b.edge_index, b.edge_attr, b.batch)
                    if mol["mode"] == "afp-only":  # la molécule n'est plus que sa structure
                        h = h.index_copy(0, mol["rows"], m + self.kind(type_idx[mol["rows"]]))
                    else:
                        h = h.index_add(0, mol["rows"], m)
                h1 = self.self1(h)
                for a, lin in zip(adjacency, self.rel1, strict=True):
                    h1 = h1 + a @ lin(h)
                h1 = self.drop(F.relu(h1))
                h2 = self.self2(h1)
                for a, lin in zip(adjacency, self.rel2, strict=True):
                    h2 = h2 + a @ lin(h1)
                return F.normalize(h2, dim=1)

        class Decoder(nn.Module):
            """DistMult : score(u, r, v) = échelle · Σ z_u · d_r · z_v + biais_r."""

            def __init__(self):
                super().__init__()
                self.diag = nn.Parameter(torch.ones(len(kinds), DIM_OUT))
                self.bias = nn.Parameter(torch.zeros(len(kinds)))
                self.scale = nn.Parameter(torch.tensor(5.0))

            def forward(self, z, s, t, r):
                return self.scale * (z[s] * self.diag[r] * z[t]).sum(dim=1) + self.bias[r]

        encoder, decoder = Encoder(), Decoder()
        heads = nn.ModuleDict({
            "structure": nn.Linear(DIM_OUT, 4),
            "color": nn.Linear(DIM_OUT, aux["n_colors"]),
            "style": nn.Linear(DIM_OUT, aux["n_styles"]),
            "level": nn.Linear(DIM_OUT, 2),
        })
        params = [*encoder.parameters(), *decoder.parameters(), *heads.parameters()]
        optimizer = torch.optim.Adam(params, lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)

        src = torch.tensor([e[0] for e in edges])
        dst = torch.tensor([e[1] for e in edges])
        rels = torch.tensor([rel[e[2]] for e in edges])
        weights = torch.tensor([e[3] for e in edges])
        # Négatifs : on remplace l'arrivée par un nœud du même type, tiré au hasard.
        by_type = defaultdict(list)
        for i, t in enumerate(types):
            by_type[t].append(i)
        pools = [by_type[types[e[1]]] for e in edges]
        aux_rows = torch.tensor(aux["rows"])
        aux_structure = torch.tensor(aux["structure"])
        aux_colors = torch.tensor(aux["colors"])
        aux_styles = torch.tensor(aux["styles"])
        aux_levels = torch.tensor(aux["levels"])
        level_on = aux.get("level_on", False)

        for _epoch in range(epochs):
            encoder.train()
            optimizer.zero_grad()
            z = encoder()
            positive = decoder(z, src, dst, rels)
            loss = (F.binary_cross_entropy_with_logits(positive, torch.ones_like(positive), reduction="none")
                    * (0.5 + weights)).mean()
            for _ in range(NEGATIVES):
                fake = torch.tensor([rng.choice(pool) for pool in pools])
                negative = decoder(z, src, fake, rels)
                loss = loss + F.binary_cross_entropy_with_logits(
                    negative, torch.zeros_like(negative)) / NEGATIVES
            zp = z[aux_rows]
            loss = loss + AUX_WEIGHT * (
                F.mse_loss(torch.sigmoid(heads["structure"](zp)), aux_structure) * 4
                + F.cross_entropy(heads["color"](zp), aux_colors)
                + F.cross_entropy(heads["style"](zp), aux_styles)
                + (F.mse_loss(torch.sigmoid(heads["level"](zp)), aux_levels) * 4 if level_on else 0)
            )
            loss.backward()
            optimizer.step()

        encoder.eval()
        with torch.no_grad():
            return encoder().detach(), decoder

    @staticmethod
    def _auc(torch, z, decoder, test, types, all_edges, seed) -> float:
        """Probabilité qu'un lien masqué soit mieux noté qu'un lien tiré au hasard (même relation)."""
        from sklearn.metrics import roc_auc_score

        rng = random.Random(seed + 1)
        kinds = sorted({e[2] for e in all_edges})
        rel = {k: i for i, k in enumerate(kinds)}
        known = {(e[0], e[1]) for e in all_edges}
        by_type = defaultdict(list)
        for i, t in enumerate(types):
            by_type[t].append(i)
        s, t, r, y = [], [], [], []
        for a, b, kind, _w in test:
            if kind not in rel:
                continue
            s.append(a); t.append(b); r.append(rel[kind]); y.append(1)  # noqa: E702
            for _ in range(5):
                fake = rng.choice(by_type[types[b]])
                if (a, fake) not in known:
                    s.append(a); t.append(fake); r.append(rel[kind]); y.append(0)  # noqa: E702
        with torch.no_grad():
            scores = decoder(z, torch.tensor(s), torch.tensor(t), torch.tensor(r)).numpy()
        return float(roc_auc_score(y, scores))

    @staticmethod
    def _nose_mrr(np, vectors, ids, index, test) -> dict:
        """Le Nez retrouve-t-il un vin quand on lui donne un arôme absent de sa fiche ?

        Pour chaque lien vin → arôme masqué pendant l'entraînement : on retire l'arôme du profil,
        on interroge Le Nez avec cet arôme et les deux arômes les plus marqués du vin, et l'on
        note le rang du vin. Trois variantes du repli sont comparées.
        """
        from apps.catalog.models import Aroma
        from apps.nose import predictor

        model = predictor.model()
        aroma_id = dict(Aroma.objects.values_list("slug", "id"))
        by_slug = {p["slug"]: p for p in model.profiles}

        def similarity(a: str, b: str) -> float | None:
            i, j = index.get(f"aroma:{a}"), index.get(f"aroma:{b}")
            return None if i is None or j is None else float(vectors[i] @ vectors[j])

        kernel = predictor.make_kernel(model, similarity)  # le même recentrage que sur le site
        totals = defaultdict(float)
        n = 0
        for s, t, kind, _w in test:
            if kind != "aroma":
                continue
            profile = by_slug.get(ids[s].split(":", 1)[1])
            hidden = aroma_id.get(ids[t].split(":", 1)[1])
            if profile is None or hidden is None or hidden not in profile["weights"]:
                continue
            others = [a for a, _w in sorted(profile["weights"].items(), key=lambda kv: -kv[1]) if a != hidden][:2]
            if len(others) < 2:
                continue
            saved = dict(profile["weights"]), dict(profile["family_weights"]), profile["total"]
            # Le profil « sans » l'arôme masqué
            w = profile["weights"].pop(hidden)
            fam = model.aroma_family[hidden]
            profile["family_weights"][fam] = profile["family_weights"].get(fam, 0) - w
            profile["total"] = max(1, profile["total"] - w)
            try:
                for name, fallback in (("embedding", kernel), ("family", "family"), ("none", None)):
                    ranking = predictor.rank(model, [hidden, *others], fallback=fallback)
                    position = next(i for i, p in enumerate(ranking, start=1) if p["slug"] == profile["slug"])
                    totals[name] += 1 / position
            finally:
                profile["weights"], profile["family_weights"], profile["total"] = saved
            n += 1
        return {**{k: v / max(n, 1) for k, v in totals.items()}, "n": n}

    @staticmethod
    def _project(np, vectors, types, seed, perplexity=PERPLEXITY):
        """Carte 2D, ramenée dans [-1, 1].

        Les vins sont projetés entre eux (t-SNE, distance cosinus) : ce sont eux que la carte
        montre d'abord, et ils en occupent tout l'espace. Chaque autre entité (cépage, arôme,
        région…) est ensuite posée au barycentre de ses cinq vins les plus proches, pondérés par
        leur proximité : un cépage se retrouve au milieu des vins qui lui ressemblent.
        """
        from sklearn.manifold import TSNE

        wines = np.array([i for i, t in enumerate(types) if t == "profile"])
        xy_w = TSNE(n_components=2, metric="cosine", perplexity=min(perplexity, len(wines) - 1), init="pca",
                    random_state=seed % (2 ** 31), learning_rate="auto").fit_transform(vectors[wines])
        xy_w = xy_w - xy_w.mean(axis=0)
        xy_w = xy_w / np.abs(xy_w).max()
        xy = np.zeros((len(types), 2))
        xy[wines] = xy_w
        rng = np.random.default_rng(seed)
        for i, t in enumerate(types):
            if t == "profile":
                continue
            sims = vectors[wines] @ vectors[i]
            top = np.argsort(-sims)[:5]
            weights = np.exp(8 * (sims[top] - sims[top].max()))
            xy[i] = (weights[:, None] * xy_w[top]).sum(axis=0) / weights.sum() + rng.normal(0, 0.012, 2)
        return np.clip(xy, -1, 1)


def _medians(p) -> tuple[float, float]:
    """Prix médian (€) et garde médiane (ans) d'une fiche ; valeurs moyennes si non renseignés."""
    price = ((p.price_min or 15) + (p.price_max or p.price_min or 15)) / 2
    aging = ((p.aging_min or 0) + (p.aging_max or p.aging_min or 4)) / 2
    return price, aging
