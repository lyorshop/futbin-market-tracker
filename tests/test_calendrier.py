from datetime import date, datetime

from fut_tracker import calendrier

DATA = {
    "hebdomadaire": [{"jour": 4, "heure": "19:00", "nom": "Promo", "effet": "crash", "detail": ""}],
    "annuel": [
        {"nom": "TOTY", "effet": "crash", "saison": 25, "debut": "2025-01-17", "fin": "2025-01-31"},
        {"nom": "TOTY", "effet": "crash", "saison": 26, "debut": "2026-01-16", "fin": "2026-01-30"},
        {"nom": "Black Friday", "effet": "crash", "saison": 26, "debut": "2025-11-28", "fin": "2025-12-01"},
    ],
    "manuel": [{"nom": "Promo eSport", "effet": "hausse", "debut": "2026-10-09", "fin": "2026-10-16"}],
}


def test_project_keeps_weekday_and_uses_latest_season():
    evs = {e["nom"]: e for e in calendrier.project(DATA, today=date(2026, 9, 29))}
    toty = evs["TOTY"]
    assert toty["debut"] == "2027-01-15" and toty["saison"] == 27 and toty["estime"]
    assert date.fromisoformat(toty["debut"]).weekday() == 4  # vendredi
    assert evs["Black Friday"]["debut"] == "2026-11-27"
    assert evs["Promo eSport"]["estime"] is False


def test_market_context_detects_crash_ahead():
    ctx = calendrier.market_context(DATA, today=date(2026, 11, 23))
    assert [e["nom"] for e in ctx["crash_proche"]] == ["Black Friday"]
    ctx = calendrier.market_context(DATA, today=date(2026, 11, 28))
    assert [e["nom"] for e in ctx["crash_en_cours"]] == ["Black Friday"]


def test_weekly_next_occurrence():
    rules = calendrier.weekly(DATA, now=datetime(2026, 9, 29, 12, 0))  # mardi
    assert rules[0]["prochain"] == "2026-10-02T19:00" and rules[0]["jour_nom"] == "vendredi"


def test_bundled_events_file_is_valid():
    data = calendrier.load()
    for ev in data["annuel"]:
        assert date.fromisoformat(ev["debut"]) <= date.fromisoformat(ev["fin"])
        assert ev["effet"] in ("crash", "hausse", "volatil")
