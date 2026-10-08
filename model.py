"""Modèle de force relative fondamentale G10 — traduction chiffrée de la méthode.

Pondérations (identiques au prompt) :
  politique monétaire 30 % | croissance/emploi 20 % | inflation 20 %
  différentiel de taux 15 % | géopolitique/risque 15 %

Règle anti-biais d'anticipation : à la date de décision t (dernier jour ouvré du mois),
on n'utilise QUE ce qui était publié à t. Les séries macro sont décalées de leur délai
de publication (voir LAG_*). Les prix et le VIX sont connus en temps réel.
"""
import numpy as np, pandas as pd
from pathlib import Path
D = Path(__file__).parent / "data"
CCY = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD", "NOK", "SEK"]
BIS = dict(USD="US", EUR="XM", GBP="GB", JPY="JP", CHF="CH", AUD="AU", NZD="NZ", CAD="CA", NOK="NO", SEK="SE")
OECD = dict(USD="USA", EUR="EA", GBP="GBR", JPY="JPN", CHF="CHE", AUD="AUS", NZD="NZL", CAD="CAN", NOK="NOR", SEK="SWE")
# Prix de 1 unité de devise en USD : (série FRED, inverser ?)
FX = dict(EUR=("DEXUSEU", False), JPY=("DEXJPUS", True), GBP=("DEXUSUK", False), CHF=("DEXSZUS", True),
          AUD=("DEXUSAL", False), NZD=("DEXUSNZ", False), CAD=("DEXCAUS", True), NOK=("DEXNOUS", True), SEK=("DEXSDUS", True))
WEIGHTS = dict(monetaire=0.30, croissance=0.20, inflation=0.20, differentiel=0.15, risque=0.15)
# Cibles d'inflation (approximation de la cible centrale)
TARGET = dict(USD=2, EUR=2, GBP=2, JPY=2, CHF=1, AUD=2.5, NZD=2, CAD=2, NOK=2, SEK=2)
# Délais de publication (mois) — volontairement prudents
LAG_CPI = dict(AUD=3, NZD=3)          # CPI trimestriel en Océanie
LAG_CPI_DEFAULT = 1                   # CPI du mois m publié courant m+1 -> connu fin m+1
LAG_UNEMP_M, LAG_UNEMP_Q = 2, 3       # chômage mensuel / trimestriel (après fin de trimestre)
# Comportement en régime de risque : +1 refuge, -1 pro-cyclique
HAVEN = dict(USD=0.7, EUR=0.0, GBP=-0.3, JPY=1.0, CHF=1.0, AUD=-1.0, NZD=-1.0, CAD=-0.5, NOK=-0.8, SEK=-0.6)
# Sensibilité au pétrole (exportateur +, importateur -)
OIL = dict(USD=0.0, EUR=-0.4, GBP=0.0, JPY=-0.6, CHF=-0.2, AUD=0.2, NZD=0.0, CAD=1.0, NOK=1.0, SEK=-0.2)

def _me(s):  # dernière observation de chaque mois
    s = s.copy(); s.index = pd.to_datetime(s.index); return s.resample("ME").last()

def load():
    fred = lambda i: pd.read_csv(D / f"{i}.csv", index_col=0, parse_dates=True)["v"]
    spot = pd.DataFrame({c: (1 / fred(s) if inv else fred(s)) for c, (s, inv) in FX.items()})
    spot["USD"] = 1.0
    spot = spot[CCY].ffill().resample("ME").last()
    def bis(name):
        b = pd.read_csv(D / f"bis_{name}.csv"); b["d"] = pd.PeriodIndex(b.TIME_PERIOD, freq="M").to_timestamp("M")
        w = b.pivot_table(index="d", columns="REF_AREA", values="OBS_VALUE")
        return w.rename(columns={v: k for k, v in BIS.items()})[CCY]
    pol = bis("cbpol")
    jp3m = _me(fred("IR3TIB01JPM156N"))
    pol["JPY"] = pol["JPY"].fillna(jp3m.reindex(pol.index)).fillna(0.0)   # trous BIS pendant le QE japonais
    pol = pol.ffill()
    cpi = bis("cpi")
    u = pd.read_csv(D / "oecd_unemp.csv")
    unemp = {}
    for c, a in OECD.items():
        x = u[u.REF_AREA == a]
        m = x[x.FREQ == "M"]
        if len(m) > 100:
            s = pd.Series(m.OBS_VALUE.values, pd.PeriodIndex(m.TIME_PERIOD, freq="M").to_timestamp("M")).sort_index()
            unemp[c] = s.shift(LAG_UNEMP_M, freq="ME")
        else:
            q = x[x.FREQ == "Q"]
            s = pd.Series(q.OBS_VALUE.values, pd.PeriodIndex(q.TIME_PERIOD, freq="Q").to_timestamp("Q")).sort_index()
            s.index = s.index + pd.offsets.MonthEnd(0)
            unemp[c] = s.shift(LAG_UNEMP_Q, freq="ME")
    idx = spot.index
    unemp = pd.DataFrame(unemp)[CCY].reindex(idx.union(pd.DataFrame(unemp).index)).sort_index().ffill(limit=12).reindex(idx)
    cpi_l = pd.DataFrame({c: cpi[c].shift(LAG_CPI.get(c, LAG_CPI_DEFAULT)) for c in CCY})
    vix = _me(fred("VIXCLS")); oil = _me(fred("DCOILBRENTEU"))
    return dict(spot=spot, pol=pol.reindex(idx).ffill(limit=2), cpi=cpi_l.reindex(idx).ffill(limit=3),
                unemp=unemp, vix=vix.reindex(idx), oil=oil.reindex(idx))

def xz(df, clip=2.5):
    """z-score en coupe transversale (entre devises) à chaque date."""
    z = df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1).replace(0, np.nan), axis=0)
    return z.clip(-clip, clip).fillna(0.0)

def factors(d):
    pol, cpi, un = d["pol"], d["cpi"], d["unemp"]
    f = {}
    # 1. Politique monétaire : changement de ton = trajectoire récente des taux (3 m) + cycle (12 m)
    f["monetaire"] = xz(0.6 * xz(pol.diff(3)) + 0.4 * xz(pol.diff(12)))
    # 2. Croissance/emploi : baisse du chômage sur 6 mois = force
    f["croissance"] = xz(-un.diff(6))
    # 3. Inflation : inflation au-dessus de la cible et en accélération -> banque centrale poussée au hawkish
    gap = cpi - pd.Series(TARGET)[CCY]
    f["inflation"] = xz(0.5 * xz(gap) + 0.5 * xz(cpi.diff(6)))
    # 4. Différentiel de taux : niveau du taux directeur (portage)
    f["differentiel"] = xz(pol)
    # 5. Géopolitique / risque : stress VIX (vs sa moyenne 12 m) x profil refuge, + choc pétrole x exposition
    vix = d["vix"]; stress = ((vix - vix.rolling(12).mean()) / vix.rolling(12).std()).clip(-2.5, 2.5).fillna(0)
    oilm = (np.log(d["oil"]).diff(3) / np.log(d["oil"]).diff().rolling(36).std()).clip(-2.5, 2.5).fillna(0)
    raw = pd.DataFrame({c: 0.7 * stress * HAVEN[c] + 0.3 * oilm * OIL[c] for c in CCY})
    f["risque"] = xz(raw)
    return f

def scores(d, weights=WEIGHTS):
    f = factors(d)
    comp = sum(weights[k] * f[k] for k in weights)
    # Échelle -5..+5 : z composite x 2, borné
    return (2 * xz(comp)).clip(-5, 5).round(2), f
