# Backtest Forex G10 — force relative fondamentale

Méthode : score de -5 à +5 par devise (monétaire 30 %, croissance 20 %, inflation 20 %,
différentiel 15 %, risque 15 %), décision mensuelle, 45 paires, depuis 2000.

    .venv/Scripts/python fetch_data.py     # rafraîchit les données (FRED, BIS, OECD)
    .venv/Scripts/python signal_actuel.py  # signal du modèle aujourd'hui (quelques secondes)
    .venv/Scripts/python backtest.py       # backtest complet -> results/*.csv + resultats.json (~5 min)
    .venv/Scripts/python report.py         # génère results/rapport_backtest.html

La date de fin du backtest se cale toute seule sur le dernier mois complet.
Dans Claude Code, la commande /forex fait tout : modèle, recherche web, analyse, mise à jour du journal.
Journal : ouvrir `journal/Journal Forex.html` dans un navigateur.

## Installation

    python -m venv .venv
    .venv/Scripts/python -m pip install -r requirements.txt
    .venv/Scripts/python fetch_data.py

Le dossier `data/` n'est pas versionné : `fetch_data.py` le recrée.
La commande Claude Code `/forex` est dans `claude/skills/forex/SKILL.md`
(à copier dans `~/.claude/skills/forex/` sur une nouvelle machine).

Étude personnelle, pas un conseil financier.
