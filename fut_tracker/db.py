import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS joueurs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    futbin_id INTEGER NOT NULL UNIQUE,
    nom TEXT NOT NULL,
    origine TEXT NOT NULL DEFAULT 'manuel',
    actif INTEGER NOT NULL DEFAULT 1,
    ajoute_le TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prix (
    joueur_id INTEGER NOT NULL REFERENCES joueurs(id) ON DELETE CASCADE,
    plateforme TEXT NOT NULL,
    prix INTEGER NOT NULL,
    releve_le TEXT NOT NULL,
    UNIQUE (joueur_id, plateforme, releve_le)
);
CREATE INDEX IF NOT EXISTS idx_prix_joueur ON prix (joueur_id, releve_le);
CREATE TABLE IF NOT EXISTS populaires (
    futbin_id INTEGER NOT NULL,
    nom TEXT NOT NULL,
    rang INTEGER NOT NULL,
    releve_le TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pages (
    futbin_id INTEGER PRIMARY KEY,
    chemin TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS images (
    futbin_id INTEGER PRIMARY KEY,
    url TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS publications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    titre TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    publie_le TEXT,
    recupere_le TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    importance INTEGER NOT NULL DEFAULT 0
);
"""


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(path=None):
    path = path or config.DB_PATH
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def session(path=None):
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_player(conn, futbin_id, nom, origine="manuel"):
    conn.execute(
        "INSERT INTO joueurs (futbin_id, nom, origine, ajoute_le) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(futbin_id) DO UPDATE SET actif = 1",
        (int(futbin_id), nom, origine, now_iso()),
    )
    return conn.execute("SELECT * FROM joueurs WHERE futbin_id = ?", (int(futbin_id),)).fetchone()


def list_players(conn, only_active=True):
    sql = "SELECT * FROM joueurs"
    if only_active:
        sql += " WHERE actif = 1"
    return conn.execute(sql + " ORDER BY nom").fetchall()


def remove_player(conn, joueur_id):
    conn.execute("UPDATE joueurs SET actif = 0 WHERE id = ?", (joueur_id,))


def add_price(conn, joueur_id, plateforme, prix, releve_le=None):
    conn.execute(
        "INSERT OR IGNORE INTO prix (joueur_id, plateforme, prix, releve_le) VALUES (?, ?, ?, ?)",
        (joueur_id, plateforme, int(prix), releve_le or now_iso()),
    )


def price_history(conn, joueur_id, plateforme):
    rows = conn.execute(
        "SELECT releve_le, prix FROM prix WHERE joueur_id = ? AND plateforme = ? ORDER BY releve_le",
        (joueur_id, plateforme),
    ).fetchall()
    return [(r["releve_le"], r["prix"]) for r in rows]


def save_popular(conn, players):
    ts = now_iso()
    conn.executemany(
        "INSERT INTO populaires (futbin_id, nom, rang, releve_le) VALUES (?, ?, ?, ?)",
        [(p["futbin_id"], p["nom"], i + 1, ts) for i, p in enumerate(players)],
    )
    for p in players:
        save_image_url(conn, p["futbin_id"], p.get("image"))
        save_page(conn, p["futbin_id"], p.get("chemin"))


def save_image_url(conn, futbin_id, url):
    if url:
        conn.execute("INSERT OR REPLACE INTO images (futbin_id, url) VALUES (?, ?)", (int(futbin_id), url))


def save_page(conn, futbin_id, chemin):
    if chemin:
        conn.execute("INSERT OR REPLACE INTO pages (futbin_id, chemin) VALUES (?, ?)", (int(futbin_id), chemin))


def get_page(conn, futbin_id):
    row = conn.execute("SELECT chemin FROM pages WHERE futbin_id = ?", (int(futbin_id),)).fetchone()
    return row["chemin"] if row else None


def get_image_url(conn, futbin_id):
    row = conn.execute("SELECT url FROM images WHERE futbin_id = ?", (int(futbin_id),)).fetchone()
    return row["url"] if row else None


def latest_popular(conn):
    last = conn.execute("SELECT MAX(releve_le) AS ts FROM populaires").fetchone()["ts"]
    if not last:
        return [], None
    rows = conn.execute(
        "SELECT futbin_id, nom, rang FROM populaires WHERE releve_le = ? ORDER BY rang", (last,)
    ).fetchall()
    return [dict(r) for r in rows], last


def popularity_counts(conn, limit=50):
    """Nombre de relevés où chaque joueur apparaît dans le top : mesure de la régularité."""
    rows = conn.execute(
        "SELECT futbin_id, nom, COUNT(*) AS apparitions, MIN(rang) AS meilleur_rang, "
        "ROUND(AVG(rang), 1) AS rang_moyen FROM populaires GROUP BY futbin_id "
        "ORDER BY apparitions DESC, rang_moyen ASC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def save_post(conn, post):
    cur = conn.execute(
        "INSERT OR IGNORE INTO publications (source, titre, url, publie_le, recupere_le, tags, importance) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (post["source"], post["titre"], post["url"], post.get("publie_le"), now_iso(),
         ",".join(post.get("tags", [])), post.get("importance", 0)),
    )
    return cur.rowcount == 1


def list_posts(conn, limit=100, min_importance=0):
    rows = conn.execute(
        "SELECT * FROM publications WHERE importance >= ? "
        "ORDER BY COALESCE(publie_le, recupere_le) DESC LIMIT ?",
        (min_importance, limit),
    ).fetchall()
    return [dict(r, tags=[t for t in r["tags"].split(",") if t]) for r in rows]
