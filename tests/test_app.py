import pytest

from fut_tracker import app as app_module, collecte, config, db, futbin


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    return app_module.app.test_client()


def test_add_player_from_link_and_manual_price(client):
    r = client.post("/api/joueurs", json={"futbin_id": "https://www.futbin.com/27/player/12345/jude-bellingham"})
    assert r.status_code == 201 and r.json["nom"] == "Jude Bellingham"
    pid = r.json["id"]
    assert client.post(f"/api/joueurs/{pid}/prix", json={"prix": "45 000"}).json["prix"] == 45000
    joueurs = client.get("/api/joueurs").json
    assert joueurs[0]["stats"]["dernier"] == 45000
    assert client.get("/").status_code == 200


def test_popular_follow(client, monkeypatch):
    monkeypatch.setattr(futbin, "fetch_popular", lambda limit=50: [{"futbin_id": i, "nom": f"J{i}"} for i in range(1, 31)])
    assert client.post("/api/populaires/actualiser").json["joueurs"] == 30
    assert client.post("/api/populaires/suivre", json={"top": 20}).json["ajoutes"] == 20
    pop = client.get("/api/populaires").json
    assert sum(p["suivi"] for p in pop["joueurs"]) == 20
    assert pop["reguliers"][0]["apparitions"] == 1


def test_collect_errors_are_reported(client, monkeypatch):
    client.post("/api/joueurs", json={"futbin_id": "1", "nom": "Test"})

    def boom(*a, **k):
        raise futbin.FutbinError("bloqué")
    monkeypatch.setattr(futbin, "fetch_price", boom)
    r = client.post("/api/collecter").json
    assert r["releves"] == 0 and "bloqué" in r["erreurs"][0]


def test_calendar_endpoint(client):
    d = client.get("/api/calendrier").json
    assert d["hebdomadaire"] and d["historique"]
