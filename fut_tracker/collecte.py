"""Tâches de collecte : prix, joueurs populaires, veille. Lancées à la main ou en arrière-plan."""
import threading
import time
from datetime import datetime

from . import config, db, futbin, veille

etat = {"prix": None, "populaires": None, "veille": None, "erreurs": []}
_lock = threading.Lock()


def _note(kind, msg=None, errors=()):
    etat[kind] = datetime.now().isoformat(timespec="seconds")
    etat["erreurs"] = ([f"[{kind}] {e}" for e in errors] + etat["erreurs"])[:30]


def collect_prices(conn, platform=None):
    platform = platform or config.PLATFORM
    ok, errors = 0, []
    for p in db.list_players(conn):
        try:
            db.add_price(conn, p["id"], platform, futbin.fetch_price(p["futbin_id"], platform))
            ok += 1
        except futbin.FutbinError as exc:
            errors.append(f"{p['nom']} : {exc}")
    conn.commit()
    _note("prix", errors=errors)
    return {"releves": ok, "erreurs": errors}


def collect_popular(conn, limit=50):
    try:
        players = futbin.fetch_popular(limit=limit)
    except futbin.FutbinError as exc:
        _note("populaires", errors=[str(exc)])
        return {"joueurs": 0, "erreurs": [str(exc)]}
    db.save_popular(conn, players)
    conn.commit()
    _note("populaires")
    return {"joueurs": len(players), "erreurs": []}


def follow_popular(conn, top=20):
    """Ajoute les N joueurs les plus utilisés à la liste de suivi."""
    players, _ = db.latest_popular(conn)
    for p in players[:top]:
        db.add_player(conn, p["futbin_id"], p["nom"], origine="populaire")
    conn.commit()
    return len(players[:top])


def import_history(conn, joueur_id, year=None, platform=None):
    platform = platform or config.PLATFORM
    row = conn.execute("SELECT futbin_id FROM joueurs WHERE id = ?", (joueur_id,)).fetchone()
    if not row:
        return 0
    points = futbin.fetch_history(row["futbin_id"], platform, year)
    for ts, price in points:
        db.add_price(conn, joueur_id, platform, price, ts)
    conn.commit()
    return len(points)


def collect_news(conn):
    report = veille.refresh(conn)
    conn.commit()
    _note("veille", errors=[f"{r['source']} : {r['erreur']}" for r in report if "erreur" in r])
    return report


def _loop():
    last_popular = 0.0
    while True:
        with _lock, db.session() as conn:
            if time.time() - last_popular >= config.POPULAR_EVERY_H * 3600:
                collect_popular(conn)
                last_popular = time.time()
            collect_prices(conn)
            collect_news(conn)
        time.sleep(config.COLLECT_EVERY_MIN * 60)


def start_background():
    threading.Thread(target=_loop, name="collecte", daemon=True).start()


def run_locked(fn, *args, **kwargs):
    """Exécute une tâche sans chevaucher la collecte automatique."""
    with _lock, db.session() as conn:
        return fn(conn, *args, **kwargs)
