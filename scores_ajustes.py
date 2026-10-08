"""Applique les ajustements de l'analyste au score du modèle, en gardant les scores RELATIFS.

Usage : python scores_ajustes.py ajustements/AAAA-MM-JJ.json [--json]

Le fichier d'ajustements contient, pour chaque devise, ce que le modèle ne voit pas encore :
  {"date": "...", "ajustements": {"USD": {"delta": -0.2, "raison": "..."}, ...}}
Règles appliquées :
  - chaque delta est borné à ±1,5 : le modèle reste la base ;
  - la moyenne des deltas est retirée : si tout le monde monte ses taux, personne ne gagne de points ;
  - score final borné à ±5.
"""
import json, sys
from pathlib import Path
import pandas as pd
import model
from backtest import pair_name

ROOT = Path(__file__).parent
MAX_DELTA = 1.5


def main(path, as_json=False):
    adj = json.loads(Path(path).read_text(encoding="utf-8"))
    d = model.load()
    S, _ = model.scores(d)
    base = S.dropna(how="all").iloc[-1]
    raw = pd.Series({c: float(adj["ajustements"].get(c, {}).get("delta", 0.0)) for c in model.CCY})
    clipped = raw.clip(-MAX_DELTA, MAX_DELTA)
    mean = clipped.mean()
    final = (base + clipped - mean).clip(-5, 5).round(2)
    hist = pd.read_csv(ROOT / "results" / "toutes_les_paires.csv").set_index("paire")
    rows = []
    for a in model.CCY:
        for b in model.CCY:
            if a == b or final[a] <= final[b]:
                continue
            name, base_ccy, _ = pair_name(a, b)
            h = hist.loc[name]
            fiable = bool(h["2000-2012"] > 0 and h["2013-2026"] > 0)
            rows.append(dict(paire=name, sens="ACHAT" if base_ccy == a else "VENTE", forte=a, faible=b,
                             ecart=round(float(final[a] - final[b]), 2), sharpe=round(float(h.sharpe), 2),
                             sharpe_2013=round(float(h["2013-2026"]), 2), fiable=fiable))
    rows.sort(key=lambda r: -r["ecart"])
    out = dict(date=adj.get("date"), moyenne_deltas=round(float(mean), 3),
               devises=[dict(devise=c, modele=round(float(base[c]), 2), delta=round(float(clipped[c] - mean), 2),
                             score=float(final[c]), raison=adj["ajustements"].get(c, {}).get("raison", ""))
                        for c in final.sort_values(ascending=False).index],
               candidats=[r for r in rows if r["ecart"] >= 3 and r["fiable"]],
               ecart_3_non_fiables=[r for r in rows if r["ecart"] >= 3 and not r["fiable"]])
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return out
    if abs(raw.mean()) > 0.3:
        print(f"ATTENTION : les ajustements bruts vont surtout dans un sens (moyenne {raw.mean():+.2f}). "
              "Ils ont été recentrés : vérifier que c'est voulu.\n")
    print(f"{'Devise':6s} {'Modèle':>7s} {'Ajust.':>7s} {'Final':>7s}")
    for r in out["devises"]:
        print(f"{r['devise']:6s} {r['modele']:+7.2f} {r['delta']:+7.2f} {r['score']:+7.2f}")
    print("\nCandidats (écart >= 3 et paire fiable sur 2000-12 ET 2013-26) :")
    for r in out["candidats"]:
        print(f"  {r['sens']:5s} {r['paire']}  écart {r['ecart']:.1f}  Sharpe {r['sharpe']} / 2013+ {r['sharpe_2013']}")
    print("\nÉcart >= 3 mais paire peu fiable (à éviter sauf raison forte) :")
    print("  " + ", ".join(f"{r['sens']} {r['paire']} ({r['ecart']:.1f})" for r in out["ecart_3_non_fiables"]))
    return out


if __name__ == "__main__":
    main(sys.argv[1], "--json" in sys.argv)
