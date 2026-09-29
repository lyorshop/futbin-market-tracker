"""Récupération des données FUTBIN.

FUTBIN ne propose pas d'API publique : ce module lit ses pages et points
d'accès internes. Leur format peut changer du jour au lendemain ; en cas
d'échec, les fonctions lèvent FutbinError et l'application continue
(la saisie manuelle des prix reste possible depuis le tableau de bord).
"""
import re
import time
from urllib.parse import urljoin
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from . import config

BASE = "https://www.futbin.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}
PLAYER_LINK = re.compile(r"/(\d{2})/player/(\d+)/([^/?#\"']+)")


class FutbinError(Exception):
    pass


_session = requests.Session()
_session.headers.update(HEADERS)
# Les pages joueur de FUTBIN affichent les prix de la plateforme choisie dans ce cookie.
_session.cookies.set("platform", config.PLATFORM, domain=".futbin.com")
# Passe à False dès que le point d'accès JSON ne répond plus, pour ne pas le réessayer à chaque joueur.
_json_ok = True
_last_request = 0.0


def _get(url, **params):
    global _last_request
    wait = config.REQUEST_PAUSE_S - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()
    try:
        resp = _session.get(url, params=params or None, timeout=20)
    except requests.RequestException as exc:
        raise FutbinError(f"FUTBIN injoignable : {exc}") from exc
    if resp.status_code != 200:
        raise FutbinError(f"FUTBIN a répondu {resp.status_code} pour {resp.url}")
    return resp


def parse_price_text(text):
    """'12,500' -> 12500 ; '1.2K' -> 1200 ; '1,35M' -> 1350000 ; '0' ou vide -> None."""
    if text is None:
        return None
    t = str(text).strip().upper().replace(" ", "").replace(" ", "")
    m = re.search(r"(\d+(?:[.,]\d+)*)\s*([KM]?)", t)
    if not m:
        return None
    number, suffix = m.groups()
    if suffix:
        value = float(number.replace(",", "."))
        value *= 1_000 if suffix == "K" else 1_000_000
    else:
        value = float(re.sub(r"[.,]", "", number))
    return int(value) or None


def parse_price_json(data, futbin_id, platform):
    try:
        prices = data[str(futbin_id)]["prices"][platform]
    except (KeyError, TypeError):
        return None
    return parse_price_text(prices.get("LCPrice"))


PRICE_SELECTORS = (
    "[class*=lowest-price]",
    ".price-box .price",
    "[class*=price-box] [class*=price]",
    "[class*=player-price] [class*=price]",
    "[id*=pc-lowest], [id*=pclowest], [id*=lowest]",
)


def parse_price_html(html, platform):
    soup = BeautifulSoup(html, "html.parser")
    scopes = (soup.select(f".platform-{platform}-only") or soup.select(f"[class*=platform-{platform}]")
              or soup.select(f"[class*={platform}-price], [class*=price-{platform}]") or [soup])
    for scope in scopes:
        for selector in PRICE_SELECTORS:
            for el in scope.select(selector):
                # On ignore les fourchettes de prix (« PR: 10,000 - 200,000 ») et les textes longs.
                text = el.get_text(" ", strip=True)
                if len(text) > 20 or "-" in text:
                    continue
                price = parse_price_text(text)
                if price:
                    return price
    return None


# Images de cartes repérées au passage sur les pages joueur, récupérées par la collecte.
images_vues = {}


def player_url(futbin_id, chemin=None, year=None):
    """FUTBIN exige le nom dans l'adresse : /27/player/6/aitana-bonmati."""
    if chemin:
        return urljoin(BASE, chemin)
    return f"{BASE}/{year or config.FUTBIN_YEAR}/player/{futbin_id}"


def fetch_price(futbin_id, platform=None, year=None, chemin=None):
    """Prix le plus bas actuel (BIN) d'un joueur sur une plateforme."""
    platform = platform or config.PLATFORM
    year = year or config.FUTBIN_YEAR
    global _json_ok
    errors = []
    if _json_ok:
        try:
            resp = _get(f"{BASE}/{year}/playerPrices", player=futbin_id)
            price = parse_price_json(resp.json(), futbin_id, platform)
            if price:
                return price
        except (FutbinError, ValueError) as exc:
            _json_ok = False
            errors.append(str(exc))
    try:
        resp = _get(player_url(futbin_id, chemin, year))
        images_vues[futbin_id] = parse_card_image(resp.text)
        price = parse_price_html(resp.text, platform)
        if price:
            return price
    except FutbinError as exc:
        errors.append(str(exc))
    raise FutbinError("Prix introuvable pour le joueur %s. %s" % (futbin_id, " | ".join(errors)))


def parse_history_json(data, platform):
    points = data.get(platform) if isinstance(data, dict) else None
    out = []
    for item in points or []:
        try:
            ms, price = item[0], int(item[1])
        except (TypeError, ValueError, IndexError):
            continue
        if price > 0:
            ts = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(microsecond=0)
            out.append((ts.isoformat(), price))
    return out


def fetch_history(futbin_id, platform=None, year=None):
    """Historique quotidien des prix (graphique FUTBIN), y compris des saisons passées."""
    platform = platform or config.PLATFORM
    year = year or config.FUTBIN_YEAR
    resp = _get(f"{BASE}/{year}/playerGraph", type="daily_graph", year=year, player=futbin_id)
    try:
        return parse_history_json(resp.json(), platform)
    except ValueError as exc:
        raise FutbinError("Historique illisible") from exc


def parse_player_links(html, year=None, limit=50):
    """Extrait les joueurs (id, nom) dans l'ordre d'apparition sur une page FUTBIN."""
    soup = BeautifulSoup(html, "html.parser")
    seen, players = set(), []
    for a in soup.find_all("a", href=True):
        m = PLAYER_LINK.search(a["href"])
        if not m:
            continue
        link_year, pid, slug = m.groups()
        if year and link_year != str(year):
            continue
        pid = int(pid)
        if pid in seen:
            continue
        seen.add(pid)
        name = " ".join(a.get_text(" ", strip=True).split()) or slug.replace("-", " ").title()
        if len(name) > 40 or not re.search(r"[A-Za-zÀ-ÿ]", name):
            name = slug.replace("-", " ").title()
        img = a.find("img")
        src = (img.get("data-src") or img.get("src") or "") if img else ""
        image = urljoin(BASE, src) if src and not src.startswith("data:") else None
        players.append({"futbin_id": pid, "nom": name, "image": image, "chemin": m.group(0)})
        if len(players) >= limit:
            break
    return players


def parse_card_image(html):
    """Adresse de l'image de la carte sur une page joueur FUTBIN."""
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
    if meta and meta.get("content"):
        return urljoin(BASE, meta["content"])
    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("src") or ""
        attrs = " ".join(img.get("class", [])) + " " + src
        if src and not src.startswith("data:") and re.search(r"player|card", attrs, re.I):
            return urljoin(BASE, src)
    return None


def fetch_image_url(futbin_id, year=None, chemin=None):
    return parse_card_image(_get(player_url(futbin_id, chemin, year)).text)


def download_image(url):
    """Télécharge une image ; renvoie (octets, type)."""
    try:
        resp = _session.get(url, headers={"Referer": BASE + "/"}, timeout=20)
    except requests.RequestException as exc:
        raise FutbinError(f"Image injoignable : {exc}") from exc
    ctype = resp.headers.get("Content-Type", "").split(";")[0]
    if resp.status_code != 200 or not ctype.startswith("image/"):
        raise FutbinError(f"Image indisponible ({resp.status_code}, {ctype or 'type inconnu'})")
    return resp.content, ctype


def fetch_popular(limit=50, year=None):
    """Joueurs les plus consultés/utilisés du moment (page « Popular » de FUTBIN)."""
    year = year or config.FUTBIN_YEAR
    resp = _get(f"{BASE}/popular")
    players = parse_player_links(resp.text, year=year, limit=limit)
    if not players:
        raise FutbinError("Aucun joueur trouvé sur la page Popular de FUTBIN")
    return players


def diagnostic(futbin_id, platform=None, year=None, chemin=None):
    """Rapport texte de ce que renvoie FUTBIN pour un joueur, pour corriger la lecture des prix."""
    platform = platform or config.PLATFORM
    year = year or config.FUTBIN_YEAR
    lines = [f"Joueur {futbin_id} - plateforme {platform} - annee {year}", ""]
    for label, url, params in (
        ("JSON", f"{BASE}/{year}/playerPrices", {"player": futbin_id}),
        ("PAGE", player_url(futbin_id, chemin, year), {}),
    ):
        try:
            resp = _session.get(url, params=params or None, timeout=20)
        except requests.RequestException as exc:
            lines += [f"== {label} : erreur {exc}", ""]
            continue
        lines.append(f"== {label} : {resp.status_code} {resp.url} ({len(resp.text)} caracteres)")
        if label == "JSON":
            lines += [resp.text[:1500], ""]
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        lines.append(f"Titre : {soup.title.get_text(strip=True) if soup.title else '-'}")
        lines.append(f"Prix lu par l'application : {parse_price_html(resp.text, platform)}")
        lines.append("")
        lines.append("-- Elements dont la classe ou l'id contient 'price' ou 'lowest' :")
        seen = 0
        for el in soup.find_all(True):
            attrs = " ".join(el.get("class", [])) + " " + (el.get("id") or "")
            if re.search(r"price|lowest", attrs, re.I):
                text = " ".join(el.get_text(" ", strip=True).split())[:80]
                lines.append(f"<{el.name} class='{' '.join(el.get('class', []))}' id='{el.get('id') or ''}'> {text}")
                seen += 1
                if seen >= 80:
                    break
        lines.append("")
        lines.append("-- Extraits du code autour de 'price' :")
        for m in list(re.finditer(r"price", resp.text, re.I))[:12]:
            lines.append(resp.text[max(0, m.start() - 200): m.start() + 200].replace("\n", " "))
            lines.append("...")
    return "\n".join(lines)
