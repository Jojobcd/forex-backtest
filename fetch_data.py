"""Télécharge et met en cache toutes les données sources (FRED, BIS, OECD).
Usage : python fetch_data.py   (relancer pour rafraîchir)"""
import io, requests, pandas as pd
from pathlib import Path
D = Path(__file__).parent / "data"; D.mkdir(exist_ok=True)
BIS_AREAS = "US+XM+GB+JP+CH+AU+NZ+CA+NO+SE"
FRED = ["DEXUSEU","DEXJPUS","DEXUSUK","DEXSZUS","DEXUSAL","DEXUSNZ","DEXCAUS","DEXNOUS","DEXSDUS",
        "VIXCLS","DCOILBRENTEU","IR3TIB01JPM156N"]

def fred(i):
    r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={i}", timeout=120); r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text)); df.columns = ["date", "v"]
    df["v"] = pd.to_numeric(df["v"], errors="coerce"); df.dropna().to_csv(D / f"{i}.csv", index=False)

def bis(flow, key, name):
    u = f"https://stats.bis.org/api/v2/data/dataflow/BIS/{flow}/1.0/{key}?format=csv&startPeriod=1997-01"
    df = pd.read_csv(io.StringIO(requests.get(u, timeout=180).text), low_memory=False)
    df[["REF_AREA", "TIME_PERIOD", "OBS_VALUE"]].to_csv(D / f"bis_{name}.csv", index=False)

def oecd_unemp():
    u = ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,1.0/"
         "USA+EA+GBR+JPN+CHE+AUS+NZL+CAN+NOR+SWE..._Z.Y._T.Y_GE15..M+Q?startPeriod=1997-01&format=csvfile")
    df = pd.read_csv(io.StringIO(requests.get(u, timeout=300).text))
    df[["REF_AREA", "FREQ", "TIME_PERIOD", "OBS_VALUE"]].to_csv(D / "oecd_unemp.csv", index=False)

if __name__ == "__main__":
    for i in FRED: fred(i); print("FRED", i)
    bis("WS_CBPOL", f"M.{BIS_AREAS}", "cbpol"); print("BIS taux directeurs")
    bis("WS_LONG_CPI", f"M.{BIS_AREAS}.771", "cpi"); print("BIS CPI")
    oecd_unemp(); print("OECD chômage")
