"""Backtest walk-forward mensuel de la méthode de force relative, 2000 -> dernier mois complet.
Décision au dernier jour ouvré du mois t avec les seules infos publiées à t ; tenue jusqu'à fin t+1.
Rendement = variation spot + portage (différentiel de taux directeurs), net de coûts."""
import itertools, json, numpy as np, pandas as pd
from pathlib import Path
import model
OUT = Path(__file__).parent / "results"; OUT.mkdir(exist_ok=True)
def _last_decision():
    """Dernière décision dont le mois de détention est complet dans les prix FRED."""
    last = pd.read_csv(Path(__file__).parent / "data" / "DEXUSEU.csv", parse_dates=["date"]).date.max()
    complete = last + pd.offsets.MonthEnd(0) if last.is_month_end or (last + pd.offsets.BDay(1)).month != last.month \
        else last - pd.offsets.MonthEnd(1)
    return (complete - pd.offsets.MonthEnd(1)).strftime("%Y-%m-%d")


START, END = "2000-01-31", _last_decision()
PRIORITY = ["EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "NOK", "SEK", "JPY"]   # convention de cotation
SCANDI = {"NOK", "SEK"}
THRESH = 2.0                                     # écart de score minimal pour prendre une paire
MAIN = "Panier 3 fortes vs 3 faibles"
TOP1 = "Top 1 paire (plus forte vs plus faible)"
TOP3 = "Top 3 paires (écarts max)"
CARRY = "Repère : portage pur (taux seuls)"


def pair_name(a, b):
    return (a + b, a, b) if PRIORITY.index(a) < PRIORITY.index(b) else (b + a, b, a)


PAIRS = sorted({pair_name(a, b) for a, b in itertools.combinations(model.CCY, 2)},
               key=lambda p: (PRIORITY.index(p[1]), PRIORITY.index(p[2])))


def cost_bps(base, quote):
    """Demi-spread + glissement par changement de position (aller simple), en points de base."""
    if base in SCANDI or quote in SCANDI:
        return 6.0
    return 1.5 if "USD" in (base, quote) else 3.0


CCY_COST = {c: (4.0 if c in SCANDI else 1.5) for c in model.CCY}
CCY_COST["USD"] = 0.0


def currency_returns(d):
    """Rendement excédentaire (log) de chaque devise contre USD sur t -> t+1, portage inclus."""
    spot, pol = d["spot"], d["pol"]
    fx = np.log(spot).diff().shift(-1)
    carry = pol.sub(pol["USD"], axis=0) / 1200.0
    return fx + carry


def stats(r, active=None):
    r = r.dropna()
    if len(r) == 0:
        return {}
    act = r[active.reindex(r.index).fillna(False).astype(bool)] if active is not None else r[r != 0]
    if len(act) == 0:
        return {}
    eq = r.cumsum()
    dd = (np.exp(eq) / np.exp(eq.cummax()) - 1).min()
    wins, losses = act[act > 0], act[act < 0]
    ann, vol = r.mean() * 12, r.std() * np.sqrt(12)
    return dict(
        mois=int(len(r)), trades=int(len(act)), reussite=float((act > 0).mean()),
        gain_moy=float(wins.mean()) if len(wins) else 0.0,
        perte_moy=float(losses.mean()) if len(losses) else 0.0,
        ratio_rr=float(wins.mean() / -losses.mean()) if len(wins) and len(losses) else np.nan,
        profit_factor=float(wins.sum() / -losses.sum()) if len(losses) else np.nan,
        rend_annuel=float(ann), vol_annuelle=float(vol), sharpe=float(ann / vol) if vol else np.nan,
        dd_max=float(dd), calmar=float(ann / -dd) if dd < 0 else np.nan,
        t_stat=float(r.mean() / r.std() * np.sqrt(len(r))) if r.std() else np.nan,
        total=float(np.exp(r.sum()) - 1))


def run_weights(W, R, costs):
    """W : poids par devise (vs USD), décidés à t. R : rendements t->t+1."""
    gross = (W * R).sum(axis=1, min_count=1)
    turn = W.diff().abs().fillna(W.abs())
    tc = (turn * pd.Series(costs)).sum(axis=1) / 1e4
    return gross - tc, gross


def strat_top_pairs(S, n):
    W = pd.DataFrame(0.0, index=S.index, columns=model.CCY)
    for t, row in S.iterrows():
        cand = sorted(((row[a] - row[b], a, b) for a in model.CCY for b in model.CCY if a != b), reverse=True)
        for _, lo, sh in cand[:n]:
            W.loc[t, lo] += 1.0 / n
            W.loc[t, sh] -= 1.0 / n
    return W


def strat_basket(S, k=3):
    W = pd.DataFrame(0.0, index=S.index, columns=model.CCY)
    for t, row in S.iterrows():
        o = row.sort_values()
        W.loc[t, o.index[-k:]] = 1.0 / k
        W.loc[t, o.index[:k]] = -1.0 / k
    return W


def regimes(idx, d):
    """Étiquettes de régime (analyse ex post uniquement, jamais utilisées pour décider)."""
    hold = idx + pd.offsets.MonthEnd(1)  # mois de détention

    def span(a, b):
        return pd.Series((hold >= a) & (hold <= b), idx)

    lab = pd.DataFrame(index=idx)
    lab["Crise financière 2007-09"] = span("2007-08-01", "2009-06-30")
    lab["Crise dette zone euro 2010-12"] = span("2010-04-01", "2012-09-30")
    lab["COVID 2020"] = span("2020-02-01", "2020-06-30")
    lab["Guerre Ukraine / choc énergie 2022"] = span("2022-02-01", "2022-12-31")
    lab["Guerres commerciales (2018-19, 2025)"] = span("2018-03-01", "2019-12-31") | span("2025-02-01", "2025-06-30")
    dus = d["pol"]["USD"].diff(6).reindex(idx)
    lab["Fed en cycle de hausse"] = dus > 0.1
    lab["Fed en cycle de baisse"] = dus < -0.1
    lab["Fed à l'arrêt"] = dus.abs() <= 0.1
    v = d["vix"].reindex(idx)
    lab["Risk-off (VIX > 25)"] = v > 25
    lab["Risk-on (VIX < 15)"] = v < 15
    return lab


def main():
    d = model.load()
    S, F = model.scores(d)
    R = currency_returns(d).loc[START:END]
    Sb = S.loc[START:END]
    out = {"periode": [START[:7], (pd.Timestamp(END) + pd.offsets.MonthEnd(1)).strftime("%Y-%m")]}

    # ---- Stratégies de portefeuille ----
    strats = {TOP1: strat_top_pairs(Sb, 1), TOP3: strat_top_pairs(Sb, 3), MAIN: strat_basket(Sb, 3)}
    bench = {CARRY: strat_basket(model.xz(d["pol"]).loc[START:END], 3)}
    for k in model.WEIGHTS:
        bench[f"Facteur seul : {k}"] = strat_basket(F[k].loc[START:END], 3)
    bench["Robustesse : signal retardé d'1 mois"] = strat_basket(S.shift(1).loc[START:END], 3)
    rets, table = {}, []
    for name, W in {**strats, **bench}.items():
        net, gross = run_weights(W, R, CCY_COST)
        rets[name] = net
        s = stats(net, active=pd.Series(True, net.index))
        s["sharpe_brut"] = stats(gross, active=pd.Series(True, gross.index)).get("sharpe")
        s["nom"] = name
        s["groupe"] = "strategie" if name in strats else "repere"
        s["2000-2012"] = stats(net.loc[:"2012-12"]).get("sharpe")
        s["2013-2026"] = stats(net.loc["2013-01":]).get("sharpe")
        s["rotation_mensuelle"] = float(W.diff().abs().sum(axis=1).mean() / 2)
        table.append(s)
    # Variante walk-forward : poids des facteurs = Sharpe glissant 60 m (positif) des facteurs, calculé
    # uniquement sur les rendements déjà réalisés à t (shift(1)). Aucune donnée future.
    fr = pd.DataFrame({k: rets[f"Facteur seul : {k}"] for k in model.WEIGHTS})
    past = fr.shift(1)
    sh = (past.rolling(60, min_periods=36).mean() / past.rolling(60, min_periods=36).std()).clip(lower=0)
    wts = sh.div(sh.sum(axis=1), axis=0)
    wts = wts.where(sh.sum(axis=1) > 0, np.nan).fillna(pd.Series(model.WEIGHTS))
    comp = sum(F[k].loc[START:END].mul(wts[k], axis=0) for k in model.WEIGHTS)
    name = "Variante : pondération adaptative (walk-forward)"
    W = strat_basket(model.xz(comp), 3)
    net, gross = run_weights(W, R, CCY_COST)
    rets[name] = net
    s = stats(net, active=pd.Series(True, net.index))
    s.update(nom=name, groupe="repere", sharpe_brut=stats(gross, active=pd.Series(True, gross.index)).get("sharpe"),
             rotation_mensuelle=float(W.diff().abs().sum(axis=1).mean() / 2))
    s["2000-2012"] = stats(net.loc[:"2012-12"]).get("sharpe")
    s["2013-2026"] = stats(net.loc["2013-01":]).get("sharpe")
    table.append(s)
    out["poids_adaptatifs_dernier"] = wts.iloc[-1].round(3).to_dict()
    pd.DataFrame(table).to_csv(OUT / "strategies.csv", index=False)
    pd.DataFrame(rets).to_csv(OUT / "rendements_mensuels.csv")
    out["strategies"] = table

    # ---- Horizon trimestriel ----
    Wq = strat_basket(Sb, 3).iloc[::3].reindex(Sb.index).ffill()
    netq, _ = run_weights(Wq, R, CCY_COST)
    out["horizon_3m"] = stats(netq, active=pd.Series(True, netq.index))

    # ---- Test de permutation : la méthode bat-elle un classement aléatoire ? ----
    rng = np.random.default_rng(42)
    ref = stats(rets[MAIN])["sharpe"]
    sims = []
    for _ in range(500):
        Sr = pd.DataFrame(rng.permuted(Sb.values, axis=1), Sb.index, Sb.columns)
        sims.append(stats(run_weights(strat_basket(Sr, 3), R, CCY_COST)[0])["sharpe"])
    sims = np.array(sims)
    out["permutation"] = dict(sharpe_methode=ref, sharpe_aleatoire_moyen=float(sims.mean()),
                              p95=float(np.percentile(sims, 95)), p_value=float((sims >= ref).mean()))

    # ---- Toutes les paires : signe de l'écart de score si |écart| >= seuil ----
    prows, pmonth, sig = [], {}, []
    for name, b, q in PAIRS:
        diff = Sb[b] - Sb[q]
        pos = np.sign(diff).where(diff.abs() >= THRESH, 0.0)
        pr = R[b] - R[q]
        c = cost_bps(b, q) / 1e4
        net = pos * pr - pos.diff().abs().fillna(pos.abs()) * c
        pmonth[name] = net
        st = stats(net, active=pos != 0)
        st.update(paire=name, part_long=float((pos > 0).mean()), part_short=float((pos < 0).mean()),
                  part_exposee=float((pos != 0).mean()), cout_bps=cost_bps(b, q))
        st["2000-2012"] = stats(net.loc[:"2012-12"]).get("sharpe")
        st["2013-2026"] = stats(net.loc["2013-01":]).get("sharpe")
        prows.append(st)
        sig.append(pd.DataFrame({"ecart": diff.abs(), "r": np.sign(diff) * pr}))
    P = pd.DataFrame(prows).sort_values("sharpe", ascending=False)
    P.to_csv(OUT / "toutes_les_paires.csv", index=False)
    PM = pd.DataFrame(pmonth)
    PM.to_csv(OUT / "paires_rendements_mensuels.csv")
    allp = PM.mean(axis=1)
    out["paires"] = P.replace({np.nan: None}).to_dict("records")
    out["paires_agregat"] = stats(allp, active=pd.Series(True, allp.index))
    out["paires_positives"] = int((P.sharpe > 0).sum())

    # ---- Toutes paires confondues : réussite selon la force du signal ----
    sig = pd.concat(sig).dropna()
    sig["tranche"] = pd.cut(sig.ecart, [0, 1, 2, 3, 4, 5, 11], right=False,
                            labels=["0-1", "1-2", "2-3", "3-4", "4-5", "5+"])
    out["force_signal"] = [dict(tranche=str(k), n=int(v.count()), reussite=float((v > 0).mean()),
                                rend_moy=float(v.mean())) for k, v in sig.groupby("tranche", observed=True).r]

    # ---- Régimes ----
    lab = regimes(Sb.index, d)
    reg = []
    for col in lab:
        m = lab[col].astype(bool)
        for nm in [MAIN, TOP1, CARRY]:
            x = rets[nm][m].dropna()
            s = stats(x, active=pd.Series(True, x.index))
            if s:
                reg.append(dict(regime=col, strategie=nm, mois=s["mois"], reussite=s["reussite"],
                                rend_moy_mensuel=float(x.mean()), sharpe=s["sharpe"], dd_max=s["dd_max"]))
    out["regimes"] = reg
    pd.DataFrame(reg).to_csv(OUT / "regimes.csv", index=False)

    # ---- Par année et courbes de capital ----
    out["annees"] = {nm: {str(y): float(np.exp(v.sum()) - 1) for y, v in rets[nm].groupby(rets[nm].index.year)}
                     for nm in [MAIN, TOP1, TOP3, CARRY]}
    out["equity"] = {nm: {(k + pd.offsets.MonthEnd(1)).strftime("%Y-%m"): float(v)
                          for k, v in np.exp(rets[nm].fillna(0).cumsum()).items()}
                     for nm in [MAIN, TOP3, TOP1, CARRY]}

    # ---- Signal actuel (dernier point disponible) ----
    last = S.dropna(how="all").index[-1]
    cur = S.loc[last].sort_values(ascending=False)
    cand = sorted(((cur[a] - cur[b], a, b) for a in model.CCY for b in model.CCY if a != b), reverse=True)[:3]
    out["signal_actuel"] = dict(
        date=last.strftime("%Y-%m-%d"), scores=cur.to_dict(),
        facteurs={k: F[k].loc[last].round(2).to_dict() for k in F},
        top3=[dict(paire=pair_name(a, b)[0], sens="ACHAT" if pair_name(a, b)[1] == a else "VENTE",
                   ecart=float(round(e, 2)), forte=a, faible=b) for e, a, b in cand],
        donnees={k: (v.dropna(how="all") if hasattr(v, "columns") else v.dropna()).index[-1].strftime("%Y-%m")
                 for k, v in d.items()})
    S.loc["2000":].to_csv(OUT / "scores_mensuels.csv")
    with open(OUT / "resultats.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=float)
    return out


if __name__ == "__main__":
    o = main()
    pd.set_option("display.width", 250)
    T = pd.DataFrame(o["strategies"]).set_index("nom")
    print(T[["reussite", "ratio_rr", "rend_annuel", "vol_annuelle", "sharpe", "sharpe_brut", "dd_max", "t_stat",
             "2000-2012", "2013-2026", "rotation_mensuelle"]].round(3).to_string())
    print("3m:", {k: round(v, 3) for k, v in o["horizon_3m"].items()})
    print("perm:", o["permutation"])
    P = pd.DataFrame(o["paires"]).set_index("paire")
    print(P[["trades", "reussite", "ratio_rr", "rend_annuel", "sharpe", "dd_max", "2000-2012", "2013-2026",
             "part_exposee"]].round(3).to_string())
    print("agrégat paires:", {k: round(v, 3) for k, v in o["paires_agregat"].items()}, "positives:", o["paires_positives"])
    print(pd.DataFrame(o["force_signal"]).round(4).to_string())
    print(pd.DataFrame(o["regimes"]).round(3).to_string())
    print(o["signal_actuel"]["date"], o["signal_actuel"]["top3"], o["signal_actuel"]["donnees"])
