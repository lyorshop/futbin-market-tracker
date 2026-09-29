import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.environ.get("FUT_DB", DATA_DIR / "marche.db"))
EVENTS_PATH = DATA_DIR / "evenements.json"

# Édition du jeu suivie par FUTBIN (27 = EA FC 27, sorti fin septembre 2026).
FUTBIN_YEAR = os.environ.get("FUT_ANNEE", "27")
# Plateforme : "pc", "ps" (PlayStation) ou "xbox".
PLATFORM = os.environ.get("FUT_PLATEFORME", "pc")
# Intervalle entre deux relevés automatiques, en minutes.
COLLECT_EVERY_MIN = int(os.environ.get("FUT_INTERVALLE_MIN", "30"))
# Pause entre deux requêtes FUTBIN, pour rester discret.
REQUEST_PAUSE_S = float(os.environ.get("FUT_PAUSE_S", "4"))
SOURCES_PATH = DATA_DIR / "sources.json"
# Actualisation de la liste des joueurs les plus utilisés, en heures.
POPULAR_EVERY_H = int(os.environ.get("FUT_POPULAIRES_H", "6"))
