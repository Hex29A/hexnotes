"""Regression checks for new-note focus and ephemeral confirmation UI."""


def test_new_note_focuses_editor_instead_of_filename_input(client):
    html = client.get("/").text
    start = html.index("function createNewNote")
    end = html.index("// === SECTION: AUTOSAVE ===", start)
    create_note = html[start:end]
    assert "$editor.focus();" in create_note
    assert "startRename();" not in create_note


def test_editor_header_has_ephemeral_badge(client):
    html = client.get("/").text
    assert 'id="ephemeral-badge"' in html
    assert "function updateEphemeralBadge()" in html
    assert "Ephemeral - 48h" in html


def test_long_press_cancel_receives_its_event(client):
    html = client.get("/").text
    assert "function cancel(e)" in html
    assert "$fab.addEventListener('touchend', cancel);" in html
