import argparse
from datetime import date

from flask import Flask, g, jsonify, render_template, request

from . import analyse, calendrier, collecte, config, db, futbin

app = Flask(__name__)


def _conn():
    if "db" not in g:
        g.db = db.connect()
    return g.db


@app.teardown_appcontext
def _close(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@app.get("/")
def index():
    return render_template("index.html", plateforme=config.PLATFORM.upper(), annee=config.FUTBIN_YEAR)


@app.get("/api/etat")
def api_etat():
    return jsonify({**collecte.etat, "plateforme": config.PLATFORM, "annee": config.FUTBIN_YEAR,
                    "intervalle_min": config.COLLECT_EVERY_MIN})


@app.get("/api/joueurs")
def api_joueurs():
    conn = _conn()
    ctx = calendrier.market_context(calendrier.load())
    out = []
    for p in db.list_players(conn):
        st = analyse.stats(db.price_history(conn, p["id"], config.PLATFORM))
        out.append({**dict(p), "stats": st, "signal": analyse.signal(st, ctx)})
    out.sort(key=lambda x: -x["signal"]["score"])
    return jsonify(out)


@app.post("/api/joueurs")
def api_add_joueur():
    body = request.get_json(force=True)
    futbin_id = str(body.get("futbin_id", "")).strip()
    m = futbin.PLAYER_LINK.search(futbin_id)  # accepte aussi un lien FUTBIN collé
    if m:
        futbin_id = m.group(2)
        nom = body.get("nom") or m.group(3).replace("-", " ").title()
    else:
        nom = body.get("nom") or f"Joueur {futbin_id}"
    if not futbin_id.isdigit():
        return jsonify({"erreur": "Identifiant ou lien FUTBIN invalide"}), 400
    conn = _conn()
    row = db.add_player(conn, int(futbin_id), nom.strip())
    conn.commit()
    return jsonify(dict(row)), 201


@app.delete("/api/joueurs/<int:joueur_id>")
def api_del_joueur(joueur_id):
    conn = _conn()
    db.remove_player(conn, joueur_id)
    conn.commit()
    return "", 204


@app.get("/api/joueurs/<int:joueur_id>/prix")
def api_prix(joueur_id):
    series = db.price_history(_conn(), joueur_id, config.PLATFORM)
    return jsonify({"points": series, "stats": analyse.stats(series),
                    "profil": analyse.weekday_profile(series)})


@app.post("/api/joueurs/<int:joueur_id>/prix")
def api_add_prix(joueur_id):
    prix = futbin.parse_price_text(request.get_json(force=True).get("prix"))
    if not prix:
        return jsonify({"erreur": "Prix invalide"}), 400
    conn = _conn()
    db.add_price(conn, joueur_id, config.PLATFORM, prix)
    conn.commit()
    return jsonify({"prix": prix}), 201


@app.post("/api/joueurs/<int:joueur_id>/historique")
def api_historique(joueur_id):
    year = (request.get_json(silent=True) or {}).get("annee") or config.FUTBIN_YEAR
    try:
        n = collecte.run_locked(collecte.import_history, joueur_id, year=year)
    except futbin.FutbinError as exc:
        return jsonify({"erreur": str(exc)}), 502
    return jsonify({"points": n})


@app.post("/api/collecter")
def api_collecter():
    return jsonify(collecte.run_locked(collecte.collect_prices))


@app.get("/api/populaires")
def api_populaires():
    conn = _conn()
    latest, ts = db.latest_popular(conn)
    followed = {p["futbin_id"] for p in db.list_players(conn)}
    for p in latest:
        p["suivi"] = p["futbin_id"] in followed
    return jsonify({"releve_le": ts, "joueurs": latest, "reguliers": db.popularity_counts(conn)})


@app.post("/api/populaires/actualiser")
def api_populaires_maj():
    return jsonify(collecte.run_locked(collecte.collect_popular))


@app.post("/api/populaires/suivre")
def api_populaires_suivre():
    top = int((request.get_json(silent=True) or {}).get("top", 20))
    return jsonify({"ajoutes": collecte.run_locked(collecte.follow_popular, top=top)})


@app.get("/api/calendrier")
def api_calendrier():
    data = calendrier.load()
    return jsonify({
        "a_venir": calendrier.upcoming(data),
        "hebdomadaire": calendrier.weekly(data),
        "historique": calendrier.history(data),
        "contexte": calendrier.market_context(data),
    })


@app.post("/api/calendrier")
def api_add_evenement():
    body = request.get_json(force=True)
    try:
        ev = {"nom": body["nom"].strip(), "effet": body.get("effet", "crash"),
              "debut": date.fromisoformat(body["debut"]).isoformat(),
              "fin": date.fromisoformat(body.get("fin") or body["debut"]).isoformat(),
              "detail": body.get("detail", "")}
    except (KeyError, ValueError, AttributeError):
        return jsonify({"erreur": "Nom et date de début (AAAA-MM-JJ) obligatoires"}), 400
    data = calendrier.load()
    data.setdefault("manuel", []).append(ev)
    calendrier.save(data)
    return jsonify(ev), 201


@app.get("/api/veille")
def api_veille():
    mini = int(request.args.get("importance", 0))
    return jsonify(db.list_posts(_conn(), min_importance=mini))


@app.post("/api/veille/actualiser")
def api_veille_maj():
    return jsonify(collecte.run_locked(collecte.collect_news))


def main():
    parser = argparse.ArgumentParser(description="Suivi du marché FUT")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--sans-collecte", action="store_true", help="désactive la collecte automatique")
    args = parser.parse_args()
    config.DATA_DIR.mkdir(exist_ok=True)
    if not args.sans_collecte:
        collecte.start_background()
    print(f"Tableau de bord : http://127.0.0.1:{args.port}")
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
