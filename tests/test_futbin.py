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
    assert players == [{"futbin_id": 100, "nom": "Mbappé"}, {"futbin_id": 200, "nom": "Vini Jr"}]
