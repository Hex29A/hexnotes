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


def test_frontend_pages_the_note_list_instead_of_a_fixed_limit():
    """Regression: ett hårdkodat limit=200 lät noter utöver det tyst falla
    bort ur sidofältet. Se #12."""
    from pathlib import Path
    js = Path(__file__).resolve().parent.parent / "static" / "index.html"
    src = js.read_text(encoding="utf-8")
    import re
    assert "async function fetchAllNotes(" in src
    # Sidstorleken ska komma från NOTES_PAGE_SIZE. Den enda hårdkodade siffran
    # som får finnas kvar är tokenvalideringens limit=1, som bara frågar om
    # token duger och aldrig ska bli en lista.
    hardcoded = [m.group(0) for m in re.finditer(r"/api/notes\?limit=\d+", src)
                 if m.group(0) != "/api/notes?limit=1"]
    assert hardcoded == [], f"hårdkodat limit kvar: {hardcoded}"
    assert src.count("fetchAllNotes(") >= 6, "alla listhämtningar går inte genom fetchAllNotes"
