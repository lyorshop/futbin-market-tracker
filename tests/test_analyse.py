from datetime import datetime, timedelta

from fut_tracker import analyse


def series(prices, start=datetime(2026, 9, 1)):
    return [((start + timedelta(hours=12 * i)).isoformat(), p) for i, p in enumerate(prices)]


def test_stats_position_and_variation():
    s = series([100, 120, 110, 90, 80, 100, 130, 125, 110, 60, 70, 75, 80, 85, 90])
    st = analyse.stats(s)
    assert st["dernier"] == 90 and st["min_30j"] == 60 and st["max_30j"] == 130
    assert st["position_30j"] == round(100 * 30 / 70)
    assert st["var_24h"] == round(100 * (90 - 80) / 80, 1)


def test_signal_low_price_and_crash_ahead():
    st = {"position_30j": 5, "nb_releves": 20, "var_7j": -5}
    buy = analyse.signal(st, {"jour_semaine": 1})
    assert buy["avis"] == "Acheter"
    ahead = analyse.signal(st, {"jour_semaine": 1, "crash_proche": [{"nom": "TOTY", "jours_avant": 3}]})
    assert ahead["score"] < buy["score"]
    assert any("TOTY" in r for r in ahead["raisons"])


def test_signal_high_price_on_weekend_says_sell():
    st = {"position_30j": 95, "nb_releves": 20, "var_7j": 12}
    assert analyse.signal(st, {"jour_semaine": 6})["avis"] == "Vendre"


def test_weekday_profile_finds_cheapest_day():
    start = datetime(2026, 8, 3)  # lundi
    pts = []
    for d in range(28):
        day = start + timedelta(days=d)
        price = 900 if day.weekday() == 4 else 1100 if day.weekday() == 6 else 1000
        pts.append((day.isoformat(), price))
    prof = analyse.weekday_profile(pts)
    assert prof["meilleur_achat"] == "vendredi" and prof["meilleure_vente"] == "dimanche"
