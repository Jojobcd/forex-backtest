"""Génère results/rapport_backtest.html à partir de results/resultats.json."""
import json
from pathlib import Path
from datetime import date
OUT = Path(__file__).parent / "results"
o = json.load(open(OUT / "resultats.json", encoding="utf-8"))

def pct(x, d=1): return "—" if x is None else f"{x*100:.{d}f} %"
def num(x, d=2): return "—" if x is None else f"{x:.{d}f}"

S = {s["nom"]: s for s in o["strategies"]}
main = S["Panier 3 fortes vs 3 faibles"]; carry = S["Repère : portage pur (taux seuls)"]
perm = o["permutation"]; fs = o["force_signal"]; sig = o["signal_actuel"]

def strat_rows():
    cols = ["reussite", "ratio_rr", "rend_annuel", "vol_annuelle", "sharpe", "dd_max", "2000-2012", "2013-2026"]
    fmt = dict(reussite=pct, ratio_rr=num, rend_annuel=pct, vol_annuelle=pct, sharpe=num, dd_max=pct)
    rows = []
    for s in o["strategies"]:
        cls = ' class="grp"' if s["groupe"] == "strategie" else ""
        tds = "".join(f"<td>{fmt.get(c, num)(s.get(c))}</td>" for c in cols)
        rows.append(f"<tr{cls}><th scope='row'>{s['nom']}</th>{tds}</tr>")
    return "\n".join(rows)

def pair_rows():
    r = []
    for p in o["paires"]:
        r.append("<tr>" + "".join([
            f"<th scope='row'>{p['paire']}</th>", f"<td data-v='{p['sharpe']}'>{num(p['sharpe'])}</td>",
            f"<td data-v='{p['reussite']}'>{pct(p['reussite'])}</td>", f"<td data-v='{p['ratio_rr']}'>{num(p['ratio_rr'])}</td>",
            f"<td data-v='{p['rend_annuel']}'>{pct(p['rend_annuel'])}</td>", f"<td data-v='{p['dd_max']}'>{pct(p['dd_max'])}</td>",
            f"<td data-v='{p['trades']}'>{p['trades']}</td>", f"<td data-v='{p['part_exposee']}'>{pct(p['part_exposee'],0)}</td>",
            f"<td data-v='{p['2000-2012'] or 0}'>{num(p['2000-2012'])}</td>", f"<td data-v='{p['2013-2026'] or 0}'>{num(p['2013-2026'])}</td>",
            f"<td data-v='{p['cout_bps']}'>{p['cout_bps']:.1f}</td>"]) + "</tr>")
    return "\n".join(r)

def regime_rows():
    by = {}
    for x in o["regimes"]: by.setdefault(x["regime"], {})[x["strategie"]] = x
    r = []
    for reg, d in by.items():
        m, t1, c = d.get("Panier 3 fortes vs 3 faibles"), d.get("Top 1 paire (plus forte vs plus faible)"), d.get("Repère : portage pur (taux seuls)")
        cell = lambda x: f"<td>{pct(x['rend_moy_mensuel'],2)}</td><td>{pct(x['reussite'],0)}</td>" if x else "<td>—</td><td>—</td>"
        r.append(f"<tr><th scope='row'>{reg}</th><td>{m['mois']}</td>{cell(m)}{cell(t1)}{cell(c)}</tr>")
    return "\n".join(r)

def year_rows():
    names = list(o["annees"])
    years = sorted(o["annees"][names[0]])
    return "\n".join("<tr><th scope='row'>" + y + "</th>" + "".join(f"<td>{pct(o['annees'][n].get(y))}</td>" for n in names) + "</tr>" for y in years)

def score_rows():
    f = sig["facteurs"]
    r = []
    for c, v in sig["scores"].items():
        r.append(f"<tr><th scope='row'>{c}</th><td><b>{v:+.2f}</b></td>" + "".join(f"<td>{f[k][c]:+.2f}</td>" for k in ["monetaire", "croissance", "inflation", "differentiel", "risque"]) + "</tr>")
    return "\n".join(r)

top3 = "".join(f"<li><b>{t['sens']} {t['paire']}</b> : {t['forte']} (forte) contre {t['faible']} (faible), écart {t['ecart']:.1f} points.</li>" for t in sig["top3"])
best = [p["paire"] for p in o["paires"][:5]]; worst = [p["paire"] for p in o["paires"][-5:]]
both = [p["paire"] for p in o["paires"] if (p["2000-2012"] or 0) > 0 and (p["2013-2026"] or 0) > 0]

data = dict(equity=o["equity"], pairs=[dict(p=p["paire"], s=p["sharpe"], a=p["2000-2012"], b=p["2013-2026"]) for p in o["paires"]], fs=fs)

html = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Backtest Forex G10</title>
<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"></script>
<style>
:root{{color-scheme:light;--bg:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--border:rgba(11,11,11,.10);
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--pos:#2a78d6;--neg:#e34948;--good:#006300;--bad:#d03b3b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--bg:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--pos:#3987e5;--neg:#e66767;--good:#0ca30c;--bad:#e66767}}}}
:root[data-theme="dark"]{{color-scheme:dark;--bg:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--pos:#3987e5;--neg:#e66767;--good:#0ca30c;--bad:#e66767}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1080px;margin:0 auto;padding:32px 16px 64px}}h1{{font-size:28px;margin:0 0 4px}}h2{{font-size:20px;margin:40px 0 8px}}h3{{font-size:16px;margin:20px 0 6px}}
.sub{{color:var(--ink2);margin:0 0 24px}}.card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px 20px;margin:12px 0}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}}.kpi .v{{font-size:28px;font-weight:600}}.kpi .l{{color:var(--ink2);font-size:13px}}
.note{{color:var(--ink2);font-size:13px}}.tw{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}}
th,td{{padding:6px 8px;border-bottom:1px solid var(--grid);text-align:right;white-space:nowrap}}th[scope=row],thead th:first-child{{text-align:left}}thead th{{color:var(--ink2);font-weight:600;cursor:default}}
#pt thead th{{cursor:pointer}}tr.grp th,tr.grp td{{font-weight:600}}.chart{{width:100%;height:380px}}.tall{{height:900px}}
.fact{{border-left:3px solid var(--s1);padding-left:10px}}.interp{{border-left:3px solid var(--s2);padding-left:10px}}ul{{padding-left:20px}}li{{margin:4px 0}}
.tag{{display:inline-block;font-size:11px;font-weight:600;padding:1px 6px;border-radius:4px;border:1px solid var(--border);color:var(--ink2);margin-right:6px}}
</style></head><body><main>
<h1>Backtest Forex G10 : force relative fondamentale</h1>
<p class="sub">Décisions mensuelles de {o['periode'][0]} à {o['periode'][1]} · 10 devises, 45 paires · portage et coûts inclus · rapport généré le {date.today().strftime('%d/%m/%Y')}</p>

<div class="card"><h3 style="margin-top:0">Résumé</h3><ul>
<li><span class="tag">FAIT</span>Le panier « 3 devises les plus fortes contre 3 plus faibles » gagne {pct(main['rend_annuel'])} par an pour {pct(main['vol_annuelle'])} de volatilité, soit un Sharpe de {num(main['sharpe'])} net de coûts.</li>
<li><span class="tag">FAIT</span>Un classement aléatoire des devises ne fait mieux que dans {pct(perm['p_value'],0)} des 500 tirages : le signal n'est probablement pas dû au hasard.</li>
<li><span class="tag">FAIT</span>Plus l'écart de score est grand, plus la paire réussit : {pct(fs[0]['reussite'])} d'écart 0-1 contre {pct(fs[-1]['reussite'])} au-delà de 5 points.</li>
<li><span class="tag">FAIT</span>Le portage pur fait un meilleur Sharpe ({num(carry['sharpe'])}) mais avec un drawdown de {pct(carry['dd_max'],0)}, contre {pct(main['dd_max'],0)} pour la méthode.</li>
<li><span class="tag">INTERPRÉTATION</span>L'avantage s'est nettement réduit depuis 2013 (Sharpe {num(main['2013-2026'])}) : la méthode est un filtre utile, pas une machine à gains.</li></ul></div>

<div class="kpis">
<div class="card kpi"><div class="v">{num(main['sharpe'])}</div><div class="l">Sharpe net, panier 3 contre 3</div></div>
<div class="card kpi"><div class="v">{pct(main['reussite'])}</div><div class="l">Mois gagnants</div></div>
<div class="card kpi"><div class="v">{pct(main['dd_max'])}</div><div class="l">Drawdown maximal</div></div>
<div class="card kpi"><div class="v">{o['paires_positives']} / 45</div><div class="l">Paires à Sharpe positif</div></div>
</div>

<h2>Courbes de capital</h2><p class="note">Capital de départ = 1, rendements mensuels composés, nets de coûts. Exposition brute : 1 unité de chaque côté.</p>
<div class="card"><div id="eq" class="chart" role="img" aria-label="Courbes de capital des stratégies"></div></div>

<h2>Stratégies et repères</h2><p class="note">« Réussite » = part des mois gagnants. « R/R » = gain moyen / perte moyenne. Les colonnes de période donnent le Sharpe.</p>
<div class="card tw"><table><thead><tr><th>Stratégie</th><th>Réussite</th><th>R/R</th><th>Rend./an</th><th>Vol./an</th><th>Sharpe</th><th>DD max</th><th>Sharpe 2000-12</th><th>Sharpe 2013-26</th></tr></thead><tbody>{strat_rows()}</tbody></table></div>
<p class="note">Horizon 3 mois (rééquilibrage trimestriel) : Sharpe {num(o['horizon_3m']['sharpe'])}, réussite {pct(o['horizon_3m']['reussite'])}, DD {pct(o['horizon_3m']['dd_max'])}. Signal retardé d'un mois : Sharpe {num(S["Robustesse : signal retardé d'1 mois"]['sharpe'])}. L'information se périme vite.</p>

<h2>Force du signal</h2><p class="note">Toutes paires et tous mois confondus : taux de réussite selon l'écart de score entre les deux devises.</p>
<div class="card"><div id="fs" class="chart" role="img" aria-label="Réussite selon l'écart de score"></div></div>

<h2>Les 45 paires</h2><p class="note">Règle : position dans le sens de l'écart de score dès qu'il atteint 2 points, sinon pas de position. Coût par changement de position indiqué en points de base. Cliquer un en-tête pour trier.</p>
<div class="card"><div id="pr" class="chart tall" role="img" aria-label="Sharpe par paire"></div></div>
<div class="card tw"><table id="pt"><thead><tr><th>Paire</th><th>Sharpe</th><th>Réussite</th><th>R/R</th><th>Rend./an</th><th>DD max</th><th>Mois en position</th><th>Exposée</th><th>Sharpe 2000-12</th><th>Sharpe 2013-26</th><th>Coût bp</th></tr></thead><tbody>{pair_rows()}</tbody></table></div>
<div class="card interp"><b>Lecture.</b> Meilleures paires : {', '.join(best)}. Pires : {', '.join(worst)}. Positives sur les deux sous-périodes : {len(both)} paires ({', '.join(both)}). Les paires entre deux devises proches (AUDNZD, EURCHF, GBPNZD) réagissent mal à ce type de signal : leurs écarts reflètent du bruit plus que des divergences réelles.</div>

<h2>Performance par régime</h2><p class="note">Rendement mensuel moyen et part de mois gagnants. Les régimes sont étiquetés après coup pour l'analyse et ne servent jamais à décider. Les régimes de moins de 12 mois (COVID, Ukraine) reposent sur trop peu de données pour conclure.</p>
<div class="card tw"><table><thead><tr><th rowspan="2">Régime</th><th rowspan="2">Mois</th><th colspan="2">Panier 3 contre 3</th><th colspan="2">Top 1 paire</th><th colspan="2">Portage pur</th></tr>
<tr><th>Moy./mois</th><th>Réussite</th><th>Moy./mois</th><th>Réussite</th><th>Moy./mois</th><th>Réussite</th></tr></thead><tbody>{regime_rows()}</tbody></table></div>
<div class="card interp"><b>Où ça marche, où ça casse.</b><ul>
<li>La méthode est la plus solide en <b>risk-off</b> (VIX au-dessus de 25) et pendant la <b>guerre en Ukraine</b>. Les divergences de fondamentaux y sont fortes et le marché les sanctionne.</li>
<li>Elle souffre en <b>crise financière 2008</b> et en <b>risk-on calme</b> (VIX sous 15). En 2008 les dénouements de portage écrasent les fondamentaux. En marché calme, les écarts entre devises sont trop faibles pour être exploitables.</li>
<li>Le panier perd beaucoup moins que le portage pur en 2008. C'est là que la diversification sur cinq facteurs paie.</li></ul></div>

<h2>Résultats annuels</h2><div class="card tw"><table><thead><tr><th>Année</th>{''.join(f'<th>{n}</th>' for n in o['annees'])}</tr></thead><tbody>{year_rows()}</tbody></table></div>

<h2>Attribution par facteur</h2><div class="card interp">
<p>Chaque facteur testé seul, en panier 3 contre 3 :</p><ul>
<li><b>Croissance/emploi</b> est le meilleur facteur : Sharpe {num(S['Facteur seul : croissance']['sharpe'])}, stable sur les deux sous-périodes.</li>
<li><b>Différentiel de taux</b> (portage) : Sharpe {num(S['Facteur seul : differentiel']['sharpe'])}, mais avec de gros krachs.</li>
<li><b>Inflation</b> : Sharpe {num(S['Facteur seul : inflation']['sharpe'])}, faible depuis 2013.</li>
<li><b>Politique monétaire</b> (variation des taux directeurs) : Sharpe {num(S['Facteur seul : monetaire']['sharpe'])}. Le marché anticipe les décisions : une hausse de taux est déjà dans le prix le jour où elle tombe.</li>
<li><b>Risque / géopolitique</b> : Sharpe {num(S['Facteur seul : risque']['sharpe'])}. Acheter les refuges quand le VIX a déjà monté arrive trop tard.</li></ul>
<p>Une pondération adaptative calculée uniquement sur le passé (Sharpe 2013-26 de {num(S['Variante : pondération adaptative (walk-forward)']['2013-2026'])}) ne fait pas mieux que les poids fixes. Il serait trompeur de sur-pondérer la croissance au vu de ce seul tableau : ce serait du sur-apprentissage.</p></div>

<h2>Signal actuel du modèle</h2>
<div class="card"><p class="note">Calculé avec les dernières données disponibles (FRED au 2 oct. 2026, VIX et pétrole au 6 oct., taux directeurs BIS jusqu'à août 2026, CPI jusqu'à août 2026 (juin pour AUD et NZD), chômage de juin à septembre 2026 selon le pays). Les décisions de banques centrales de septembre 2026 ne sont <b>pas</b> encore dans les taux BIS : vérifier avant tout usage.</p>
<div class="tw"><table><thead><tr><th>Devise</th><th>Score</th><th>Monétaire</th><th>Croissance</th><th>Inflation</th><th>Différentiel</th><th>Risque</th></tr></thead><tbody>{score_rows()}</tbody></table></div>
<p class="note">Facteurs en z-score entre devises. Score final sur l'échelle -5 à +5.</p>
<ul>{top3}</ul>
<p class="interp">Ces trois paires ont un historique médiocre dans ce backtest (Sharpe entre 0,05 et 0,15). Le signal est donc fort mais la fiabilité historique de ces paires est faible. À croiser avec l'analyse discrétionnaire complète.</p></div>

<h2>Méthodologie</h2><div class="card"><ul>
<li><b>Décision</b> au dernier jour ouvré de chaque mois, tenue un mois. Prix FRED (fixing de midi à New York).</li>
<li><b>Anti-anticipation</b> : CPI décalé d'1 mois (3 mois pour AUD et NZD, publiés par trimestre), chômage décalé de 2 mois (3 mois après la fin du trimestre pour CHF et NZD). Taux directeurs, VIX et pétrole connus en temps réel.</li>
<li><b>Facteurs</b> : monétaire = variation des taux directeurs sur 3 et 12 mois ; croissance = baisse du chômage sur 6 mois ; inflation = écart à la cible et accélération sur 6 mois ; différentiel = niveau du taux directeur ; risque = stress VIX par profil refuge, plus choc pétrolier par exposition. Chaque facteur en z-score entre devises, pondéré 30/20/20/15/15, puis remis sur l'échelle -5 à +5.</li>
<li><b>Rendement</b> = variation spot + portage au taux directeur, moins coûts (1,5 bp par côté sur les paires USD, 3 bp sur les croisées, 6 bp avec NOK ou SEK).</li>
<li><b>Aucun paramètre n'a été ajusté</b> après avoir vu les résultats. Les pondérations sont celles de ta méthode.</li></ul></div>

<h2>Limites</h2><div class="card"><ul>
<li>Les données macro sont les versions révisées actuelles, pas celles publiées à l'époque. Les révisions du chômage et du CPI sont faibles mais existent.</li>
<li>Non reproductibles mécaniquement : ton des communiqués et discours, probabilités FedWatch/OIS, rapport COT, surprises par rapport au consensus. Le facteur monétaire n'en est qu'une approximation par les décisions de taux.</li>
<li>Le portage au taux directeur approche celui des contrats à terme. Il n'inclut ni swap ni frais de courtier.</li>
<li>Ce rapport est une étude historique. Les performances passées ne préjugent pas des performances futures. Ce n'est pas un conseil financier.</li></ul>
<p class="note">Sources : FRED (Federal Reserve Bank of St. Louis), séries H.10, VIXCLS, DCOILBRENTEU ; BIS, séries WS_CBPOL et WS_LONG_CPI ; OECD, Infra-annual Labour Statistics. Téléchargées le {date.today().strftime('%d/%m/%Y')}.</p></div>
</main>
<script>
const D={json.dumps(data, ensure_ascii=False)};
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
function layout(extra){{return Object.assign({{paper_bgcolor:css('--surface'),plot_bgcolor:css('--surface'),font:{{family:'system-ui,-apple-system,Segoe UI,sans-serif',color:css('--ink2'),size:12}},
margin:{{l:56,r:24,t:16,b:40}},xaxis:{{gridcolor:css('--grid'),linecolor:css('--axis'),zeroline:false}},yaxis:{{gridcolor:css('--grid'),linecolor:css('--axis'),zerolinecolor:css('--axis')}},
hoverlabel:{{bgcolor:css('--surface'),bordercolor:css('--border'),font:{{color:css('--ink')}}}},legend:{{orientation:'h',y:1.1}}}},extra)}}
const cfg={{displayModeBar:false,responsive:true}};
function draw(){{
 const cols=['--s1','--s2','--s3','--s4'];const names=Object.keys(D.equity);
 const tr=names.map((n,i)=>{{const k=Object.keys(D.equity[n]);const v=Object.values(D.equity[n]);return {{x:k,y:v,name:n,mode:'lines',line:{{width:2,color:css(cols[i])}},hovertemplate:'%{{x}} : %{{y:.2f}}<extra>'+n+'</extra>'}}}});
 const ann=names.map((n,i)=>{{const v=Object.values(D.equity[n]);return {{x:Object.keys(D.equity[n]).at(-1),y:v.at(-1),text:v.at(-1).toFixed(2),showarrow:false,xanchor:'left',font:{{color:css('--ink2')}}}}}});
 Plotly.react('eq',tr,layout({{hovermode:'x unified',annotations:ann,margin:{{l:56,r:48,t:40,b:40}}}}),cfg);
 Plotly.react('fs',[{{x:D.fs.map(f=>f.tranche),y:D.fs.map(f=>f.reussite*100),type:'bar',marker:{{color:css('--s1')}},text:D.fs.map(f=>(f.reussite*100).toFixed(1)+' %'),textposition:'outside',
   customdata:D.fs.map(f=>[f.n,(f.rend_moy*100).toFixed(2)]),hovertemplate:'Écart %{{x}} pts<br>Réussite %{{y:.1f}} %<br>%{{customdata[0]}} observations<br>Rend. moyen %{{customdata[1]}} %/mois<extra></extra>'}}],
   layout({{yaxis:{{range:[45,58],ticksuffix:' %',gridcolor:css('--grid')}},xaxis:{{title:{{text:'Écart de score (points)'}}}},bargap:.35,
   shapes:[{{type:'line',xref:'paper',x0:0,x1:1,y0:50,y1:50,line:{{color:css('--muted'),dash:'dot',width:1}}}}]}}),cfg);
 const p=[...D.pairs].reverse();
 Plotly.react('pr',[{{y:p.map(r=>r.p),x:p.map(r=>r.s),type:'bar',orientation:'h',marker:{{color:p.map(r=>r.s>=0?css('--pos'):css('--neg'))}},
   customdata:p.map(r=>[r.a==null?'—':r.a.toFixed(2),r.b==null?'—':r.b.toFixed(2)]),hovertemplate:'%{{y}}<br>Sharpe %{{x:.2f}}<br>2000-12 : %{{customdata[0]}} · 2013-26 : %{{customdata[1]}}<extra></extra>'}}],
   layout({{margin:{{l:70,r:24,t:8,b:40}},xaxis:{{title:{{text:'Sharpe net (2000-2026)'}},gridcolor:css('--grid'),zerolinecolor:css('--axis')}},yaxis:{{automargin:true,tickfont:{{size:11}}}},bargap:.25}}),cfg);
}}
draw();matchMedia('(prefers-color-scheme: dark)').addEventListener('change',draw);
document.querySelectorAll('#pt thead th').forEach((th,i)=>th.addEventListener('click',()=>{{const tb=document.querySelector('#pt tbody');const rows=[...tb.rows];
 const asc=th.dataset.asc!=='1';th.dataset.asc=asc?'1':'0';rows.sort((a,b)=>{{if(i===0)return asc?a.cells[0].textContent.localeCompare(b.cells[0].textContent):b.cells[0].textContent.localeCompare(a.cells[0].textContent);
 const x=parseFloat(a.cells[i].dataset.v)||0,y=parseFloat(b.cells[i].dataset.v)||0;return asc?x-y:y-x}});rows.forEach(r=>tb.appendChild(r))}}));
</script></body></html>"""
(OUT / "rapport_backtest.html").write_text(html, encoding="utf-8")
print("OK", OUT / "rapport_backtest.html")
