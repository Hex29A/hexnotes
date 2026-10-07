"""Unsaved text survives the app being closed (local drafts, flush on hide).

Every keystroke is mirrored to localStorage until the server has it; hiding
the page sends pending text at once; on the next start, drafts the server
does not have are sent up — onto the note if it is unchanged, otherwise as a
note of their own so nothing is ever written over. Run in a real browser,
like test_format_shortcuts.py.
"""
import json
import time

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

import backend.main as bm  # noqa: E402
from tests.test_format_shortcuts import TOKEN, browser, server  # noqa: E402,F401


def _wait(pg, expr, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        if pg.evaluate(expr):
            return
        time.sleep(0.05)
    raise AssertionError("timed out waiting for: " + expr)


def _open(server, browser, note_id, drafts=None):
    url, _ = server
    ctx = browser.new_context()
    script = f"localStorage.setItem('hexnotes_token', '{TOKEN}');"
    if drafts is not None:
        script += f"localStorage.setItem('hexnotes_drafts', {json.dumps(json.dumps(drafts))});"
    ctx.add_init_script(script)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"{url}/#{note_id}")
    _wait(pg, f"typeof activeNoteId !== 'undefined' && activeNoteId === {note_id!r}")
    return ctx, pg, errors


@pytest.fixture
def notes(server):
    _, notes = server
    for f in notes.glob("*.md"):
        f.unlink()
    (notes / "home.md").write_text("# Home\n")
    (notes / "shop.md").write_text("milk\n")
    bm.build_index()
    return notes


def _field(note, name):
    return note[name] if isinstance(note, dict) else getattr(note, name)


def _contents():
    """Note bodies as the API sees them (the files carry frontmatter)."""
    return {k: _field(n, "content") for k, n in bm.notes_index.items()}


def test_typing_keeps_a_draft_until_saved_and_shows_state(server, browser, notes):
    ctx, pg, errors = _open(server, browser, "shop")
    pg.locator(".cm-content").click()
    pg.keyboard.press("Control+End")
    pg.keyboard.type("eggs")
    assert pg.evaluate("$saveIndicator.textContent") == "●"
    draft = json.loads(pg.evaluate("localStorage.getItem('hexnotes_drafts')"))
    assert draft["shop"]["content"].endswith("eggs")
    _wait(pg, "pendingContent === null && !isSaving")
    assert pg.evaluate("$saveIndicator.textContent") == "✓"
    assert pg.evaluate("localStorage.getItem('hexnotes_drafts')") is None
    ctx.close()
    assert not errors


def test_hiding_the_page_saves_at_once(server, browser, notes):
    ctx, pg, errors = _open(server, browser, "shop")
    pg.locator(".cm-content").click()
    pg.keyboard.press("Control+End")
    pg.keyboard.type("bread")
    pg.evaluate("Object.defineProperty(document, 'hidden', {value: true, configurable: true});"
                "document.dispatchEvent(new Event('visibilitychange'))")
    time.sleep(0.4)  # well inside the 1 s debounce
    assert _contents()["shop"].endswith("bread")
    ctx.close()
    assert not errors


def test_draft_for_unchanged_note_is_saved_onto_it(server, browser, notes):
    base = _field(bm.notes_index["shop"], "version")
    drafts = {"shop": {"content": "milk\nlost words", "base": base, "t": 1}}
    ctx, pg, errors = _open(server, browser, "home", drafts)
    _wait(pg, "localStorage.getItem('hexnotes_drafts') === null")
    assert _contents()["shop"] == "milk\nlost words"
    assert "Restored" in pg.evaluate("$errorBar.textContent")
    ctx.close()
    assert not errors


def test_draft_for_changed_note_becomes_its_own_note(server, browser, notes):
    drafts = {"shop": {"content": "milk\nmine", "base": "stale-version", "t": 1}}
    ctx, pg, errors = _open(server, browser, "home", drafts)
    _wait(pg, "localStorage.getItem('hexnotes_drafts') === null")
    assert _contents()["shop"] == "milk\n"   # never written over
    assert "milk\nmine" in _contents().values()
    ctx.close()
    assert not errors


def test_draft_already_on_server_is_just_dropped(server, browser, notes):
    drafts = {"": {"content": "milk\n", "t": 1}, "shop": {"content": "milk\n", "base": "x", "t": 1}}
    ctx, pg, errors = _open(server, browser, "home", drafts)
    _wait(pg, "localStorage.getItem('hexnotes_drafts') === null")
    assert len(_contents()) == 2
    ctx.close()
    assert not errors


def test_new_note_then_new_again_keeps_both_apart(server, browser, notes):
    ctx, pg, errors = _open(server, browser, "home")
    pg.evaluate("createNewNote()")
    pg.keyboard.type("first quick thought")
    pg.evaluate("createNewNote()")          # within the debounce
    _wait(pg, "!isSaving")
    time.sleep(0.3)
    assert pg.evaluate("isNew && activeNoteId === null && $editor.value === ''")
    assert "first quick thought" in _contents().values()
    ctx.close()
    assert not errors
