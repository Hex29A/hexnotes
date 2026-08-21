"""Nya tester v1.21: JS-struktur + hint-element."""
def test_fab_hint_element_served(client):
    html = client.get("/").text
    assert 'id="fab-hint"' in html
    assert "Ephemeral" in html


def test_longpress_code_present(client):
    """Langtryckslogiken ska servas: touchstart-listener + HOLD_MS pa FAB."""
    import re
    html = client.get("/").text
    js = "".join(re.findall(r"<script>(.*?)</script>", html, re.S))
    assert "fabLongPress" in js
    assert "HOLD_MS = 500" in js
    assert "touchstart" in js


def test_ephemeral_topbar_hidden_on_mobile_css(client):
    html = client.get("/").text
    assert "#btn-ephemeral { display: none; }" in html
