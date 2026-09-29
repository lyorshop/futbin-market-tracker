"""Calendrier du marché : cycles de la semaine, grands événements et prévisions."""
import json
from datetime import date, datetime, timedelta

from . import config

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
# Fenêtre avant un événement où le marché commence souvent à baisser.
PRE_EVENT_DAYS = 7


def load(path=None):
    with open(path or config.EVENTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def save(data, path=None):
    with open(path or config.EVENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _d(s):
    return date.fromisoformat(s)


def history(data):
    """Événements passés triés, groupés par saison."""
    return sorted(data.get("annuel", []), key=lambda e: e["debut"])


def project(data, today=None):
    """Prévoit la prochaine occurrence de chaque événement annuel.

    Méthode : on part de la date la plus récente connue et on ajoute 52 semaines
    (364 jours, ce qui garde le même jour de la semaine, EA lançant presque
    toujours ses promos un vendredi) jusqu'à tomber dans le futur.
    """
    today = today or date.today()
    latest = {}
    for ev in data.get("annuel", []):
        if ev["nom"] not in latest or ev["debut"] > latest[ev["nom"]]["debut"]:
            latest[ev["nom"]] = ev
    out = []
    for ev in latest.values():
        start, end = _d(ev["debut"]), _d(ev["fin"])
        years = 0
        while end < today:
            start += timedelta(days=364)
            end += timedelta(days=364)
            years += 1
        out.append({
            "nom": ev["nom"], "effet": ev["effet"], "detail": ev.get("detail", ""),
            "debut": start.isoformat(), "fin": end.isoformat(),
            "estime": years > 0, "saison": ev.get("saison", 0) + years,
        })
    for ev in data.get("manuel", []):
        if _d(ev["fin"]) >= today:
            out.append({**ev, "estime": False})
    return sorted(out, key=lambda e: e["debut"])


def upcoming(data, today=None, horizon_days=120):
    today = today or date.today()
    out = []
    for ev in project(data, today):
        start, end = _d(ev["debut"]), _d(ev["fin"])
        if start - today > timedelta(days=horizon_days):
            continue
        ev = dict(ev)
        ev["jours_avant"] = max((start - today).days, 0)
        ev["en_cours"] = start <= today <= end
        out.append(ev)
    return out


def weekly(data, now=None):
    """Cycles de la semaine, avec le prochain passage de chacun."""
    now = now or datetime.now()
    out = []
    for rule in data.get("hebdomadaire", []):
        h, m = map(int, rule["heure"].split(":"))
        delta = (rule["jour"] - now.weekday()) % 7
        nxt = (now + timedelta(days=delta)).replace(hour=h, minute=m, second=0, microsecond=0)
        if nxt < now:
            nxt += timedelta(days=7)
        out.append({**rule, "jour_nom": JOURS[rule["jour"]], "prochain": nxt.isoformat(timespec="minutes")})
    return sorted(out, key=lambda r: r["prochain"])


def market_context(data, today=None):
    """Résumé de la situation actuelle pour le calcul des signaux."""
    today = today or date.today()
    evs = upcoming(data, today, horizon_days=PRE_EVENT_DAYS)
    return {
        "crash_en_cours": [e for e in evs if e["en_cours"] and e["effet"] == "crash"],
        "crash_proche": [e for e in evs if not e["en_cours"] and e["effet"] == "crash"],
        "jour_semaine": today.weekday(),
    }
