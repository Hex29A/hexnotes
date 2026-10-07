"""Regression test v1.21.1: ephemeral must survive naming (the doRename flow)."""
def test_create_with_filename_and_ttl(client, auth):
    """Exactly the mobile flow that was broken: POST with filename + ttl_hours."""
    r = client.post("/api/notes", json={
        "content": "mobilnot", "filename": "test-ephemeral.md", "ttl_hours": 48,
    }, headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert data["expires_at"] is not None, "ttl_hours was ignored on POST with filename"


def test_served_js_doRename_includes_ttl(client):
    """Frontend regression: the doRename POST must contain the ttl_hours logic."""
    import re
    html = client.get("/").text
    js = "".join(re.findall(r"<script>(.*?)</script>", html, re.S))
    assert "if (ephemeralArmed) renameBody.ttl_hours = 48;" in js
