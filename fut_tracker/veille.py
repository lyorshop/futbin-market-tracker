"""Veille des comptes et forums qui publient des infos sur le marché.

- Reddit : lu automatiquement (flux JSON public).
- RSS / Atom : n'importe quel flux (chaîne YouTube, site d'actualité, passerelle X).
- X (Twitter) : l'API officielle est payante ; on lit le compte seulement si un
  flux RSS le relaie (champ 'flux', par ex. créé avec rss.app ou RSSHub).
Chaque publication reçoit des tags (fuite, promo, crash…) et une note d'importance.
"""
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

from . import config, db

HEADERS = {"User-Agent": "fut-market-tracker/1.0 (suivi personnel)"}
ATOM = "{http://www.w3.org/2005/Atom}"


def load_sources(path=None):
    with open(path or config.SOURCES_PATH, encoding="utf-8") as f:
        return json.load(f)


def tag(text, keywords, weights):
    low = text.lower()
    tags = []
    for name, words in keywords.items():
        if any(re.search(r"(?<![a-z0-9])" + re.escape(w) + r"s?(?![a-z0-9])", low) for w in words):
            tags.append(name)
    return tags, sum(weights.get(t, 1) for t in tags)


def _iso(value):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_feed(xml_text):
    """Lit un flux RSS 2.0 ou Atom et renvoie [{titre, url, publie_le}]."""
    root = ET.fromstring(xml_text)
    items = []
    for it in root.iter("item"):
        items.append({
            "titre": (it.findtext("title") or it.findtext("description") or "").strip(),
            "url": (it.findtext("link") or "").strip(),
            "publie_le": _iso(it.findtext("pubDate")),
        })
    for entry in root.iter(ATOM + "entry"):
        link = entry.find(ATOM + "link")
        items.append({
            "titre": (entry.findtext(ATOM + "title") or "").strip(),
            "url": link.get("href", "") if link is not None else "",
            "publie_le": _iso(entry.findtext(ATOM + "published") or entry.findtext(ATOM + "updated")),
        })
    return [i for i in items if i["url"] and i["titre"]]


def parse_reddit(data):
    posts = []
    for child in data.get("data", {}).get("children", []):
        d = child.get("data", {})
        created = d.get("created_utc")
        posts.append({
            "titre": d.get("title", ""),
            "url": "https://www.reddit.com" + d.get("permalink", ""),
            "publie_le": datetime.fromtimestamp(created, tz=timezone.utc).isoformat() if created else None,
        })
    return posts


def fetch_source(src):
    if src["type"] == "reddit":
        resp = requests.get(f"https://www.reddit.com/r/{src['sub']}/new.json", params={"limit": 50},
                            headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return parse_reddit(resp.json())
    if src.get("flux"):
        resp = requests.get(src["flux"], headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return parse_feed(resp.text)
    return None  # compte X/YouTube sans flux : rien à lire automatiquement


def refresh(conn, cfg=None):
    """Lit toutes les sources actives. Renvoie un compte-rendu par source."""
    cfg = cfg or load_sources()
    keywords, weights = cfg.get("mots_cles", {}), cfg.get("poids", {})
    report = []
    for src in cfg.get("sources", []):
        if not src.get("actif", True):
            continue
        try:
            items = fetch_source(src)
        except (requests.RequestException, ET.ParseError, ValueError) as exc:
            report.append({"source": src["nom"], "erreur": str(exc)})
            continue
        if items is None:
            report.append({"source": src["nom"], "erreur": "pas de flux configuré (voir README)"})
            continue
        new = 0
        for item in items:
            tags, score = tag(item["titre"], keywords, weights)
            # Sur les forums on ne garde que ce qui parle du marché ; les comptes suivis sont gardés en entier.
            if src["type"] == "reddit" and not tags:
                continue
            new += db.save_post(conn, {**item, "source": src["nom"], "tags": tags, "importance": score})
        report.append({"source": src["nom"], "nouveaux": new})
    return report
