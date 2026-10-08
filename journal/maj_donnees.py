"""Construit donnees.js (lu par « Journal Forex.html ») à partir des fichiers JSON de analyses/ et idees/.
Claude ajoute un fichier par analyse et par idée, puis relance ce script."""
import json
from pathlib import Path
H = Path(__file__).parent
def load(d):
    out = []
    for f in sorted((H / d).glob("*.json")):
        x = json.loads(f.read_text(encoding="utf-8"))
        x = x.get("data", x); x["id"] = x.get("id", f.stem); out.append(x)
    return out
data = {"analyses": load("analyses"), "idees": load("idees")}
(H / "donnees.js").write_text("/* Généré par maj_donnees.py : ne pas modifier à la main. */\nwindow.JOURNAL_DATA = "
                              + json.dumps(data, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
print(len(data["analyses"]), "analyse(s),", len(data["idees"]), "idée(s)")
