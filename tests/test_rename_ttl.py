"""Regressionstest v1.21.1: ephemeral ska overleva namngivning (doRename-flodet)."""
def test_create_with_filename_and_ttl(client, auth):
    """Exakt det mobilflode som var trasigt: POST med filename + ttl_hours."""
    r = client.post("/api/notes", json={
        "content": "mobilnot", "filename": "test-ephemeral.md", "ttl_hours": 48,
    }, headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert data["expires_at"] is not None, "ttl_hours ignorerades vid POST med filename"


def test_served_js_doRename_includes_ttl(client):
    """Frontend-regression: doRename-POST:en ska innehalla ttl_hours-logik."""
    import re
    html = client.get("/").text
    js = "".join(re.findall(r"<script>(.*?)</script>", html, re.S))
    assert "if (ephemeralArmed) renameBody.ttl_hours = 48;" in js
