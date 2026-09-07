# === Optimistic concurrency (base_version) ===
#
# Guards the lost-update case: a note is open in the browser while an AI agent
# writes to it over the API. Without a version check the browser's next
# autosave silently overwrites the agent's work.


def _create(client, auth, content, filename="conflict.md"):
    return client.post(
        "/api/notes", json={"content": content, "filename": filename}, headers=auth
    ).json()


def _read_raw(client, auth, note_id):
    return client.get(f"/api/notes/{note_id}", headers=auth).json()["content"]


# --- version field ---

def test_create_returns_version(client, auth):
    created = _create(client, auth, "Hello")
    assert created["version"]


def test_list_includes_version(client, auth):
    _create(client, auth, "Hello")
    notes = client.get("/api/notes", headers=auth).json()
    assert all(n["version"] for n in notes)


def test_version_changes_when_content_changes(client, auth):
    created = _create(client, auth, "One")
    r = client.patch(
        f"/api/notes/{created['id']}", json={"content": "Two"}, headers=auth
    )
    assert r.json()["version"] != created["version"]


def test_version_stable_for_identical_content(client, auth):
    a = _create(client, auth, "Same", filename="a.md")
    b = _create(client, auth, "Same", filename="b.md")
    assert a["version"] == b["version"]


def test_pin_does_not_change_version(client, auth):
    """Version hashes body only — pinning rewrites frontmatter, not content,
    so an open editor must not be invalidated by it."""
    created = _create(client, auth, "Pin me")
    pinned = client.post(f"/api/notes/{created['id']}/pin", headers=auth).json()
    assert pinned["pinned"] is True
    assert pinned["version"] == created["version"]


# --- happy path ---

def test_patch_with_correct_base_version_succeeds(client, auth):
    created = _create(client, auth, "Original")
    r = client.patch(
        f"/api/notes/{created['id']}",
        json={"content": "Updated", "base_version": created["version"]},
        headers=auth,
    )
    assert r.status_code == 200
    assert r.json()["content"] == "Updated"


def test_patch_without_base_version_still_works(client, auth):
    """Backwards compatible: existing API clients send no base_version."""
    created = _create(client, auth, "Original")
    r = client.patch(
        f"/api/notes/{created['id']}", json={"content": "Updated"}, headers=auth
    )
    assert r.status_code == 200
    assert r.json()["content"] == "Updated"


def test_version_from_response_chains(client, auth):
    """The version returned by a PATCH is valid as the next base_version."""
    created = _create(client, auth, "v1")
    v2 = client.patch(
        f"/api/notes/{created['id']}",
        json={"content": "v2", "base_version": created["version"]},
        headers=auth,
    ).json()
    r = client.patch(
        f"/api/notes/{created['id']}",
        json={"content": "v3", "base_version": v2["version"]},
        headers=auth,
    )
    assert r.status_code == 200


# --- conflict ---

def test_stale_base_version_returns_409(client, auth):
    created = _create(client, auth, "Original")
    # Someone else writes
    client.patch(f"/api/notes/{created['id']}", json={"content": "Theirs"}, headers=auth)
    # We save based on the version we opened
    r = client.patch(
        f"/api/notes/{created['id']}",
        json={"content": "Mine", "base_version": created["version"]},
        headers=auth,
    )
    assert r.status_code == 409


def test_conflict_does_not_overwrite(client, auth):
    created = _create(client, auth, "Original")
    client.patch(f"/api/notes/{created['id']}", json={"content": "Theirs"}, headers=auth)
    client.patch(
        f"/api/notes/{created['id']}",
        json={"content": "Mine", "base_version": created["version"]},
        headers=auth,
    )
    assert _read_raw(client, auth, created["id"]) == "Theirs"


def test_conflict_payload_carries_their_content_and_version(client, auth):
    created = _create(client, auth, "Original")
    theirs = client.patch(
        f"/api/notes/{created['id']}", json={"content": "Theirs"}, headers=auth
    ).json()
    r = client.patch(
        f"/api/notes/{created['id']}",
        json={"content": "Mine", "base_version": created["version"]},
        headers=auth,
    )
    detail = r.json()["detail"]
    assert detail["error"] == "conflict"
    assert detail["content"] == "Theirs"
    assert detail["version"] == theirs["version"]


def test_conflict_version_allows_retry(client, auth):
    """'Keep mine' rebases onto the returned version and succeeds."""
    created = _create(client, auth, "Original")
    client.patch(f"/api/notes/{created['id']}", json={"content": "Theirs"}, headers=auth)
    conflict = client.patch(
        f"/api/notes/{created['id']}",
        json={"content": "Mine", "base_version": created["version"]},
        headers=auth,
    ).json()
    r = client.patch(
        f"/api/notes/{created['id']}",
        json={"content": "Mine", "base_version": conflict["detail"]["version"]},
        headers=auth,
    )
    assert r.status_code == 200
    assert _read_raw(client, auth, created["id"]) == "Mine"


def test_stale_empty_patch_does_not_trash(client, auth):
    """A stale client must not be able to trash a note that moved on."""
    created = _create(client, auth, "Original")
    client.patch(f"/api/notes/{created['id']}", json={"content": "Theirs"}, headers=auth)
    r = client.patch(
        f"/api/notes/{created['id']}",
        json={"content": "   ", "base_version": created["version"]},
        headers=auth,
    )
    assert r.status_code == 409
    assert client.get(f"/api/notes/{created['id']}", headers=auth).status_code == 200


def test_current_base_version_can_still_trash(client, auth):
    """An up-to-date client keeps the normal empty-content trash behaviour."""
    created = _create(client, auth, "Original")
    r = client.patch(
        f"/api/notes/{created['id']}",
        json={"content": "  ", "base_version": created["version"]},
        headers=auth,
    )
    assert r.status_code == 204
    assert client.get(f"/api/notes/{created['id']}", headers=auth).status_code == 404


def test_conflict_does_not_create_history_entry(client, auth):
    """A rejected write must leave no trace."""
    created = _create(client, auth, "Original")
    client.patch(f"/api/notes/{created['id']}", json={"content": "Theirs"}, headers=auth)
    before = client.get(f"/api/notes/{created['id']}/history", headers=auth).json()
    client.patch(
        f"/api/notes/{created['id']}",
        json={"content": "Mine", "base_version": created["version"]},
        headers=auth,
    )
    after = client.get(f"/api/notes/{created['id']}/history", headers=auth).json()
    assert len(before) == len(after)


def test_conflict_requires_auth(client):
    r = client.patch("/api/notes/whatever", json={"content": "x", "base_version": "abc"})
    assert r.status_code == 401
