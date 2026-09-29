from fut_tracker import veille

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>TOTY leaked loading screen</title><link>https://x.com/a/1</link><pubDate>Tue, 29 Sep 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""
ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Market crash incoming?</title><link href="https://youtube.com/watch?v=1"/><published>2026-09-28T18:00:00+00:00</published></entry>
</feed>"""


def test_parse_rss_and_atom():
    rss = veille.parse_feed(RSS)
    assert rss == [{"titre": "TOTY leaked loading screen", "url": "https://x.com/a/1", "publie_le": "2026-09-29T10:00:00+00:00"}]
    atom = veille.parse_feed(ATOM)
    assert atom[0]["url"] == "https://youtube.com/watch?v=1"


def test_tagging():
    cfg = veille.load_sources()
    tags, score = veille.tag("TOTY leaked: market crash before packs", cfg["mots_cles"], cfg["poids"])
    assert {"fuite", "promo", "crash", "pack"} <= set(tags)
    assert score >= 10
    assert veille.tag("Best formation for 4-2-3-1", cfg["mots_cles"], cfg["poids"]) == ([], 0)
    # « drop » ne doit pas déclencher sur « dropdown »
    assert "crash" not in veille.tag("dropdown menu bug", cfg["mots_cles"], cfg["poids"])[0]


def test_parse_reddit():
    data = {"data": {"children": [{"data": {"title": "SBC fodder prices", "permalink": "/r/fut/1", "created_utc": 1790000000}}]}}
    assert veille.parse_reddit(data)[0]["url"] == "https://www.reddit.com/r/fut/1"
