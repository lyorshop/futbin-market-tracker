"""Statistiques de prix et signaux achat / vente.

Les signaux combinent la position du prix dans sa fourchette récente, la
tendance et le calendrier. Ce sont des indications, pas des certitudes.
"""
from datetime import datetime, timedelta
from statistics import mean

from .calendrier import JOURS


def _parse(ts):
    return datetime.fromisoformat(ts)


def _window(series, end, days):
    start = end - timedelta(days=days)
    return [p for ts, p in series if _parse(ts) >= start]


def _price_at(series, when):
    """Dernier prix connu avant la date donnée."""
    before = [p for ts, p in series if _parse(ts) <= when]
    return before[-1] if before else None


def stats(series):
    if not series:
        return None
    end = _parse(series[-1][0])
    last = series[-1][1]
    w7, w30 = _window(series, end, 7), _window(series, end, 30)
    lo, hi = min(w30), max(w30)
    out = {
        "dernier": last,
        "releve_le": series[-1][0],
        "min_7j": min(w7), "max_7j": max(w7), "moy_7j": round(mean(w7)),
        "min_30j": lo, "max_30j": hi, "moy_30j": round(mean(w30)),
        # 0 % = au plus bas des 30 derniers jours, 100 % = au plus haut.
        "position_30j": round(100 * (last - lo) / (hi - lo)) if hi > lo else 50,
        "nb_releves": len(series),
    }
    for label, days in (("var_24h", 1), ("var_7j", 7)):
        ref = _price_at(series, end - timedelta(days=days))
        out[label] = round(100 * (last - ref) / ref, 1) if ref else None
    return out


def weekday_profile(series):
    """Écart moyen (en %) de chaque jour de la semaine par rapport à la moyenne sur 7 jours.

    Une valeur négative veut dire que ce jour est en général moins cher.
    """
    points = [(_parse(ts), price) for ts, price in series]
    buckets = {d: [] for d in range(7)}
    for dt, price in points:
        ref = [p for t, p in points if abs(t - dt) <= timedelta(days=3, hours=12)]
        if len(ref) >= 3:
            avg = mean(ref)
            buckets[dt.weekday()].append(100 * (price - avg) / avg)
    profile = [{"jour": JOURS[d], "ecart": round(mean(v), 1) if v else None, "n": len(v)}
               for d, v in buckets.items()]
    known = [p for p in profile if p["ecart"] is not None]
    best = min(known, key=lambda p: p["ecart"])["jour"] if len(known) >= 4 else None
    worst = max(known, key=lambda p: p["ecart"])["jour"] if len(known) >= 4 else None
    return {"jours": profile, "meilleur_achat": best, "meilleure_vente": worst}


def signal(st, context):
    """Score de -100 (vendre) à +100 (acheter), avec les raisons en clair."""
    if not st:
        return {"score": 0, "avis": "Pas assez de données", "raisons": []}
    score, reasons = 0, []
    pos = st["position_30j"]
    if st["nb_releves"] >= 5:
        score += round((50 - pos) * 0.8)
        if pos <= 20:
            reasons.append(f"Prix proche du plus bas sur 30 jours ({pos} % de la fourchette).")
        elif pos >= 80:
            reasons.append(f"Prix proche du plus haut sur 30 jours ({pos} % de la fourchette).")
    if st.get("var_7j") is not None and st["var_7j"] <= -15:
        score -= 10
        reasons.append(f"Baisse de {abs(st['var_7j'])} % en 7 jours : la chute peut continuer, acheter par petites quantités.")
    for ev in context.get("crash_proche", []):
        score -= 30
        reasons.append(f"{ev['nom']} dans {ev['jours_avant']} jour(s) : le marché baisse souvent avant. "
                       "Vendre maintenant, racheter pendant l'événement.")
    for ev in context.get("crash_en_cours", []):
        score += 20
        reasons.append(f"{ev['nom']} en cours : période de prix bas, bonne fenêtre d'achat pour revendre ensuite.")
    day = context.get("jour_semaine")
    if day in (3, 4):
        score += 10
        reasons.append("Jeudi/vendredi : récompenses et nouvelle promo, prix souvent au plus bas de la semaine.")
    elif day in (5, 6):
        score -= 10
        reasons.append("Week-end : les méta-cartes sont souvent au plus haut, bon moment pour vendre.")
    score = max(-100, min(100, score))
    if score >= 30:
        avis = "Acheter"
    elif score >= 10:
        avis = "Plutôt acheter"
    elif score <= -30:
        avis = "Vendre"
    elif score <= -10:
        avis = "Plutôt vendre"
    else:
        avis = "Attendre"
    return {"score": score, "avis": avis, "raisons": reasons}
