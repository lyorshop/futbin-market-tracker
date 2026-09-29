from fut_tracker import futbin


def test_parse_price_text():
    assert futbin.parse_price_text("12,500") == 12500
    assert futbin.parse_price_text("1.2K") == 1200
    assert futbin.parse_price_text("1,35M") == 1350000
    assert futbin.parse_price_text("850") == 850
    assert futbin.parse_price_text("0") is None
    assert futbin.parse_price_text("") is None


def test_parse_price_json():
    data = {"231747": {"prices": {"pc": {"LCPrice": "1,250,000"}, "ps": {"LCPrice": "990,000"}}}}
    assert futbin.parse_price_json(data, 231747, "pc") == 1250000
    assert futbin.parse_price_json(data, 1, "pc") is None


def test_parse_price_html():
    html = """<div class="platform-ps-only"><div class="price lowest-price-1">900</div></div>
              <div class="platform-pc-only"><div class="price inline-with-icon lowest-price-1">15,750</div></div>"""
    assert futbin.parse_price_html(html, "pc") == 15750


def test_parse_history_json():
    data = {"pc": [[1727740800000, 12000], [1727827200000, 0], [1727913600000, 11000]]}
    points = futbin.parse_history_json(data, "pc")
    assert [p for _, p in points] == [12000, 11000]
    assert points[0][0].startswith("2024-10-01")


def test_parse_player_links():
    html = """<a href="/27/player/100/kylian-mbappe"><span>Mbappé</span></a>
              <a href="/27/player/100/kylian-mbappe">doublon</a>
              <a href="/27/player/200/vini-jr"><img src="x.png"></a>
              <a href="/26/player/300/ancienne-carte">Ancienne</a>"""
    players = futbin.parse_player_links(html, year=27)
    assert [(p["futbin_id"], p["nom"]) for p in players] == [(100, "Mbappé"), (200, "Vini Jr")]
    assert players[0]["chemin"] == "/27/player/100/kylian-mbappe"
    assert players[1]["image"] == "https://www.futbin.com/x.png"


def test_player_url_uses_known_path():
    assert futbin.player_url(6, "/27/player/6/aitana-bonmati") == "https://www.futbin.com/27/player/6/aitana-bonmati"
    assert futbin.player_url(6, year="27") == "https://www.futbin.com/27/player/6"


def test_parse_card_image():
    html = '<meta property="og:image" content="https://cdn.futbin.com/cards/6.png">'
    assert futbin.parse_card_image(html) == "https://cdn.futbin.com/cards/6.png"
    html = '<img class="player-card-img" src="/content/players/6.png">'
    assert futbin.parse_card_image(html) == "https://www.futbin.com/content/players/6.png"


def test_parse_price_html_ignores_price_range():
    html = """<div class="price-range">PR: 10,000 - 200,000</div>
              <div class="player-price-box"><span class="price-value">48.5K</span></div>"""
    assert futbin.parse_price_html(html, "pc") == 48500


def test_diagnostic_report(monkeypatch):
    class Resp:
        def __init__(self, url, text, status=200):
            self.url, self.text, self.status_code = url, text, status

    def fake_get(url, params=None, timeout=None):
        if "playerPrices" in url:
            return Resp(url, "Not found", 404)
        return Resp(url, '<title>Joueur</title><div class="platform-pc-only"><div class="lowest-price-1">12,000</div></div>')
    monkeypatch.setattr(futbin._session, "get", fake_get)
    report = futbin.diagnostic(1)
    assert "JSON : 404" in report and "Prix lu par l'application : 12000" in report
