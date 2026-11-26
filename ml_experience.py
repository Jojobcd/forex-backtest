"""Expérience : l'apprentissage automatique (régression, arbres, LSTM) fait-il mieux que le modèle à règles ?

Walk-forward strict : à la date t, un modèle n'apprend que sur des rendements déjà réalisés (mois s <= t-1,
dont le rendement s -> s+1 est connu fin s+1). Réentraînement tous les 12 mois. Même stratégie (panier 3 fortes
contre 3 faibles), mêmes coûts et même période de test que backtest.py. Le modèle actuel n'est pas modifié.
Usage : python ml_experience.py  ->  results/ml_experience.json et results/rapport_ml.html"""
import json, numpy as np, pandas as pd, torch
from pathlib import Path
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
import model, backtest as bt

OUT = Path(__file__).parent / "results"
TRAIN_START, OOS_START = "1997-01-31", "2003-01-31"   # 6 ans d'apprentissage minimum avant le premier test
RETRAIN, SEQ, SEEDS, N_PERM = 12, 12, 5, 300
REGLES = "Règles (modèle actuel)"


def features(d, F):
    """Facteurs du modèle + tendance passée de chaque devise (rendements déjà réalisés à t)."""
    R = bt.currency_returns(d)
    past = R.shift(1)                       # rendement t-1 -> t, connu à t
    X = {k: F[k] for k in model.WEIGHTS}
    X["tendance_1m"] = model.xz(past)
    X["tendance_3m"] = model.xz(past.rolling(3).sum())
    X["tendance_12m"] = model.xz(past.rolling(12).sum())
    y = R.sub(R.mean(axis=1), axis=0)       # rendement RELATIF de la devise sur t -> t+1
    return X, y, R


def panel(X, cols, idx):
    """Tableau (mois x devise) -> lignes (mois, devise) avec une colonne par variable."""
    return pd.concat({k: X[k].loc[idx].stack(future_stack=True) for k in cols}, axis=1)


def walk_forward(fit_predict, idx_test):
    """Appelle fit_predict(train_end, dates) tous les RETRAIN mois ; renvoie les prédictions (mois x devise)."""
    preds = []
    for i in range(0, len(idx_test), RETRAIN):
        dates = idx_test[i:i + RETRAIN]
        train_end = dates[0] - pd.offsets.MonthEnd(1)     # dernier mois dont le rendement est connu à dates[0]
        preds.append(fit_predict(train_end, dates))
    return pd.concat(preds)


def tabular(make, cols, X, y):
    def fp(train_end, dates):
        tr = pd.date_range(TRAIN_START, train_end, freq="ME")
        Xtr = panel(X, cols, tr); ytr = y.loc[tr].stack(future_stack=True)
        ok = Xtr.notna().all(axis=1) & ytr.notna()
        Xtr, ytr = Xtr[ok], ytr[ok]
        sd = ytr.std(); ytr = (ytr / sd).clip(-3, 3)
        m = make().fit(Xtr.values, ytr.values)
        Xte = panel(X, cols, dates).fillna(0.0)
        return pd.Series(m.predict(Xte.values), Xte.index).unstack()[model.CCY]
    return fp


class LSTMNet(torch.nn.Module):
    def __init__(self, n_in, h=16):
        super().__init__()
        self.lstm = torch.nn.LSTM(n_in, h, batch_first=True)
        self.drop = torch.nn.Dropout(0.2)
        self.head = torch.nn.Linear(h, 1)

    def forward(self, x):
        o, _ = self.lstm(x)
        return self.head(self.drop(o[:, -1])).squeeze(-1)


def sequences(X, cols, dates, all_idx):
    """Pour chaque (date, devise) : les SEQ derniers mois de variables (fenêtre se terminant à la date)."""
    A = np.stack([X[k].reindex(all_idx)[model.CCY].values for k in cols], axis=-1)   # mois x devise x var
    A = np.nan_to_num(A)
    pos = {t: i for i, t in enumerate(all_idx)}
    seq, keys = [], []
    for t in dates:
        i = pos[t]
        if i + 1 < SEQ:
            continue
        for j, c in enumerate(model.CCY):
            seq.append(A[i + 1 - SEQ:i + 1, j]); keys.append((t, c))
    return np.array(seq, dtype=np.float32), keys


def lstm_fp(cols, X, y, all_idx, seed_preds):
    def fp(train_end, dates):
        tr = pd.date_range(TRAIN_START, train_end, freq="ME")
        Str, ktr = sequences(X, cols, tr, all_idx)
        ytr = np.array([y.at[t, c] for t, c in ktr], dtype=np.float32)
        ok = ~np.isnan(ytr); Str, ytr = Str[ok], ytr[ok]
        sd = ytr.std(); ytr = np.clip(ytr / sd, -3, 3)
        n_val = 24 * len(model.CCY)                       # les 24 derniers mois servent d'arrêt anticipé
        Ste, kte = sequences(X, cols, dates, all_idx)
        outs = []
        for seed in range(SEEDS):
            torch.manual_seed(seed); np.random.seed(seed)
            net = LSTMNet(len(cols)); opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-4)
            xt, yt = torch.tensor(Str[:-n_val]), torch.tensor(ytr[:-n_val])
            xv, yv = torch.tensor(Str[-n_val:]), torch.tensor(ytr[-n_val:])
            best, best_state, wait = np.inf, None, 0
            for _ in range(80):
                net.train(); perm = torch.randperm(len(xt))
                for b in range(0, len(xt), 256):
                    ix = perm[b:b + 256]
                    opt.zero_grad(); loss = torch.nn.functional.mse_loss(net(xt[ix]), yt[ix]); loss.backward(); opt.step()
                net.eval()
                with torch.no_grad():
                    v = torch.nn.functional.mse_loss(net(xv), yv).item()
                if v < best - 1e-4:
                    best, best_state, wait = v, {k: t.clone() for k, t in net.state_dict().items()}, 0
                else:
                    wait += 1
                    if wait >= 6:
                        break
            net.load_state_dict(best_state); net.eval()
            with torch.no_grad():
                p = net(torch.tensor(Ste)).numpy()
            s = pd.Series(p, pd.MultiIndex.from_tuples(kte)).unstack()[model.CCY]
            seed_preds.setdefault(seed, []).append(s); outs.append(s)
        print(f"  LSTM entraîné jusqu'à {train_end:%Y-%m}", flush=True)
        return sum(outs) / len(outs)
    return fp


def sharpe_rapide(v, Rv, cost):
    """Même calcul que strat_basket + run_weights, en numpy (pour les 300 tirages au hasard)."""
    rk = np.argsort(np.argsort(v, axis=1), axis=1)
    W = np.where(rk >= v.shape[1] - 3, 1 / 3, np.where(rk < 3, -1 / 3, 0.0))
    turn = np.abs(np.diff(W, axis=0, prepend=0.0))
    net = np.nansum(W * Rv, axis=1) - turn @ cost / 1e4
    return net.mean() / net.std(ddof=1) * np.sqrt(12)


def evaluate(P, R, idx, rng, n_perm=N_PERM):
    W = bt.strat_basket(P.loc[idx], 3)
    net, _ = bt.run_weights(W, R.loc[idx], bt.CCY_COST)
    s = bt.stats(net, active=pd.Series(True, net.index))
    s["2003-2012"] = bt.stats(net.loc[:"2012-12"]).get("sharpe")
    s["2013-2026"] = bt.stats(net.loc["2013-01":]).get("sharpe")
    if n_perm:
        v, Rv = P.loc[idx, model.CCY].values, R.loc[idx, model.CCY].values
        cost = np.array([bt.CCY_COST[c] for c in model.CCY])
        sims = np.array([sharpe_rapide(rng.permuted(v, axis=1), Rv, cost) for _ in range(n_perm)])
        s["p_value_hasard"] = float((sims >= s["sharpe"]).mean())
    return s, net


def main():
    torch.set_num_threads(4)
    d = model.load()
    S, F = model.scores(d)
    X, y, R = features(d, F)
    idx = S.loc[OOS_START:bt.END].index
    all_idx = S.loc[TRAIN_START:bt.END].index
    F5, F8 = list(model.WEIGHTS), list(X)
    seed_preds = {}
    preds = {
        REGLES: S,
        "Régression ridge (5 facteurs)": walk_forward(tabular(lambda: Ridge(alpha=10.0), F5, X, y), idx),
        "Régression ridge (5 facteurs + tendance)": walk_forward(tabular(lambda: Ridge(alpha=10.0), F8, X, y), idx),
        "Arbres (gradient boosting)": walk_forward(tabular(lambda: HistGradientBoostingRegressor(
            max_depth=3, learning_rate=0.05, max_iter=200, min_samples_leaf=50, l2_regularization=1.0,
            random_state=0), F8, X, y), idx),
        "LSTM (moyenne de 5 réseaux)": walk_forward(lstm_fp(F8, X, y, all_idx, seed_preds), idx),
    }
    rng = np.random.default_rng(42)
    rows, rets = [], {}
    print("Modèles entraînés, évaluation...", flush=True)
    for name, P in preds.items():
        s, net = evaluate(P, R, idx, rng)
        rets[name] = net
        s["nom"] = name
        rows.append(s)
    base = rets[REGLES]
    for s in rows:
        diff = (rets[s["nom"]] - base).dropna()
        s["ecart_vs_regles_t"] = None if s["nom"] == REGLES else float(diff.mean() / diff.std() * np.sqrt(len(diff)))
    # Instabilité du LSTM : chaque réseau seul
    lstm_seuls = []
    for seed, parts in seed_preds.items():
        s, _ = evaluate(pd.concat(parts), R, idx, None, n_perm=0)
        lstm_seuls.append(dict(graine=seed, sharpe=s["sharpe"], s2013=s["2013-2026"]))
    out = dict(periode_test=[idx[0].strftime("%Y-%m"), (idx[-1] + pd.offsets.MonthEnd(1)).strftime("%Y-%m")],
               mois_test=len(idx), resultats=rows, lstm_par_reseau=lstm_seuls,
               equity={n: {(k + pd.offsets.MonthEnd(1)).strftime("%Y-%m"): float(v)
                           for k, v in np.exp(r.fillna(0).cumsum()).items()} for n, r in rets.items()})
    with open(OUT / "ml_experience.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=float)
    rapport(out)
    return out


def rapport(o):
    pct = lambda x: "—" if x is None else f"{x*100:.1f} %"
    num = lambda x: "—" if x is None else f"{x:.2f}"
    rows = "".join(
        f"<tr><th scope='row'>{s['nom']}</th><td>{num(s['sharpe'])}</td><td>{pct(s['reussite'])}</td>"
        f"<td>{pct(s['rend_annuel'])}</td><td>{pct(s['dd_max'])}</td><td>{num(s['2003-2012'])}</td>"
        f"<td>{num(s['2013-2026'])}</td><td>{num(s['p_value_hasard'])}</td><td>{num(s['ecart_vs_regles_t'])}</td></tr>"
        for s in o["resultats"])
    seeds = ", ".join(f"{x['sharpe']:.2f}" for x in o["lstm_par_reseau"])
    eq = json.dumps(o["equity"])
    html = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Expérience apprentissage automatique</title>
<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"></script>
<style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#6b6a65;--line:#e4e1da}}
@media (prefers-color-scheme:dark){{:root{{--bg:#161615;--fg:#ecebe6;--mut:#9c9a93;--line:#33322f}}}}
body{{background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif;max-width:980px;margin:0 auto;padding:24px 16px}}
h1{{font-size:1.6rem;margin:0 0 4px}} p.mut{{color:var(--mut);margin-top:0}}
.tw{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}}
th,td{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}}
th[scope=row],thead th:first-child{{text-align:left}} thead th{{color:var(--mut);font-weight:600}}
#eq{{height:420px;margin-top:16px}}
</style></head><body>
<h1>Le LSTM bat-il le modèle à règles ?</h1>
<p class="mut">Test sur {o['mois_test']} mois jamais vus par les modèles ({o['periode_test'][0]} à {o['periode_test'][1]}),
même stratégie (3 devises les plus fortes contre les 3 plus faibles), mêmes frais.</p>
<div class="tw"><table><thead><tr><th>Méthode</th><th>Ratio rendement/risque</th><th>Mois gagnants</th><th>Rendement annuel</th>
<th>Pire baisse</th><th>2003-2012</th><th>2013-2026</th><th>p (vs hasard)</th><th>t (vs règles)</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="mut">p : part des classements tirés au hasard qui font aussi bien (sous 0,05 = avantage probablement réel).
t : écart mensuel moyen avec le modèle à règles, en nombre d'écarts-types (au-delà de 2 en valeur absolue = différence nette).
Ratio de chacun des 5 LSTM pris seuls : {seeds}.</p>
<div id="eq"></div>
<script>
const E={eq};const dark=matchMedia('(prefers-color-scheme: dark)').matches;
Plotly.newPlot('eq',Object.entries(E).map(([n,v])=>({{x:Object.keys(v),y:Object.values(v),name:n,mode:'lines'}})),
{{title:'Capital de départ 1 (frais déduits)',paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',
font:{{color:dark?'#ecebe6':'#1d1d1b'}},legend:{{orientation:'h',y:-0.2}},margin:{{l:40,r:10,t:40,b:10}}}},{{responsive:true,displayModeBar:false}});
</script></body></html>"""
    (OUT / "rapport_ml.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    o = main()
    T = pd.DataFrame(o["resultats"]).set_index("nom")
    pd.set_option("display.width", 250)
    print(T[["sharpe", "reussite", "rend_annuel", "dd_max", "2003-2012", "2013-2026", "p_value_hasard",
             "ecart_vs_regles_t"]].round(3).to_string())
    print("LSTM par réseau :", [(x["graine"], round(x["sharpe"], 2), round(x["s2013"], 2)) for x in o["lstm_par_reseau"]])
