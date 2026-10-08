"""Signal du modèle à la dernière date disponible, en quelques secondes (sans relancer le backtest).
Usage : python signal_actuel.py [--json]"""
import json, sys
import pandas as pd
from pathlib import Path
import model
from backtest import pair_name

R = Path(__file__).parent / "results"
NOMS = dict(USD="dollar américain", EUR="euro", GBP="livre sterling", JPY="yen japonais", CHF="franc suisse",
            AUD="dollar australien", NZD="dollar néo-zélandais", CAD="dollar canadien", NOK="couronne norvégienne",
            SEK="couronne suédoise")


def main():
    d = model.load()
    S, F = model.scores(d)
    last = S.dropna(how="all").index[-1]
    cur = S.loc[last].sort_values(ascending=False)
    hist = pd.read_csv(R / "toutes_les_paires.csv").set_index("paire") if (R / "toutes_les_paires.csv").exists() else None
    pairs = []
    for a in model.CCY:
        for b in model.CCY:
            if a == b or cur[a] <= cur[b]:
                continue
            name, base, _ = pair_name(a, b)
            h = hist.loc[name] if hist is not None else None
            pairs.append(dict(paire=name, sens="ACHAT" if base == a else "VENTE", forte=a, faible=b,
                              ecart=round(float(cur[a] - cur[b]), 2),
                              sharpe_hist=None if h is None else round(float(h.sharpe), 2),
                              sharpe_2013=None if h is None else round(float(h["2013-2026"]), 2)))
    pairs.sort(key=lambda p: -p["ecart"])
    dates = {k: (v.dropna(how="all") if hasattr(v, "columns") else v.dropna()).index[-1].strftime("%Y-%m")
             for k, v in d.items()}
    raw_dates = dict(
        taux_directeurs=pd.read_csv(model.D / "bis_cbpol.csv").TIME_PERIOD.max(),
        cpi=pd.read_csv(model.D / "bis_cpi.csv").TIME_PERIOD.max(),
        chomage=pd.read_csv(model.D / "oecd_unemp.csv").TIME_PERIOD.max(),
        prix=pd.read_csv(model.D / "DEXUSEU.csv").date.max())
    out = dict(date=last.strftime("%Y-%m-%d"), donnees=raw_dates,
               scores={c: float(v) for c, v in cur.items()},
               facteurs={k: {c: round(float(x), 2) for c, x in F[k].loc[last].items()} for k in F},
               paires_ecart_3plus=[p for p in pairs if p["ecart"] >= 3])
    if "--json" in sys.argv:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return out
    print(f"Signal au {out['date']}  (données : {raw_dates})\n")
    for c, v in cur.items():
        print(f"  {c}  {v:+.2f}  {NOMS[c]}")
    print("\nPaires avec écart >= 3 points (Sharpe historique de la paire / depuis 2013) :")
    for p in out["paires_ecart_3plus"]:
        print(f"  {p['sens']:5s} {p['paire']}  écart {p['ecart']:.1f}  hist {p['sharpe_hist']}  2013+ {p['sharpe_2013']}")
    return out


if __name__ == "__main__":
    main()
